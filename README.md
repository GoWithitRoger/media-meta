# Media Meta

A small Python utility for extracting technical metadata and a best-effort recording date from media
files. It uses [Mutagen](https://mutagen.readthedocs.io/) for embedded tags and falls back to the
filesystem date when no usable recording-date tag is present.

This is a hobby project maintained on a best-effort basis. Media metadata varies widely between
formats and recording tools, so callers should inspect `recorded_on_source` instead of assuming every
date came from an embedded tag.

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

```python
from media_meta import extract_metadata

metadata = extract_metadata("/path/to/audio.wav")
print(metadata["recorded_on"])
print(metadata["recorded_on_source"])
```

The result also includes the resolved path, filename, file size, modification time, and available
duration, sample-rate, channel, bitrate, and format information.

## Development

```bash
uv run ruff check .
uv run ty check
uv run pytest
```

## License

MIT. See [LICENSE](LICENSE).
