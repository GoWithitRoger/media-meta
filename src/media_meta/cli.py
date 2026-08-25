# src/media_meta/cli.py

import argparse
import json
import sys
from pathlib import Path

from .extractor import extract_metadata


def main():
    """The main entry point for the media-meta command-line interface."""
    parser = argparse.ArgumentParser(
        description="Extract technical and embedded metadata from a media file."
    )
    parser.add_argument(
        "filepath",
        type=Path,
        help="The path to the media file.",
    )
    args = parser.parse_args()

    try:
        metadata = extract_metadata(args.filepath)
        # Pretty-print the JSON output
        print(json.dumps(metadata, indent=4))
        sys.exit(0)
    except FileNotFoundError:
        print(f"Error: Media file not found: {args.filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
