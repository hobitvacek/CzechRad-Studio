"""Conservative automatic proposals for later manual segment editing."""

from __future__ import annotations

from datetime import timedelta

from ..core.models import TimeQuality
from ..importer.session import ImportAnalysis
from ..missions.aggregation import assess_stop_radiation
from .model import ProposalType, SegmentProposal


def propose_segments(
    analysis: ImportAnalysis,
    *,
    recording_gap: timedelta = timedelta(minutes=5),
) -> tuple[SegmentProposal, ...]:
    """Suggest notable time ranges without assigning their final meaning."""

    if recording_gap <= timedelta(0):
        raise ValueError("recording_gap must be positive")

    proposals: list[SegmentProposal] = []
    for candidate in analysis.stop_candidates:
        assessment = assess_stop_radiation(
            candidate, analysis.geometry_measurements
        )
        elevated = assessment is not None and assessment.elevated
        proposals.append(
            SegmentProposal(
                proposal_type=ProposalType.STATIONARY,
                start=candidate.start,
                end=candidate.end,
                confidence=0.90 if elevated else 0.70,
                reason=(
                    "Dlouhé zastavení se zvýšenou radiací; možné cílené "
                    "stacionární měření."
                    if elevated
                    else "Dlouhé prostorově stabilní zastavení."
                ),
                sample_count=len(candidate.measurements),
                center_latitude=candidate.center_latitude,
                center_longitude=candidate.center_longitude,
            )
        )

    for episode in analysis.location_losses:
        proposals.append(
            SegmentProposal(
                proposal_type=ProposalType.GPS_LOSS,
                start=episode.start,
                end=episode.end,
                confidence=0.65,
                reason=(
                    "Ztráta použitelné GPS mezi důvěryhodným vstupním a "
                    "výstupním bodem; může jít o pobyt v budově."
                ),
                sample_count=len(episode.measurements),
                center_latitude=episode.entry_anchor.latitude,
                center_longitude=episode.entry_anchor.longitude,
            )
        )

    trusted_time = sorted(
        (
            result.measurement
            for result in analysis.track_validations
            if result.time_quality is TimeQuality.VALID
            and result.measurement.checksum_valid
            and result.radiation_valid
        ),
        key=lambda item: item.timestamp,
    )
    for previous, current in zip(trusted_time, trusted_time[1:]):
        if current.timestamp - previous.timestamp >= recording_gap:
            proposals.append(
                SegmentProposal(
                    proposal_type=ProposalType.RECORDING_GAP,
                    start=previous.timestamp,
                    end=current.timestamp,
                    confidence=1.0,
                    reason="Delší mezera v záznamu; vhodná hranice úseků.",
                    sample_count=0,
                    center_latitude=previous.latitude,
                    center_longitude=previous.longitude,
                )
            )

    return tuple(
        sorted(proposals, key=lambda item: (item.start, item.proposal_type.value))
    )

