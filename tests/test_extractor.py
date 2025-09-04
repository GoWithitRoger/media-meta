# media-meta/tests/test_extractor.py

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from media_meta.extractor import _parse_tag_date, extract_metadata


def test_extract_metadata_file_not_found():
    """Verify it raises an error for a non-existent file."""
    with pytest.raises(FileNotFoundError):
        extract_metadata("non_existent_file.wav")


def test_fallback_to_filesystem_date(tmp_path: Path):
    """Verify it uses filesystem time when no tags are present."""
    fake_file = tmp_path / "test.wav"
    fake_file.touch()

    metadata = extract_metadata(fake_file)

    assert metadata["recorded_on_source"] == "filesystem_fallback"
    assert "recorded_on" in metadata
    assert metadata["filename"] == "test.wav"


@pytest.mark.parametrize(
    "input_str, expected_iso",
    [
        ("2024-09-04T10:30:00", "2024-09-04T10:30:00+00:00"),
        ("2023-01-15", "2023-01-15T00:00:00+00:00"),
        ("2022", "2022-01-01T00:00:00+00:00"),
    ],
)
def test_parse_tag_date(input_str, expected_iso):
    """Verify date strings are parsed correctly into ISO 8601 format."""
    assert _parse_tag_date(input_str) == expected_iso


def test_parse_tag_date_invalid():
    """Verify invalid date strings return None."""
    assert _parse_tag_date("this is not a date string") is None


def test_extract_metadata_from_tags(tmp_path: Path):
    """Verify it correctly extracts a date from a prioritized tag (TDRC)."""
    # 1. Create a fake file
    fake_audio_file = tmp_path / "test.mp3"
    fake_audio_file.touch()

    # 2. Create a mock object that simulates a MutagenFile instance
    mock_file = MagicMock()
    mock_file.info.length = 120.5
    mock_file.info.sample_rate = 44100
    mock_file.info.channels = 2
    mock_file.info.bitrate = 128000
    mock_file.__class__.__name__ = "MP3"
    mock_file.tags = {
        "TIT2": "Test Title",
        "TDRC": "2023-05-10T14:22:00",  # The date tag we want to find
    }

    # 3. Use patch to make MutagenFile return your mock object
    with patch("media_meta.extractor.MutagenFile", return_value=mock_file):
        metadata = extract_metadata(fake_audio_file)

    # 4. Assert the results
    assert metadata["recorded_on_source"] == "tag"
    assert metadata["recorded_on"] == "2023-05-10T14:22:00+00:00"
    assert metadata["duration_seconds"] == 120.5
    assert metadata["format"] == "MP3"
