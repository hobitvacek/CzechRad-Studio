"""Detect spatially bounded stop candidates in a trusted GPS track."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from statistics import median

from ..core.models import CzechRadMeasurement
from ..importer.validation import validate_measurement


@dataclass(frozen=True, slots=True)
class StopCandidate:
    """A prolonged spatial cluster that may represent a real stop.

    A GPS track alone cannot identify the reason for stopping. In particular,
    a long public-transport dwell can look exactly like intentional stationary
    measurement. The UI must therefore present candidates for confirmation.
    """

    start: datetime
    end: datetime
    measurements: tuple[CzechRadMeasurement, ...]
    center_latitude: float
    center_longitude: float
    radius_p95_m: float

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


def _distance_m(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    latitude_a_rad = radians(latitude_a)
    latitude_b_rad = radians(latitude_b)
    latitude_delta = latitude_b_rad - latitude_a_rad
    longitude_delta = radians(longitude_b - longitude_a)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(latitude_a_rad)
        * cos(latitude_b_rad)
        * sin(longitude_delta / 2) ** 2
    )
    return 2 * 6_371_000 * asin(sqrt(haversine))


def _candidate(
    measurements: list[CzechRadMeasurement],
) -> StopCandidate:
    center_latitude = median(item.latitude for item in measurements)
    center_longitude = median(item.longitude for item in measurements)
    distances = sorted(
        _distance_m(
            center_latitude,
            center_longitude,
            item.latitude,
            item.longitude,
        )
        for item in measurements
    )
    percentile_index = min(len(distances) - 1, int(len(distances) * 0.95))
    return StopCandidate(
        start=measurements[0].timestamp,
        end=measurements[-1].timestamp,
        measurements=tuple(measurements),
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        radius_p95_m=distances[percentile_index],
    )


def detect_stop_candidates(
    track_measurements: tuple[CzechRadMeasurement, ...],
    *,
    radius_m: float = 30.0,
    minimum_duration: timedelta = timedelta(minutes=3),
    maximum_sample_gap: timedelta = timedelta(seconds=30),
    merge_gap: timedelta = timedelta(seconds=90),
) -> tuple[StopCandidate, ...]:
    """Return prolonged spatial clusters from trusted positions.

    The algorithm is intentionally conservative about meaning, not presence:
    it detects where the device stayed within ``radius_m`` of an anchor for at
    least ``minimum_duration``. Invalid GPS positions and discontinuous
    recording periods cannot create or bridge a candidate.
    """

    if radius_m <= 0:
        raise ValueError("radius_m must be positive")
    if minimum_duration < timedelta(0):
        raise ValueError("minimum_duration must not be negative")
    if maximum_sample_gap <= timedelta(0):
        raise ValueError("maximum_sample_gap must be positive")
    if merge_gap < timedelta(0):
        raise ValueError("merge_gap must not be negative")
    if not track_measurements:
        return ()

    dates = {item.timestamp.date() for item in track_measurements}
    if len(dates) != 1:
        raise ValueError("daily track must contain exactly one UTC date")
    expected_date = next(iter(dates))
    points = sorted(
        (
            item
            for item in track_measurements
            if validate_measurement(item, expected_date=expected_date).has_geometry
        ),
        key=lambda item: item.timestamp,
    )

    candidates: list[StopCandidate] = []
    start_index = 0
    while start_index < len(points) - 1:
        anchor = points[start_index]
        end_index = start_index + 1
        while end_index < len(points):
            previous = points[end_index - 1]
            current = points[end_index]
            if current.timestamp - previous.timestamp > maximum_sample_gap:
                break
            if (
                _distance_m(
                    anchor.latitude,
                    anchor.longitude,
                    current.latitude,
                    current.longitude,
                )
                > radius_m
            ):
                break
            end_index += 1

        cluster = points[start_index:end_index]
        if cluster[-1].timestamp - cluster[0].timestamp >= minimum_duration:
            candidates.append(_candidate(cluster))
            start_index = end_index
        else:
            start_index += 1

    if not candidates:
        return ()

    merged: list[StopCandidate] = [candidates[0]]
    for candidate in candidates[1:]:
        previous = merged[-1]
        centers_distance = _distance_m(
            previous.center_latitude,
            previous.center_longitude,
            candidate.center_latitude,
            candidate.center_longitude,
        )
        if (
            candidate.start - previous.end <= merge_gap
            and centers_distance <= radius_m * 2
        ):
            merged[-1] = _candidate(
                list((*previous.measurements, *candidate.measurements))
            )
        else:
            merged.append(candidate)

    return tuple(merged)

