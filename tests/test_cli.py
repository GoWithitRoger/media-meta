# tests/test_cli.py

import json
from typing import cast
from unittest.mock import patch

import pytest

from media_meta.cli import main


@patch("sys.argv", ["media-meta", "tests/fixtures/sample.mp3"])
@patch("media_meta.cli.extract_metadata")
def test_cli_success(mock_extract_metadata, capsys):
    """Verify the CLI runs successfully and prints JSON output."""
    # 1. Setup a fake return value for the core extractor function.
    # We are testing the CLI's ability to format and print, not the extractor itself.
    fake_metadata = {
        "filename": "sample.mp3",
        "recorded_on": "2024-01-01T00:00:00+00:00",
        "recorded_on_source": "tag",
    }
    mock_extract_metadata.return_value = fake_metadata

    # 2. Run the CLI's main function, expecting it to exit cleanly.
    with pytest.raises(SystemExit) as e:
        main()

    # 3. Assert that the exit code is 0 (success).
    exit_exc = cast(SystemExit, e.value)
    assert exit_exc.code == 0

    # 4. Assert that the correct JSON was printed to standard output.
    captured = capsys.readouterr()
    assert captured.err == ""
    # Parse the captured stdout to compare dictionaries, which is more robust
    # than comparing raw strings.
    output_data = json.loads(captured.out)
    assert output_data == fake_metadata


@patch("sys.argv", ["media-meta", "non_existent_file.wav"])
def test_cli_file_not_found(capsys):
    """Verify the CLI prints an error and exits with code 1 for a missing file."""
    # 1. Run the CLI's main function, expecting it to exit with an error.
    with pytest.raises(SystemExit) as e:
        main()

    # 2. Assert that the exit code is 1 (error).
    exit_exc = cast(SystemExit, e.value)
    assert exit_exc.code == 1

    # 3. Assert that the correct error message was printed to standard error.
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error: Media file not found" in captured.err
    assert "non_existent_file.wav" in captured.err
