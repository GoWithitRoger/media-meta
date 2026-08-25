import hashlib
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from mutagen.mp4 import MP4

from media_meta import (
    SegmentProvenance,
    read_segment_provenance,
    write_segment_provenance,
)


def _provenance() -> SegmentProvenance:
    return SegmentProvenance(
        parent_asset_id="asset-123",
        parent_stable_identity="conversation-corpus:asset-123",
        parent_filename="original.m4a",
        parent_sha256=hashlib.sha256(b"parent").hexdigest(),
        parent_size_bytes=123456,
        parent_duration_samples=441000,
        parent_codec="AAC-LC",
        segment_id="asset-123-0001",
        source_start_sample=44100,
        source_end_sample=132300,
        source_sample_rate_hz=44100,
        recorded_on="2024-01-15T10:00:01+00:00",
        recorded_on_basis="parent_tag_plus_source_offset",
        recorded_on_method="sample_offset",
        recorded_on_confidence="high",
        timezone_status="explicit",
        derived_at="2025-01-01T00:00:00+00:00",
        manifest_sha256=hashlib.sha256(b"manifest").hexdigest(),
        policy_version="policy-1",
        detector_run_id="run-1",
        encoder_settings={"codec": "aac", "bitrate": 64000},
    )


@pytest.fixture
def synthetic_m4a(tmp_path: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg unavailable")
    path = tmp_path / "segment.m4a"
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        pytest.skip(f"ffmpeg cannot generate fixture: {result.stderr}")
    return path


def test_mp4_provenance_roundtrip_and_unrelated_tags(synthetic_m4a: Path):
    path = synthetic_m4a
    media = MP4(path)
    media.add_tags() if media.tags is None else None
    assert media.tags is not None
    media.tags["©nam"] = ["keep this title"]
    media.save()
    expected = _provenance()
    write_segment_provenance(path, expected)
    assert read_segment_provenance(path) == expected
    reread = MP4(path)
    assert reread.tags is not None
    assert reread.tags["©nam"] == ["keep this title"]
    assert "----:org.gowithitroger.conversation-corpus:parent_asset_id" in reread.tags
    original_size = path.stat().st_size
    write_segment_provenance(path, expected)
    assert read_segment_provenance(path) == expected
    assert path.stat().st_size == original_size


def test_source_store_ids_roundtrip_and_pairwise_validation(synthetic_m4a: Path):
    expected = replace(_provenance(), source_scan_run_id=4, source_object_id=29)
    write_segment_provenance(synthetic_m4a, expected)
    assert read_segment_provenance(synthetic_m4a) == expected
    with pytest.raises(ValueError):
        replace(_provenance(), source_scan_run_id=4)
    with pytest.raises(ValueError):
        replace(_provenance(), source_object_id=-1, source_scan_run_id=4)


def test_write_rejects_non_mp4_without_mutating(tmp_path: Path):
    path = tmp_path / "not.wav"
    path.write_bytes(b"not an mp4")
    original = path.read_bytes()
    with pytest.raises(ValueError):
        write_segment_provenance(path, _provenance())
    assert path.read_bytes() == original


def test_failed_write_removes_sibling_temp_and_preserves_source(
    synthetic_m4a: Path, monkeypatch: pytest.MonkeyPatch
):
    import media_meta.provenance as provenance_module

    path = synthetic_m4a
    original = path.read_bytes()

    def fail_write(*args, **kwargs):
        raise ValueError("synthetic write failure")

    monkeypatch.setattr(provenance_module, "_write_tags", fail_write)
    with pytest.raises(ValueError, match="synthetic write failure"):
        write_segment_provenance(path, _provenance())
    assert path.read_bytes() == original
    assert list(path.parent.glob(f".{path.stem}.*{path.suffix}")) == []


def test_target_replacement_during_write_is_not_overwritten(
    synthetic_m4a: Path, monkeypatch: pytest.MonkeyPatch
):
    import media_meta.provenance as provenance_module

    path = synthetic_m4a
    replacement = path.with_name("newer-target.m4a")
    shutil.copy2(path, replacement)
    newer_bytes = replacement.read_bytes()
    original_write = provenance_module._write_tags

    def racing_write(temp_path, provenance):
        original_write(temp_path, provenance)
        os.replace(replacement, path)

    monkeypatch.setattr(provenance_module, "_write_tags", racing_write)
    with pytest.raises(ValueError, match="target changed"):
        write_segment_provenance(path, _provenance())
    assert path.read_bytes() == newer_bytes
    assert list(path.parent.glob(f".{path.stem}.*{path.suffix}")) == []


def test_provenance_validation():
    with pytest.raises(ValueError):
        SegmentProvenance(
            **{
                **_provenance().to_dict(),
                "parent_sha256": "bad",
            }
        )


def test_unknown_recording_time_removes_day_tags_and_roundtrips(synthetic_m4a: Path):
    path = synthetic_m4a
    media = MP4(path)
    media.add_tags() if media.tags is None else None
    assert media.tags is not None
    media.tags["©day"] = ["unrelated-existing-date"]
    media.save()
    unknown = replace(
        _provenance(),
        parent_sha256=None,
        recorded_on=None,
        recorded_on_basis="unknown",
        recorded_on_method="unknown",
        recorded_on_confidence="unknown",
        timezone_status="unknown",
    )
    write_segment_provenance(path, unknown)
    assert read_segment_provenance(path) == unknown
    reread = MP4(path)
    assert reread.tags is not None
    assert "©day" not in reread.tags
    assert "----:org.gowithitroger.conversation-corpus:recorded_on" not in reread.tags


@pytest.mark.parametrize(
    "changes",
    [
        {"parent_duration_samples": 0},
        {"source_end_sample": 441001, "parent_duration_samples": 441000},
        {"source_sample_rate_hz": float("inf")},
        {"source_sample_rate_hz": float("nan")},
    ],
)
def test_provenance_rejects_invalid_ranges_and_rate(changes):
    with pytest.raises(ValueError):
        replace(_provenance(), **changes)
