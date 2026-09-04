"""QGIS-independent checks for preparing measurement segments for SÚRO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..segments import MeasurementSegment, SegmentType


@dataclass(frozen=True)
class SegmentReadiness:
    """Readiness result for one user-owned measurement segment."""

    segment_id: str
    included: bool
    ready: bool
    missing: tuple[str, ...]

    @property
    def label(self) -> str:
        if not self.included:
            return "Nezahrnout"
        return "Připraveno" if self.ready else "Doplnit údaje"


@dataclass(frozen=True)
class MissionReadiness:
    """Aggregate readiness summary for one mission."""

    total_count: int
    included_count: int
    ready_count: int
    incomplete_count: int
    results: tuple[SegmentReadiness, ...]


def assess_segment(segment: MeasurementSegment) -> SegmentReadiness:
    """Check only fields already confirmed by the user.

    No value is inferred from GPS, speed, filename or other indirect data.
    """

    if not segment.include_in_suro:
        return SegmentReadiness(segment.id, False, False, ())

    missing = []
    if segment.status != "confirmed":
        missing.append("potvrdit úsek")
    if segment.segment_type in (
        SegmentType.UNCLASSIFIED,
        SegmentType.EXCLUDED,
    ):
        missing.append("zvolit způsob měření")
    if segment.detector_height_m is None:
        missing.append("výška detektoru")
    if not segment.detector_orientation.strip():
        missing.append("orientace detektoru")
    if not segment.route_description.strip():
        missing.append("popis trasy nebo místa")

    return SegmentReadiness(
        segment.id,
        True,
        not missing,
        tuple(missing),
    )


def assess_mission(
    segments: Iterable[MeasurementSegment],
) -> MissionReadiness:
    """Return an aggregate without changing segments or source LOG files."""

    results = tuple(assess_segment(segment) for segment in segments)
    included = tuple(result for result in results if result.included)
    ready_count = sum(result.ready for result in included)
    return MissionReadiness(
        total_count=len(results),
        included_count=len(included),
        ready_count=ready_count,
        incomplete_count=len(included) - ready_count,
        results=results,
    )
