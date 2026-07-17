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


def parse_measurement_line(
    line: str, *, line_number: int | None = None
) -> CzechRadMeasurement:
    """Parse one CzechRad measurement while preserving untrusted GPS facts."""

    raw_line = line.strip()
    if not raw_line.startswith("$CZRA1,"):
        raise CzechRadParseError("not a $CZRA1 measurement")
    if "*" not in raw_line:
        raise CzechRadParseError("missing checksum separator")

    sentence, checksum_text = raw_line.rsplit("*", 1)
    # CzechRad firmware writes both zero-padded (``*0C``) and compact
    # (``*C``) hexadecimal checksums, so both representations are valid.
    if len(checksum_text) not in {1, 2}:
        raise CzechRadParseError("checksum must contain one or two hexadecimal digits")
    try:
        expected_checksum = int(checksum_text, 16)
    except ValueError as exc:
        raise CzechRadParseError("checksum is not hexadecimal") from exc

    fields = sentence[1:].split(",")
    if len(fields) != 15:
        raise CzechRadParseError(
            f"expected 15 fields, received {len(fields)}"
        )

    try:
        cpm = int(fields[3])
        interval_counts = int(fields[4])
        total_counts = int(fields[5])
        altitude_m = float(fields[11])
        satellites = int(fields[13])
        hdop_raw = int(fields[14])
    except ValueError as exc:
        raise CzechRadParseError("invalid numeric measurement field") from exc

    return CzechRadMeasurement(
        device_id=fields[1],
        timestamp=_parse_timestamp(fields[2]),
        cpm=cpm,
        interval_counts=interval_counts,
        total_counts=total_counts,
        gps_status=fields[6],
        latitude=_parse_coordinate(fields[7], fields[8], latitude=True),
        longitude=_parse_coordinate(fields[9], fields[10], latitude=False),
        altitude_m=altitude_m,
        altitude_status=fields[12],
        satellites=satellites,
        hdop_raw=hdop_raw,
        expected_checksum=expected_checksum,
        calculated_checksum=calculate_checksum(sentence[1:]),
        raw_line=raw_line,
        line_number=line_number,
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

