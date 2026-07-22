"""Correlate cumulative ``NOGPS.LOG`` records with one daily track LOG."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..core.models import CzechRadMeasurement
from .validation import validate_measurement


@dataclass(frozen=True)
class NogpsCorrelation:
    """Auditable selection of NOGPS records for one daily track."""

    expected_date: date
    device_id: str
    matched: tuple[CzechRadMeasurement, ...]
    untrusted_time: tuple[CzechRadMeasurement, ...]
    different_device: tuple[CzechRadMeasurement, ...]
    outside_window: tuple[CzechRadMeasurement, ...]


def correlate_nogps(
    track_measurements: tuple[CzechRadMeasurement, ...],
    nogps_measurements: tuple[CzechRadMeasurement, ...],
    *,
    boundary_tolerance: timedelta = timedelta(minutes=10),
) -> NogpsCorrelation:
    """Select records belonging to the same device and daily recording window.

    CzechRad appends NOGPS records from multiple days and sessions to one
    cumulative file. A syntactically valid device-default date must therefore
    never be accepted merely because it appears in ``NOGPS.LOG``.
    """

    if not track_measurements:
        raise ValueError("track_measurements must not be empty")
    if boundary_tolerance < timedelta(0):
        raise ValueError("boundary_tolerance must not be negative")

    ordered_track = sorted(track_measurements, key=lambda item: item.timestamp)
    device_ids = {item.device_id for item in ordered_track}
    dates = {item.timestamp.date() for item in ordered_track}
    if len(device_ids) != 1:
        raise ValueError("daily track must contain exactly one device")
    if len(dates) != 1:
        raise ValueError("daily track must contain exactly one UTC date")

    device_id = next(iter(device_ids))
    expected_date = next(iter(dates))
    window_start = ordered_track[0].timestamp - boundary_tolerance
    window_end = ordered_track[-1].timestamp + boundary_tolerance

    matched: list[CzechRadMeasurement] = []
    untrusted_time: list[CzechRadMeasurement] = []
    different_device: list[CzechRadMeasurement] = []
    outside_window: list[CzechRadMeasurement] = []

    for measurement in sorted(nogps_measurements, key=lambda item: item.timestamp):
        if measurement.device_id != device_id:
            different_device.append(measurement)
            continue

        validation = validate_measurement(measurement, expected_date=expected_date)
        if not validation.usable_without_location:
            untrusted_time.append(measurement)
            continue

        if not window_start <= measurement.timestamp <= window_end:
            outside_window.append(measurement)
            continue

        matched.append(measurement)

    return NogpsCorrelation(
        expected_date=expected_date,
        device_id=device_id,
        matched=tuple(matched),
        untrusted_time=tuple(untrusted_time),
        different_device=tuple(different_device),
        outside_window=tuple(outside_window),
    )
