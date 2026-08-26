# Media Meta

`media-meta` extracts technical metadata and embedded recording-date evidence from media files
using [Mutagen](https://mutagen.readthedocs.io/). Date observations retain their source tag,
raw value, precision, and timezone semantics.

Embedded dates are evidence, not automatically authoritative. If no embedded date is parseable,
`recorded_on` is `None` and one low-confidence filesystem timestamp is exposed separately as
`filesystem_time_candidate`.

## Install

Install the command-line tool with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/GoWithitRoger/media-meta.git
```

To add the library to a uv-managed project:

```bash
uv add git+https://github.com/GoWithitRoger/media-meta.git
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
print(metadata["duration_seconds"])
```

For MP4/M4A files, the package can read and embed caller-supplied `SegmentProvenance`; it validates
the values but does not calculate recording times or infer source ranges. Provenance uses MP4
freeform atoms because modern `mdta` mappings are not supported by the current Mutagen integration.
Remuxing may strip these tags, so write them after the final remux.

### Command line

```bash
media-meta /path/to/audio.wav
```

The command prints the extracted metadata as JSON.

## Development

```bash
uv run ruff check .
uv run ty check
uv run pytest
```

## License

MIT. See [LICENSE](LICENSE).
