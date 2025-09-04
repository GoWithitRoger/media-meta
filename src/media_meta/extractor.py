# media-meta/src/media_meta/extractor.py

import datetime
from pathlib import Path
from typing import Any

from dateutil.parser import parse as parse_datetime
from mutagen import File as MutagenFile
from mutagen import FileType, MutagenError

__all__ = ["extract_metadata"]

# A comprehensive list of tags used for the recording date.
_DATE_TAGS = [
    "TDRC",
    "\xa9day",
    "TDOR",
    "TDRL",
    "DATE",
    "TYER",
    "TDAT",
]


def _parse_tag_date(date_string: str) -> str | None:
    """Tries to parse a date string into a timezone-aware ISO 8601 format."""
    try:
        # The 'ignoretz=True' flag is crucial. Many tags lack timezone info,
        # so we parse them as naive and then correctly assign UTC.
        # Use a default date of 1-1-1 for missing components (day, month)
        default_date = datetime.datetime(1, 1, 1)
        dt_object: datetime.datetime
        dt_object = parse_datetime(date_string, ignoretz=True, default=default_date)
        return dt_object.replace(tzinfo=datetime.timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _get_recorded_on(media_file: FileType | None) -> str | None:
    """Intelligently extracts and standardizes the recording date from metadata tags."""
    if not media_file or not media_file.tags:
        return None

    for tag in _DATE_TAGS:
        try:
            if tag in media_file.tags:
                value: Any = media_file.tags[tag]
                raw_value = str(value[0] if isinstance(value, list) else value)
                parsed_date = _parse_tag_date(raw_value.strip())
                if parsed_date:
                    return parsed_date
        except (KeyError, IndexError):
            continue
    return None


def extract_metadata(filepath: str | Path) -> dict[str, Any]:
    """Extracts key technical and descriptive metadata from a media file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {path}")

    metadata: dict[str, Any] = {
        "filepath": str(path.resolve()),
        "filename": path.name,
        "file_size_bytes": path.stat().st_size,
        "file_modified_on": datetime.datetime.fromtimestamp(
            path.stat().st_mtime, tz=datetime.timezone.utc
        ).isoformat(),
        "recorded_on": None,
        "recorded_on_source": "none",
    }

    try:
        media_file = MutagenFile(path, easy=False)

        if media_file:
            info = media_file.info
            metadata.update(
                {
                    "duration_seconds": info.length,
                    "sample_rate_hz": info.sample_rate,
                    "channels": info.channels,
                    "bitrate_bps": getattr(info, "bitrate", 0),
                    "format": media_file.__class__.__name__,
                }
            )

            recorded_on_date = _get_recorded_on(media_file)
            if recorded_on_date:
                metadata["recorded_on"] = recorded_on_date
                metadata["recorded_on_source"] = "tag"

    except MutagenError as e:
        metadata["error"] = f"Could not process file with mutagen: {e}"
    except Exception as e:
        metadata["error"] = f"An unexpected error occurred: {e}"

    if not metadata["recorded_on"]:
        try:
            ts = path.stat().st_birthtime
        except AttributeError:
            ts = path.stat().st_mtime

        metadata["recorded_on"] = datetime.datetime.fromtimestamp(
            ts, tz=datetime.timezone.utc
        ).isoformat()
        metadata["recorded_on_source"] = "filesystem_fallback"

    return metadata
