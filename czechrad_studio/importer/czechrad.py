"""Parser for CzechRad ``$CZRA1`` LOG records."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from ..core.models import CzechRadMeasurement


class CzechRadParseError(ValueError):
    """Raised when a CzechRad measurement line is structurally invalid."""


@dataclass(frozen=True, slots=True)
class ParseFailure:
    """Audit information for a line that could not be parsed."""

    line_number: int
    line: str
    reason: str


@dataclass(frozen=True, slots=True)
class ParsedLog:
    """Parsed measurements and non-fatal line failures from one source."""

    measurements: tuple[CzechRadMeasurement, ...]
    failures: tuple[ParseFailure, ...]


def calculate_checksum(payload: str) -> int:
    """Calculate the XOR checksum used between ``$`` and ``*``."""

    checksum = 0
    try:
        encoded = payload.encode("ascii")
    except UnicodeEncodeError as exc:
        raise CzechRadParseError("measurement payload is not ASCII") from exc

    for byte in encoded:
        checksum ^= byte
    return checksum


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CzechRadParseError(f"invalid timestamp: {value!r}") from exc

    if parsed.tzinfo is None:
        raise CzechRadParseError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _parse_coordinate(value: str, hemisphere: str, *, latitude: bool) -> float:
    try:
        raw = float(value)
    except ValueError as exc:
        raise CzechRadParseError(f"invalid coordinate: {value!r}") from exc

    allowed = {"N", "S"} if latitude else {"E", "W"}
    if hemisphere not in allowed:
        raise CzechRadParseError(f"invalid hemisphere: {hemisphere!r}")

    degrees = int(raw // 100)
    minutes = raw - degrees * 100
    maximum = 90 if latitude else 180
    if minutes >= 60 or degrees > maximum:
        raise CzechRadParseError(f"coordinate outside valid range: {value!r}")

    decimal = degrees + minutes / 60
    if hemisphere in {"S", "W"}:
        decimal = -decimal
    return decimal


def _parse_coordinates(fields: list[str]) -> tuple[float | None, float | None, str | None]:
    """Parse position independently so valid radiation is never discarded.

    CzechRad can write stale or nonsensical coordinate text while a GPS fix is
    unavailable. The source text and a short audit reason are retained, but no
    geometry is created from either coordinate when one of them is malformed.
    """

    try:
        latitude = _parse_coordinate(fields[7], fields[8], latitude=True)
        longitude = _parse_coordinate(fields[9], fields[10], latitude=False)
    except CzechRadParseError as exc:
        return None, None, str(exc)
    return latitude, longitug=¶‰Ëkºwµç_counts = int(fields[5])
        altitude_m = float(fields[11])
        satellites = int(fields[13])
        hdop_raw = int(fields[14])
    except ValueError as exc:
        raise CzechRadParseError("invalid numeric measurement field") from exc

    latitude, longitude, coordinate_issue = _parse_coordinates(fields)

    return CzechRadMeasurement(
        device_id=fields[1],
        timestamp=_parse_timestamp(fields[2]),
        cpm=cpm,
        interval_counts=interval_counts,
        total_counts=total_counts,
        radiation_status=fields[6],
        gps_status=fields[12],
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
        satellites=satellites,
        hdop_raw=hdop_raw,
        expected_checksum=expected_checksum,
        calculated_checksum=calculate_checksum(sentence[1:]),
        raw_line=raw_line,
        line_number=line_number,
        coordinate_issue=coordinate_issue,
    )


def parse_log(lines: Iterable[str]) -> ParsedLog:
    """Parse a LOG stream, skipping comments and auditing malformed records."""

    measurements: list[CzechRadMeasurement] = []
    failures: list[ParseFailure] = []

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            measurements.append(
                parse_measurement_line(stripped, line_number=line_number)
            )
        except CzechRadParseError as exc:
            failures.append(ParseFailure(line_number, stripped, str(exc)))

    return ParsedLog(tuple(measurements), tuple(failures))
