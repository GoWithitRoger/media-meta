# media-meta/src/media_meta/__init__.py

"""A utility to extract technical and embedded metadata from media files."""

__version__ = "0.1.0"

from .extractor import extract_metadata

__all__ = ["extract_metadata"]
