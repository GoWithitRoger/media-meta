import pytest

from media_meta import DateObservation, offset_date_observation, parse_date_observation


@pytest.mark.parametrize(
    ("value", "normalized", "precision", "timezone"),
    [
        ("2024-09-04T10:30:00-05:00", "2024-09-04T10:30:00-05:00", "second", "explicit"),
        ("2024-09-04T10:30+05:30", "2024-09-04T10:30:00+05:30", "minute", "explicit"),
        ("2024-09-04T10:30", "2024-09-04T10:30:00", "minute", "naive"),
        ("2024-09-04", "2024-09-04", "day", "unknown"),
        ("2024", "2024", "year", "unknown"),
    ],
)
def test_parse_date_observation_preserves_semantics(value, normalized, precision, timezone):
    observation = parse_date_observation("©day", value)
    assert observation.normalized_value == normalized
    assert observation.date_precision == precision
    assert observation.timezone_status == timezone
    assert observation.raw_value == value


def test_invalid_observation_is_retained():
    observation = parse_date_observation("TDRC", "not a date")
    assert observation == DateObservation(
        "TDRC", "not a date", None, "invalid", "unknown", "invalid"
    )


def test_offset_retains_explicit_timezone():
    observation = parse_date_observation("©day", "2024-01-01T00:00:00+05:30")
    shifted = offset_date_observation(observation, 44100, 44100)
    assert shifted.normalized_value == "2024-01-01T00:00:01+05:30"
    assert shifted.timezone_status == "explicit"


@pytest.mark.parametrize("value", ["2024", "2024-01-01", "2024-01"])
def test_offset_rejects_coarse_dates(value):
    with pytest.raises(ValueError):
        offset_date_observation(parse_date_observation("©day", value), 1, 44100)


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf")])
def test_offset_rejects_invalid_rates(rate):
    observation = parse_date_observation("©day", "2024-01-01T00:00:00")
    with pytest.raises(ValueError):
        offset_date_observation(observation, 1, rate)
