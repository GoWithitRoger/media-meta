# media-meta/src/media_meta/__init__.py

"""Extract and preserve metadata from media files."""

__version__ = "0.2.0"

from .dates import (
    DateObservation,
    offset_date_observation,
    offset_observation,
    parse_date_observation,
)
from .extractor import extract_metadata
from .provenance import (
    COORDINATE_SPACE,
    DERIVATIVE_KIND,
    PROVENANCE_NAMESPACE,
    PROVENANCE_SCHEMA_VERSION,
    SOURCE_TIMELINE_ORIGIN,
    SegmentProvenance,
    read_segment_provenance,
    write_segment_provenance,
)

__all__ = [
    "COORDINATE_SPACE",
    "DERIVATIVE_KIND",
    "DateObservation",
    "PROVENANCE_NAMESPACE",
    "PROVENANCE_SCHEMA_VERSION",
    "SegmentProvenance",
    "SOURCE_TIMELINE_ORIGIN",
    "extract_metadata",
    "offset_date_observation",
    "offset_observation",
    "parse_date_observation",
    "read_segment_provenance",
    "write_segment_provenance",
]
