"""Optional map-only aggregation of stable prolonged stops."""

from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from .stops import StopCandidate


@dataclass(frozen=True, slots=True)
class StopSummary:
    """One average display point representing a stable stop."""

    start: datetime
    end: datetime
    latitude: float
    longitude: float
    average_cpm: float
    minimum_cpm: int
    maximum_cpm: int
    sample_count: int

    @property
    def dose_rate_usvh(self) -> float:
        from ..core.radiation import cpm_to_usvh

        return cpm_to_usvh(self.average_cpm)


def has_radiation_signal(candidate: StopCandidate) -> bool:
    """Detect a clear jump or sustained rise that should remain expanded.

    This deliberately favours keeping the original points. Aggregation is only
    used when a stop looks radiologically stable; it never modifies source data.
    """

    values = [item.cpm for item in candidate.measurements]
    if len(values) < 2:
        return False

    for previous, current in zip(values, values[1:]):
        if current - previous >= max(15, previous * 0.50):
            return True

    for index in range(len(values) - 3):
        window = values[index : index + 4]
        if all(right > left for left, right in zip(window, window[1:])):
            if window[-1] - window[0] >= max(15, window[0] * 0.35):
                return True
    return False


def summarize_stable_stop(candidate: StopCandidate) -> StopSummary | None:
    """Return an average point, or ``None`` when original detail matters."""

    if has_radiation_signal(candidate):
        return None
    values = [item.cpm for item in candidate.measurements]
    return StopSummary(
        start=candidate.start,
        end=candidate.end,
        latitude=candidate.center_latitude,
        longitude=candidate.center_longitude,
        average_cpm=mean(values),
        minimum_cpm=min(values),
        maximum_cpm=max(values),
        sample_count=len(values),
    )

