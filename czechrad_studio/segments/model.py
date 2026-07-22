"""QGIS-independent measurement segment and proposal types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SegmentType(str, Enum):
    UNCLASSIFIED = "unclassified"
    WALKING = "walking"
    CAR = "car"
    PUBLIC_TRANSPORT = "public_transport"
    STATIONARY = "stationary"
    INDOOR = "indoor"
    EXCLUDED = "excluded"


class ProposalType(str, Enum):
    STATIONARY = "stationary"
    GPS_LOSS = "gps_loss"
    RECORDING_GAP = "recording_gap"


@dataclass(frozen=True)
class SegmentProposal:
    """One automatic suggestion which always requires user confirmation."""

    proposal_type: ProposalType
    start: datetime
    end: datetime
    confidence: float
    reason: str
    sample_count: int
    center_latitude: float | None = None
    center_longitude: float | None = None
    id: str | None = None
    source_log_id: str | None = None
    revision_id: str | None = None


@dataclass(frozen=True)
class MeasurementSegment:
    """A user-owned stable segment attached to a daily source LOG."""

    id: str
    source_log_id: str
    mission_id: str | None
    start: datetime
    end: datetime
    segment_type: SegmentType
    title: str
    status: str
    include_in_suro: bool
    detector_height_m: float | None
    detector_orientation: str
    route_description: str
    notes: str
