"""Embedded provenance for derived MP4/M4A audio segments."""

from __future__ import annotations

import datetime as _datetime
import json
import math
import os
import re
import shutil
import stat
import tempfile
from dataclasses import MISSING, dataclass, fields
from pathlib import Path
from typing import Any, Mapping

from mutagen import MutagenError
from mutagen.mp4 import MP4, MP4FreeForm

__all__ = [
    "COORDINATE_SPACE",
    "DERIVATIVE_KIND",
    "PROVENANCE_NAMESPACE",
    "PROVENANCE_SCHEMA_VERSION",
    "SOURCE_TIMELINE_ORIGIN",
    "SegmentProvenance",
    "read_segment_provenance",
    "write_segment_provenance",
]

PROVENANCE_NAMESPACE = "----:org.gowithitroger.conversation-corpus:"
PROVENANCE_SCHEMA_VERSION = "1"
DERIVATIVE_KIND = "salient_audio_segment"
COORDINATE_SPACE = "source_audio"
SOURCE_TIMELINE_ORIGIN = "decoded_audio_start"
_MP4_SUFFIXES = {".mp4", ".m4a", ".m4b", ".m4v", ".m4p"}
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True, slots=True)
class SegmentProvenance:
    """Validated lineage and timing for one derived audio segment."""

    parent_asset_id: str
    parent_stable_identity: str
    parent_filename: str
    parent_sha256: str | None
    parent_size_bytes: int
    parent_duration_samples: int
    parent_codec: str
    segment_id: str
    source_start_sample: int
    source_end_sample: int
    source_sample_rate_hz: int | float
    recorded_on_basis: str
    recorded_on_method: str
    recorded_on_confidence: str
    timezone_status: str
    derived_at: str
    manifest_sha256: str
    recorded_on: str | None = None
    source_scan_run_id: int | None = None
    source_object_id: int | None = None
    policy_version: str | None = None
    detector_run_id: str | None = None
    encoder_settings: str | Mapping[str, Any] | None = None
    schema_version: str = PROVENANCE_SCHEMA_VERSION
    kind: str = DERIVATIVE_KIND
    derived: bool = True
    coordinate_space: str = COORDINATE_SPACE
    source_timeline_origin: str = SOURCE_TIMELINE_ORIGIN

    def __post_init__(self) -> None:
        text_fields = (
            "parent_asset_id",
            "parent_stable_identity",
            "parent_filename",
            "parent_codec",
            "segment_id",
            "recorded_on_basis",
            "recorded_on_method",
            "recorded_on_confidence",
            "timezone_status",
        )
        for name in text_fields:
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be a non-empty string")
        for name in (
            "parent_size_bytes",
            "parent_duration_samples",
            "source_start_sample",
            "source_end_sample",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in ("source_scan_run_id", "source_object_id"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if (self.source_scan_run_id is None) != (self.source_object_id is None):
            raise ValueError("source_scan_run_id and source_object_id must be provided together")
        if self.source_end_sample <= self.source_start_sample:
            raise ValueError("source_end_sample must be greater than source_start_sample")
        if isinstance(self.source_sample_rate_hz, bool) or not isinstance(
            self.source_sample_rate_hz, (int, float)
        ) or not math.isfinite(float(self.source_sample_rate_hz)) or (
            self.source_sample_rate_hz <= 0
        ):
            raise ValueError("source_sample_rate_hz must be positive")
        if self.parent_duration_samples <= 0:
            raise ValueError("parent_duration_samples must be positive")
        if self.source_end_sample > self.parent_duration_samples:
            raise ValueError("source_end_sample cannot exceed parent_duration_samples")
        for name in ("parent_sha256", "manifest_sha256"):
            value = getattr(self, name)
            if value is None and name == "parent_sha256":
                continue
            if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
                raise ValueError(f"{name} must be a SHA-256 hexadecimal digest")
            object.__setattr__(self, name, value.lower())
        if self.schema_version != PROVENANCE_SCHEMA_VERSION:
            raise ValueError(f"unsupported provenance schema version: {self.schema_version}")
        if self.kind != DERIVATIVE_KIND:
            raise ValueError(f"unsupported provenance kind: {self.kind}")
        if self.derived is not True:
            raise ValueError("derived must be true for segment provenance")
        if self.coordinate_space != COORDINATE_SPACE:
            raise ValueError(f"coordinate_space must be {COORDINATE_SPACE!r}")
        if self.source_timeline_origin != SOURCE_TIMELINE_ORIGIN:
            raise ValueError(f"source_timeline_origin must be {SOURCE_TIMELINE_ORIGIN!r}")
        if self.recorded_on is not None and "T" not in self.recorded_on:
            raise ValueError("recorded_on must be an ISO-8601 datetime or None")
        for name in ("recorded_on", "derived_at"):
            value = getattr(self, name)
            if value is None and name == "recorded_on":
                continue
            if not isinstance(value, str) or "T" not in value:
                raise ValueError(f"{name} must be an ISO-8601 datetime")
            try:
                _datetime.datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be an ISO-8601 datetime") from exc

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical metadata field mapping."""

        return {field.name: getattr(self, field.name) for field in fields(self)}


def _target(path: str | Path) -> Path:
    target = Path(path)
    if target.is_symlink():
        raise ValueError("refusing to mutate a symlink")
    if not target.exists():
        raise FileNotFoundError(target)
    if not target.is_file():
        raise ValueError("segment provenance requires a regular file")
    if target.suffix.lower() not in _MP4_SUFFIXES:
        raise ValueError("segment provenance is supported only for MP4/M4A files")
    return target


def _target_state(path: Path) -> tuple[int, int, int, int, int]:
    """Return identity and mutation indicators for a regular target file."""

    try:
        state = path.lstat()
    except OSError as exc:
        raise ValueError("target disappeared while writing provenance") from exc
    if stat.S_ISLNK(state.st_mode) or not stat.S_ISREG(state.st_mode):
        raise ValueError("target changed to a non-regular file while writing provenance")
    return (
        state.st_dev,
        state.st_ino,
        state.st_size,
        state.st_mtime_ns,
        state.st_ctime_ns,
    )


def _as_text(value: object) -> str:
    if isinstance(value, MP4FreeForm):
        return bytes(value).decode("utf-8", errors="strict")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="strict")
    if isinstance(value, (list, tuple)):
        return _as_text(value[0]) if value else ""
    return str(value)


def _key(name: str) -> str:
    return f"{PROVENANCE_NAMESPACE}{name}"


def _read_tags(path: Path) -> dict[str, str]:
    try:
        media = MP4(path)
    except (MutagenError, OSError) as exc:
        raise ValueError(f"could not read MP4/M4A metadata: {exc}") from exc
    if not media.tags:
        return {}
    values: dict[str, str] = {}
    for field in fields(SegmentProvenance):
        key = _key(field.name)
        if key in media.tags:
            values[field.name] = _as_text(media.tags[key])
    return values


def read_segment_provenance(filepath: str | Path) -> SegmentProvenance | None:
    """Read embedded segment provenance, returning ``None`` for ordinary media."""

    path = _target(filepath)
    values = _read_tags(path)
    if not values or values.get("derived", "").lower() != "true":
        return None
    # Required fields are the fields without dataclass defaults.
    missing = [
        field.name
        for field in fields(SegmentProvenance)
        if (
            field.default is MISSING
            and field.default_factory is MISSING
            and field.name not in {"parent_sha256", "recorded_on"}
            and field.name not in values
        )
    ]
    if missing:
        raise ValueError(f"incomplete segment provenance; missing: {', '.join(missing)}")
    converted: dict[str, Any] = dict(values)
    for name in (
        "parent_size_bytes",
        "parent_duration_samples",
        "source_start_sample",
        "source_end_sample",
    ):
        converted[name] = int(values[name])
    for name in ("source_scan_run_id", "source_object_id"):
        if name in values:
            converted[name] = int(values[name])
    converted["source_sample_rate_hz"] = (
        float(values["source_sample_rate_hz"])
        if any(char in values["source_sample_rate_hz"] for char in ".eE")
        else int(values["source_sample_rate_hz"])
    )
    converted["derived"] = values["derived"].lower() == "true"
    converted["parent_sha256"] = values.get("parent_sha256") or None
    converted["recorded_on"] = values.get("recorded_on") or None
    for name in ("policy_version", "detector_run_id", "encoder_settings"):
        if name not in converted:
            converted[name] = None
    if isinstance(converted["encoder_settings"], str):
        try:
            decoded = json.loads(converted["encoder_settings"])
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(decoded, Mapping):
                converted["encoder_settings"] = decoded
    return SegmentProvenance(**converted)  # type: ignore[call-arg]


def _serialize(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Mapping):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _write_tags(path: Path, provenance: SegmentProvenance) -> None:
    try:
        media = MP4(path)
        if media.tags is None:
            media.add_tags()
        assert media.tags is not None
        if provenance.recorded_on is None:
            media.tags.pop("©day", None)
            media.tags.pop(_key("recorded_on"), None)
        else:
            media.tags["©day"] = [provenance.recorded_on]
        for field in fields(provenance):
            value = getattr(provenance, field.name)
            if value is None:
                # Remove stale optional values so replacement is idempotent.
                media.tags.pop(_key(field.name), None)
                continue
            media.tags[_key(field.name)] = [MP4FreeForm(_serialize(value).encode("utf-8"))]
        media.save()
    except (MutagenError, OSError) as exc:
        raise ValueError(f"could not write MP4/M4A metadata: {exc}") from exc


def write_segment_provenance(
    filepath: str | Path,
    provenance: SegmentProvenance,
) -> Path:
    """Atomically write provenance to an MP4/M4A sibling temporary copy."""

    if not isinstance(provenance, SegmentProvenance):
        raise TypeError("provenance must be a SegmentProvenance")
    source = _target(filepath)
    source_state = _target_state(source)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{source.stem}.", suffix=source.suffix, dir=str(source.parent)
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        _write_tags(temporary, provenance)
        # Ensure the fully-mutated temporary file is durable before replace.
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        written = read_segment_provenance(temporary)
        if written != provenance:
            raise ValueError("written segment provenance failed verification")
        if _target_state(source) != source_state:
            raise ValueError("target changed while writing provenance")
        os.replace(temporary, source)
        try:
            directory_fd = os.open(source.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # The file itself was durably fsynced; some filesystems disallow
            # opening directories, so directory durability is best effort.
            pass
        return source
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
