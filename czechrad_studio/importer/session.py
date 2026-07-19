"""QGIS-independent orchestration of one daily CzechRad import."""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from ..core.models import CzechRadMeasurement, MeasurementValidation, TimeQuality
from ..missions.location_loss import LocationLossEpisode, detect_location_loss_episodes
from ..missions.stops import StopCandidate, detect_stop_candidates
from .czechrad import ParsedLog, parse_log
from .nogps import NogpsCorrelation, correlate_nogps
from .validation import HDOP_NO_FIX, validate_measurement


@dataclass(frozen=True, slots=True)
class ImportAnalysis:
    """Complete analysis prepared for presentation by QGIS or another client."""

    expected_date: date
    track: ParsedLog
    track_validations: tuple[MeasurementValidation, ...]
    nogps: ParsedLog | None
    nogps_correlation: NogpsCorrelation | None
    location_losses: tuple[LocationLossEpisode, ...]
    stop_candidates: tuple[StopCandidate, ...]

    @property
    def geometry_measurements(self) -> tuple[CzechRadMeasurement, ...]:
        return tuple(
            result.measurement for result in self.track_validations if result.has_geometry
        )

    @property
    def without_geometry_count(self) -> int:
        track_count = sum(
            result.usable_without_location and not result.has_geometry
            for result in self.track_validations
        )
        nogps_count = (
            len(self.nogps_correlation.matched)
            if self.nogps_correlation is not None
            else 0
        )
        return track_count + nogps_count

    @property
    def failure_count(self) -> int:
        return len(self.track.failures) + (
            len(self.nogps.failures) if self.nogps is not None else 0
        )


def _trusted_daily_date(measurements: tuple[CzechRadMeasurement, ...]) -> date:
    gps_dates = Counter(
        item.timestamp.date()
        for item in measurements
        if item.checksum_valid
        and item.gps_status == "A"
        and item.satellites > 0
        and item.hdop_raw != HDOP_NO_FIX
    )
    candidate_dates = gps_dates or Counter(
        item.timestamp.date() for item in measurements if item.checksum_valid
    )
    if not candidate_dates:
        raise ValueError("denní LOG neobsahuje důvěryhodné měření")
    return candidate_dates.most_common(1)[0][0]


def analyze_log_lines(
    track_lines: Iterable[str],
    nogps_lines: Iterable[str] | None = None,
) -> ImportAnalysis:
    """Parse and analyze one daily LOG plus an optional cumulative NOGPS file."""

    track = parse_log(track_lines)
    if not track.measurements:
        raise ValueError("denní LOG neobsahuje žádné měření CzechRad")

    expected_date = _trusted_daily_date(track.measurements)
    track_validations = tuple(
        validate_measurement(item, expected_date=expected_date)
        for item in track.measurements
    )
    trusted_time_track = tuple(
        result.measurement
        for result in track_validations
        if result.time_quality is TimeQuality.VALID
        and result.measurement.checksum_valid
        and result.radiation_valid
    )

    nogps = parse_log(nogps_lines) if nogps_lines is not None else None
    correlation = (
        correlate_nogps(trusted_time_track, nogps.measurements)
        if nogps is not None
        else None
    )
    matched_nogps = correlation.matched if correlation is not None else ()

    return ImportAnalysis(
        expected_date=expected_date,
        track=track,
        track_validations=track_validations,
        nogps=nogps,
        nogps_correlation=correlation,
        location_losses=detect_location_loss_episodes(
            trusted_time_track, matched_nogps
        ),
        stop_candidates=detect_stop_candidates(trusted_time_track),
    )


def analyze_log_files(
    track_path: str | Path,
    nogps_path: str | Path | None = None,
) -> ImportAnalysis:
    """Read local files and return the same portable analysis model."""

    track_file = Path(track_path)
    with track_file.open("r", encoding="utf-8-sig", errors="replace") as handle:
        track_lines = tuple(handle)

    nogps_lines = None
    if nogps_path:
        with Path(nogps_path).open(
            "r", encoding="utf-8-sig", errors="replace"
        ) as handle:
            nogps_lines = tuple(handle)

    return analyze_log_lines(track_lines, nogps_lines)

