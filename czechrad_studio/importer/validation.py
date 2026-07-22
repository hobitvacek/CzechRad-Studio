"""Validation rules for parsed CzechRad measurements."""

from __future__ import annotations

from datetime import date

from ..core.models import (
    CzechRadMeasurement,
    LocationQuality,
    MeasurementValidation,
    TimeQuality,
)


HDOP_NO_FIX = 9999


def validate_measurement(
    measurement: CzechRadMeasurement, *, expected_date: date | None = None
) -> MeasurementValidation:
    """Validate time, radiation and GPS independently.

    ``expected_date`` is normally the trusted date of the related mission or
    track LOG. It prevents a device default date from being accepted merely
    because it is syntactically valid.
    """

    issues: list[str] = []

    if expected_date is not None and measurement.timestamp.date() != expected_date:
        time_quality = TimeQuality.UNTRUSTED
        issues.append("timestamp_date_mismatch")
    else:
        time_quality = TimeQuality.VALID

    radiation_valid = (
        measurement.cpm >= 0
        and measurement.interval_counts >= 0
        and measurement.total_counts >= 0
    )
    if not radiation_valid:
        issues.append("negative_radiation_value")

    latitude = measurement.latitude
    longitude = measurement.longitude
    has_nonzero_coordinates = (
        latitude is not None
        and longitude is not None
        and not (latitude == 0.0 and longitude == 0.0)
    )

    if measurement.coordinate_issue is not None:
        location_quality = LocationQuality.INVALID
        issues.append("invalid_coordinate_encoding")
    elif not has_nonzero_coordinates:
        location_quality = LocationQuality.NONE
        issues.append("missing_coordinates")
    elif (
        measurement.gps_status != "A"
        or measurement.satellites <= 0
        or measurement.hdop_raw == HDOP_NO_FIX
    ):
        location_quality = LocationQuality.INVALID
        issues.append("untrusted_gps_fix")
    else:
        location_quality = LocationQuality.VALID

    if not measurement.checksum_valid:
        issues.append("checksum_mismatch")

    return MeasurementValidation(
        measurement=measurement,
        time_quality=time_quality,
        location_quality=location_quality,
        radiation_valid=radiation_valid,
        issues=tuple(issues),
    )
