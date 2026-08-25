"""Lossless-ish observations of dates found in media metadata.

Media applications commonly write dates without a timezone, and some write
only a year or a calendar date.  Treating all of these as UTC datetimes is a
particularly dangerous form of data loss, so this module keeps the original
tag and its precision alongside any normalized value.
"""

from __future__ import annotations

import datetime as _datetime
import math
import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from dateutil.parser import isoparse

__all__ = [
    "DateObservation",
    "offset_date_observation",
    "offset_observation",
    "parse_date_observation",
]

_YEAR_RE = re.compile(r"^(?P<year>\d{4})$")
_MONTH_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")
_DAY_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")
_TIME_RE = re.compile(r"[T ]\d{2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?")


@dataclass(frozen=True, slots=True)
class DateObservation:
    """One date value as observed in a media tag.

    ``normalized_value`` is an ISO-8601 value only when the source is
    parseable.  A naive datetime remains naive.  ``timezone_status`` is one
    of ``explicit``, ``naive``, ``unknown`` (date-only values), or ``invalid``.
    ``date_precision`` is ``year``, ``month``, ``day``, ``minute``,
    ``second``, or ``unknown``.
    """

    tag_key: str
    raw_value: str
    normalized_value: str | None
    timezone_status: str
    date_precision: str
    confidence: str

    @property
    def parseable(self) -> bool:
        """Whether this observation yielded a normalized value."""

        return self.normalized_value is not None

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable representation."""

        return {
            "tag_key": self.tag_key,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "timezone_status": self.timezone_status,
            "date_precision": self.date_precision,
            "confidence": self.confidence,
        }


def _invalid(tag_key: str, raw_value: str) -> DateObservation:
    return DateObservation(
        tag_key=tag_key,
        raw_value=raw_value,
        normalized_value=None,
        timezone_status="invalid",
        date_precision="unknown",
        confidence="invalid",
    )


def parse_date_observation(tag_key: str, value: object) -> DateObservation:
    """Parse a tag value without inventing timezone or date components."""

    if isinstance(value, bytes):
        raw_value = value.decode("utf-8", errors="replace")
    else:
        raw_value = str(value)
    raw_value = raw_value.strip()
    if not raw_value:
        return _invalid(tag_key, raw_value)

    if _YEAR_RE.fullmatch(raw_value):
        return DateObservation(tag_key, raw_value, raw_value, "unknown", "year", "low")
    if _MONTH_RE.fullmatch(raw_value):
        try:
            _datetime.date.fromisoformat(f"{raw_value}-01")
        except ValueError:
            return _invalid(tag_key, raw_value)
        return DateObservation(tag_key, raw_value, raw_value, "unknown", "month", "low")
    if _DAY_RE.fullmatch(raw_value):
        try:
            _datetime.date.fromisoformat(raw_value)
        except ValueError:
            return _invalid(tag_key, raw_value)
        return DateObservation(tag_key, raw_value, raw_value, "unknown", "day", "medium")

    try:
        parsed = isoparse(raw_value)
    except (TypeError, ValueError, OverflowError):
        return _invalid(tag_key, raw_value)

    # ``isoparse`` returns a date for a date-only input; the explicit regexes
    # above handle those while retaining their source precision.
    if isinstance(parsed, _datetime.datetime):
        aware = parsed.tzinfo is not None and parsed.utcoffset() is not None
        status = "explicit" if aware else "naive"
        # Seconds are the conservative precision for a timestamp.  A value
        # without seconds is still a valid datetime, but is less precise.
        time_match = _TIME_RE.search(raw_value)
        has_seconds = bool(time_match and time_match.group(0).count(":") >= 2)
        precision = "second" if has_seconds else "minute"
        confidence = "high" if aware else "medium"
        return DateObservation(
            tag_key,
            raw_value,
            parsed.isoformat(),
            status,
            precision,
            confidence,
        )
    return _invalid(tag_key, raw_value)


def _datetime_from_observation(observation: DateObservation) -> _datetime.datetime:
    if not observation.parseable or observation.date_precision not in {"minute", "second"}:
        raise ValueError("only parseable datetime observations can be offset")
    assert observation.normalized_value is not None
    try:
        return _datetime.datetime.fromisoformat(observation.normalized_value)
    except ValueError as exc:
        raise ValueError("observation does not contain a parseable datetime") from exc


def _exact_seconds(source_start_sample: int, sample_rate_hz: int | float) -> Fraction:
    if isinstance(source_start_sample, bool) or not isinstance(source_start_sample, int):
        raise TypeError("source_start_sample must be a non-negative integer")
    if source_start_sample < 0:
        raise ValueError("source_start_sample must be non-negative")
    if isinstance(sample_rate_hz, bool) or not isinstance(sample_rate_hz, (int, float)):
        raise TypeError("sample_rate_hz must be a positive number")
    if not math.isfinite(float(sample_rate_hz)) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be finite and positive")
    try:
        rate = Fraction(Decimal(str(sample_rate_hz)))
    except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
        raise ValueError("sample_rate_hz must be a valid number") from exc
    return Fraction(source_start_sample, 1) / rate


def offset_date_observation(
    observation: DateObservation,
    source_start_sample: int,
    sample_rate_hz: int | float,
) -> DateObservation:
    """Offset a datetime observation by an exact source sample position.

    Date-only, month-only, and year-only observations are rejected because an
    offset would necessarily invent missing time components.  The original
    timezone semantics are retained.
    """

    if not isinstance(observation, DateObservation):
        raise TypeError("observation must be a DateObservation")
    elapsed = _exact_seconds(source_start_sample, sample_rate_hz)
    parsed = _datetime_from_observation(observation)
    # Python datetime has microsecond precision.  Round only at that final
    # representation boundary; the sample/rate ratio itself is exact.
    microseconds_numerator = elapsed.numerator * 1_000_000
    whole_microseconds, remainder = divmod(microseconds_numerator, elapsed.denominator)
    if remainder * 2 >= elapsed.denominator:
        whole_microseconds += 1
    shifted = parsed + _datetime.timedelta(microseconds=whole_microseconds)
    return replace(observation, normalized_value=shifted.isoformat())


# Short alias for callers that already have a DateObservation object.
offset_observation = offset_date_observation
