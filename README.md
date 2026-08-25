# Media Meta

A small Python utility for extracting technical metadata and embedded recording-date evidence from
media files. It reads tags with [Mutagen](https://mutagen.readthedocs.io/). Date observations retain
their source tag, raw value, precision, and timezone semantics; the library never turns a naive or
date-only value into a made-up UTC timestamp.

When there is no parseable embedded recording date, `extract_metadata` leaves
`recorded_on` as `None` and returns a low-confidence
`filesystem_time_candidate` separately. Filesystem birth/modified times are
not archival recording dates.

This is a hobby utility. Media metadata varies widely between formats and recording tools, so callers
should inspect the returned date evidence rather than assume that every date is authoritative.

## Install

From GitHub:

```bash
python -m pip install git+https://github.com/GoWithitRoger/media-meta.git
```

For development:

```bash
git clone https://github.com/GoWithitRoger/media-meta.git
cd media-meta
uv sync --all-extras --locked
```

## Usage

### Python

```python
from media_meta import extract_metadata

metadata = extract_metadata("/path/to/audio.wav")
print(metadata["recorded_on"])
print(metadata["recorded_on_source"])
```

For derived MP4/M4A segments, `SegmentProvenance` validates and
`write_segment_provenance` embeds caller-supplied parent identity, source
sample ranges, recording-date evidence, and transform details. The class
does not calculate `recorded_on`; a caller must supply that value when the
approved workflow has enough evidence to calculate it. A supplied
`recorded_on` is mirrored to the standard `©day` tag. The provenance fields
are stored in namespaced MP4 freeform tags. Writes use a sibling temporary
file and an atomic replacement; the source is not modified when validation or
writing fails.

The current Mutagen path does not support modern MP4 `mdta` key mappings, so
provenance uses freeform atoms. Remuxing (including with FFmpeg) may strip
freeform metadata. Write provenance after the final remux and retain the
authoritative provenance manifest alongside the media.

This utility does not authorize chopping, silence removal, compaction, or
other source transformations. Its writer is for files that have already been
created as derivatives by an explicitly approved corpus workflow. Originals
remain subject to the corpus preservation and retention policy.

```python
from media_meta import SegmentProvenance, write_segment_provenance

write_segment_provenance("segment.m4a", SegmentProvenance(
    parent_asset_id="asset-123",
    parent_stable_identity="conversation-corpus:asset-123",
    parent_filename="original.m4a",
    parent_sha256="0" * 64,
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
    manifest_sha256="1" * 64,
))
```

### Command line

This package also installs a command-line utility. You can use it to get a JSON output of a file's metadata directly from your terminal.

**Command:**

```bash
media-meta /path/to/audio.wav
```

**Illustrative Output:**

The JSON below shows the shape of a successful result; paths, timestamps,
technical values, and date observations vary by input file. When there is no
parseable embedded date, `recorded_on` is `null` and the separate
low-confidence filesystem candidate is populated.

```json
{
    "filepath": "/path/to/audio.wav",
    "filename": "audio.wav",
    "file_size_bytes": 4501234,
    "file_modified_on": "2025-09-04T18:30:00+00:00",
    "recorded_on": "2024-01-15T10:00:00+00:00",
    "recorded_on_source": "tag",
    "recorded_on_observation": {
        "tag_key": "©day",
        "raw_value": "2024-01-15T10:00:00+00:00",
        "normalized_value": "2024-01-15T10:00:00+00:00",
        "timezone_status": "explicit",
        "date_precision": "second",
        "confidence": "high"
    },
    "date_observations": [
        {
            "tag_key": "©day",
            "raw_value": "2024-01-15T10:00:00+00:00",
            "normalized_value": "2024-01-15T10:00:00+00:00",
            "timezone_status": "explicit",
            "date_precision": "second",
            "confidence": "high"
        }
    ],
    "filesystem_time_candidate": null,
    "duration_seconds": 30.1,
    "sample_rate_hz": 44100,
    "channels": 2,
    "bitrate_bps": 1411200,
    "format": "WAVE"
}
```

## Development

```bash
uv run ruff check .
uv run ty check
uv run pytest
```

## License

MIT. See [LICENSE](LICENSE).
