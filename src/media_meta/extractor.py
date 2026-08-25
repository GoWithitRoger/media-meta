"""Extract technical metadata and preservation-safe recording-date observations."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen import FileType, MutagenError

from .dates import DateObservation, parse_date_observation

__all__ = ["extract_metadata"]

_DATE_TAGS = ["TDRC", "©day", "TDOR", "TDRL", "DATE", "TYER", "TDAT"]


def _parse_tag_date(date_string: str) -> str | None:
    """Backward-compatible normalized-value helper.

    New callers should use :func:`parse_date_observation` to retain precision
    and provenance details.
    """

    observation = parse_date_observation("unknown", date_string)
    return observation.normalized_value


def _tag_values(value: object) -> list[object]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _date_observations(media_file: FileType | None) -> list[DateObservation]:
    if not media_file or not media_file.tags:
        return []
    observations: list[DateObservation] = []
    for tag in _DATE_TAGS:
        try:
            if tag in media_file.tags:
                for value in _tag_values(media_file.tags[tag]):
                    observations.append(parse_date_observation(tag, value))
        except (KeyError, IndexError, TypeError):
            continue
    return observations


def _get_recorded_on(media_file: FileType | None) -> DateObservation | None:
    """Return the first parseable date according to tag priority."""

    return next((obs for obs in _date_observations(media_file) if obs.parseable), None)


def extract_metadata(filepath: str | Path) -> dict[str, Any]:
    """Extract technical metadata and embedded date observations.

    Filesystem timestamps are exposed only as an explicitly labeled candidate;
    they are never promoted to the authoritative ``recorded_on`` value.
    """

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {path}")

    stat = path.stat()
    metadata: dict[str, Any] = {
        "filepath": str(path.resolve()),
        "filename": path.name,
        "file_size_bytes": stat.st_size,
        "file_modified_on": datetime.datetime.fromtimestamp(
            stat.st_mtime, tz=datetime.timezone.utc
        ).isoformat(),
        "recorded_on": None,
        "recorded_on_source": "none",
        "recorded_on_observation": None,
        "date_observations": [],
        "filesystem_time_candidate": None,
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
            observations = _date_observations(media_file)
            metadata["date_observations"] = [obs.to_dict() for obs in observations]
            selected = next((obs for obs in observations if obs.parseable), None)
            if selected is not None:
                metadata["recorded_on"] = selected.normalized_value
                metadata["recorded_on_source"] = "tag"
                metadata["recorded_on_observation"] = selected.to_dict()
    except MutagenError as exc:
        metadata["error"] = f"Could not process file with mutagen: {exc}"
    except Exception as exc:
        metadata["error"] = f"An unexpected error occurred: {exc}"

    if metadata["recorded_on"] is None:
        try:
            timestamp = stat.st_birthtime
            method = "filesystem_birthtime"
        except AttributeError:
            timestamp = stat.st_mtime
            method = "filesystem_mtime"
        normalized = datetime.datetime.fromtimestamp(
            timestamp, tz=datetime.timezone.utc
        ).isoformat()
        metadata["filesystem_time_candidate"] = {
            "raw_value": str(timestamp),
            "normalized_value": normalized,
            "method": method,
            "confidence": "low",
        }
    return metadata
