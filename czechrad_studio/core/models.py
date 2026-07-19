"""QGIS-independent domain types for CzechRad measurements."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .radiation import cpm_to_usvh, interval_counts_to_usvh


class TimeQuality(str, Enum):
    """Trust assigned to a measurement timestamp."""

    VALID = "valid"
    UNTRUSTED = "untrusted"
    MISSING = "missing"


class LocationQuality(str, Enum):
    """Trust assigned to the original GPS position."""

    VALID = "gps_valid"
    INVALID = "gps_invalid"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class CzechRadMeasurement:
    """One parsed ``$CZRA1`` record without QGIS-specific objects."""

    device_id: str
    timestamp: datetime
    cpm: int
    interval_counts: int
    total_counts: int
    gps_status: str
    latitude: float | None
    longitude: float | None
    altitude_m: float | None
    altitude_status: str
    satellites: int
    hdop_raw: int
    expected_checksum: int
    calculated_checksum: int
    raw_line: str
    line_number: int | None = None

    @property
    def checksum_valid(self) -> bool:
        """Return whether the NMEA-style XOR checksum matches."""

        return self.expected_checksum == self.calculated_checksum

    @property
    def hdop(self) -> float:
        """Return the device HDOP value in decimal form."""

        return self.hdop_raw / 100.0

    @property
    def dose_rate_usvh(self) -> float:
        """Stable one-minute dose-rate estimate shown by CzechRad."""

        return cpm_to_usvh(self.cpm)

    @property
    def interval_dose_rate_usvh(self) -> float:
        """Faster, noisier estimate from the latest five-second interval."""

        return interval_counts_to_usvh(self.interval_counts)


@dataclass(frozen=True, slots=True)
class MeasurementValidation:
    """Independent validation result for a parsed measurement."""

    measurement: CzechRadMeasurement
    time_quality: TimeQuality
    location_quality: LocationQuality
    radiation_valid: bool
    issues: tuple[str, ...]

    @property
    def usable_without_location(self) -> bool:
        """Whether the radiation value may be stored without geometry."""

        return (
            self.measurement.checksum_valid
            and self.time_quality is TimeQuality.VALID
            and self.radiation_valid
        )

    @property
    def has_geometry(self) -> bool:
        """Whether the original coordinates may create map geometry."""

        return self.location_quality is LocationQuality.VALID

