"""Measurement segment domain model and automatic proposals."""

from .model import MeasurementSegment, ProposalType, SegmentProposal, SegmentType
from .proposals import propose_segments

__all__ = [
    "MeasurementSegment",
    "ProposalType",
    "SegmentProposal",
    "SegmentType",
    "propose_segments",
]
