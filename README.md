# Media Meta

A simple utility to extract technical and embedded metadata from media files, especially the true "recorded on" date.

## Installation
Install the library using **uv**:

```bash
uv pip install git+[https://github.com/GoWithitRoger/media-meta.git](https://github.com/GoWithitRoger/media-meta.git)
```

> **Note:** If you use `pip`, the equivalent command is: `pip install git+https://github.com/GoWithitRoger/media-meta.git`

## Usage
Python
    
```python
from media_meta import extract_metadata

metadata = extract_metadata("/path/to/your/audio.wav")
print(metadata)
```
    

## Contributing & Development Setup
Interested in contributing? Follow these steps to set up a development environment.

1. **Clone the repository:**

```bash
git clone [https://github.com/GoWithitRoger/media-meta.git](https://github.com/GoWithitRoger/media-meta.git)
cd media-meta
```
    

2. **Install dependencies:** This will install the library in editable mode along with all development tools (`ruff`, `pytest`, etc.).

    - **With `uv` (Recommended):**

```bash   
uv sync --all-extras
```   

    - **With `pip`:**

```bash
pip install -e .[dev]
```   

3. **Run tests:** After setting up the environment, you can run the test suite to verify everything is working correctly.

```bash
uv run pytest
```