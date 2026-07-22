"""Optional map-only aggregation of stable prolonged stops."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, median

from .stops import StopCandidate


@dataclass(frozen=True)
class StopSummary:
    """One average display point representing a stable stop."""

    start: datetime
    end: datetime
    latitude: float
    longitude: float
    average_cpm: float
    average_interval_counts: float
    minimum_cpm: int
    maximum_cpm: int
    sample_count: int
    cpm_per_usvh: float

    @property
    def dose_rate_usvh(self) -> float:
        from ..core.radiation import cpm_to_usvh

        return cpm_to_usvh(
            self.average_cpm, cpm_per_usvh=self.cpm_per_usvh
        )

    @property
    def interval_dose_rate_usvh(self) -> float:
        from ..core.radiation import interval_counts_to_usvh

        return interval_counts_to_usvh(
            self.average_interval_counts, cpm_per_usvh=self.cpm_per_usvh
        )


@dataclass(frozen=True)
class StopRadiationAssessment:
    """Comparison of one stop with the nearby moving-track background."""

    baseline_cpm: float
    stop_average_cpm: float
    sustained_cpm: float
    comparison_cpm: float
    increase_cpm: float
    increase_ratio: float
    context_samples: int
    elevated: bool
    cpm_per_usvh: float

    @property
    def comparison_usvh(self) -> float:
        from ..core.radiation import cpm_to_usvh

        return cpm_to_usvh(
            self.comparison_cpm, cpm_per_usvh=self.cpm_per_usvh
        )


def _maximum_window_average(values: list[int], window_size: int) -> float:
    if not values:
        raise ValueError("values must not be empty")
    effective_size = min(len(values), window_size)
    return max(
        mean(values[index : index + effective_size])
        for index in range(len(values) - effective_size + 1)
    )


def assess_stop_radiation(
    candidate: StopCandidate,
    track_measurements: tuple,
    *,
    context_duration: timedelta = timedelta(minutes=3),
    minimum_context_samples: int = 12,
    relative_threshold: float = 0.30,
    absolute_threshold_usvh: float = 0.03,
    sustained_samples: int = 6,
) -> StopRadiationAssessment | None:
    """Compare a stop with nearby track values and flag robust elevation.

    The baseline is the median of measurements immediately before and after the
    stop. A stop is elevated only when its median or a sustained 30-second
    window exceeds both the relative and absolute thresholds. Isolated noisy
    points therefore do not create a candidate.
    """

    if context_duration <= timedelta(0):
        raise ValueError("context_duration must be positive")
    if minimum_context_samples < 1:
        raise ValueError("minimum_context_samples must be positive")
    if relative_threshold < 0 or absolute_threshold_usvh < 0:
        raise ValueError("radiation thresholds must not be negative")
    if sustained_samples < 1:
        raise ValueError("sustained_samples must be positive")

    context = [
        item.cpm
        for item in track_measurements
        if item.cpm >= 0
        and (
            candidate.start - context_duration <= item.timestamp < candidate.start
            or candidate.end < item.timestamp <= candidate.end + context_duration
        )
    ]
    if len(context) < minimum_context_samples:
        return None

    stop_values = [item.cpm for item in candidate.measurements if item.cpm >= 0]
    if not stop_values:
        return None

    baseline_cpm = float(median(context))
    stop_average_cpm = mean(stop_values)
    sustained_cpm = _maximum_window_average(stop_values, sustained_samples)
    comparison_cpm = max(float(median(stop_values)), sustained_cpm)
    increase_cpm = comparison_cpm - baseline_cpm
    increase_ratio = (
        increase_cpm / baseline_cpm
        if baseline_cpm > 0
        else (float("inf") if increase_cpm > 0 else 0.0)
    )
    cpm_per_usvh = candidate.measurements[0].cpm_per_usvh
    minimum_increase_cpm = absolute_threshold_usvh * cpm_per_usvh
    elevated = (
        increase_cpm >= minimum_increase_cpm
        and increase_ratio >= relative_threshold
    )
    return StopRadiationAssessment(
        baseline_cpm=baseline_cpm,
        stop_average_cpm=stop_average_cpm,
        sustained_cpm=sustained_cpm,
        comparison_cpm=comparison_cpm,
        increase_cpm=increase_cpm,
        increase_ratio=increase_ratio,
        context_samples=len(context),
        elevated=elevated,
        cpm_per_usvh=cpm_per_usvh,
    )


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


def summarize_stable_stop(
    candidate: StopCandidate,
    track_measurements: tuple | None = None,
) -> StopSummary | None:
    """Return an average point, or ``None`` when original detail matters."""

    if track_measurements is not None:
        assessment = assess_stop_radiation(candidate, track_measurements)
        if assessment is not None and assessment.elevated:
            return None
    elif has_radiation_signal(candidate):
        # Backward-compatible conservative behaviour for clients which do not
        # yet provide the surrounding track.
        return None
    values = [item.cpm for item in candidate.measurements]
    interval_values = [item.interval_counts for item in candidate.measurements]
    return StopSummary(
        start=candidate.start,
        end=candidate.end,
        latitude=candidate.center_latitude,
        longitude=candidate.center_longitude,
        average_cpm=mean(values),
        average_interval_counts=mean(interval_values),
        minimum_cpm=min(values),
        maximum_cpm=max(values),
        sample_count=len(values),
        cpm_per_usvh=candidate.measurements[0].cpm_per_usvh,
    )
