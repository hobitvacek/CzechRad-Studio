"""Tests for conservative automatic measurement-segment proposals."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from czechrad_studio.core import (
    CzechRadMeasurement,
    LocationQuality,
    MeasurementValidation,
    TimeQuality,
)
from czechrad_studio.missions import LocationLossEpisode, StopCandidate
from czechrad_studio.segments import ProposalType, propose_segments


def measurement(at, latitude=50.0, longitude=14.0):
    return CzechRadMeasurement(
        device_id="TEST", timestamp=at, cpm=40, interval_counts=3,
        total_counts=int(at.timestamp()), radiation_status="A", gps_status="A",
        latitude=latitude, longitude=longitude, altitude_m=200.0,
        satellites=8, hdop_raw=100, expected_checksum=1,
        calculated_checksum=1, raw_line="$CZRA1,test",
    )


def validation(item):
    return MeasurementValidation(
        measurement=item, time_quality=TimeQuality.VALID,
        location_quality=LocationQuality.VALID,
        radiation_valid=True, issues=(),
    )


class SegmentProposalTest(unittest.TestCase):
    def test_proposes_stop_gps_loss_and_recording_gap(self):
        start = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)
        first = measurement(start)
        stop_end = measurement(start + timedelta(minutes=4))
        after_gap = measurement(start + timedelta(minutes=15), 50.01, 14.01)
        exit_anchor = measurement(start + timedelta(minutes=17), 50.011, 14.011)
        stop = StopCandidate(
            start=first.timestamp, end=stop_end.timestamp,
            measurements=(first, stop_end), center_latitude=50.0,
            center_longitude=14.0, radius_p95_m=2.0,
        )
        loss = LocationLossEpisode(
            start=after_gap.timestamp + timedelta(seconds=5),
            end=after_gap.timestamp + timedelta(minutes=1),
            measurements=(measurement(after_gap.timestamp + timedelta(seconds=5), None, None),),
            entry_anchor=after_gap, exit_anchor=exit_anchor,
        )
        analysis = SimpleNamespace(
            stop_candidates=(stop,), location_losses=(loss,),
            geometry_measurements=(first, stop_end, after_gap, exit_anchor),
            track_validations=tuple(
                validation(item) for item in (first, stop_end, after_gap, exit_anchor)
            ),
        )

        proposals = propose_segments(analysis)

        self.assertEqual(
            {ProposalType.STATIONARY, ProposalType.GPS_LOSS, ProposalType.RECORDING_GAP},
            {item.proposal_type for item in proposals},
        )
        gap = next(
            item for item in proposals
            if item.proposal_type is ProposalType.RECORDING_GAP
        )
        self.assertEqual(stop_end.timestamp, gap.start)
        self.assertEqual(after_gap.timestamp, gap.end)
        self.assertEqual(1.0, gap.confidence)

    def test_rejects_nonpositive_gap_threshold(self):
        analysis = SimpleNamespace(
            stop_candidates=(), location_losses=(), geometry_measurements=(),
            track_validations=(),
        )
        with self.assertRaises(ValueError):
            propose_segments(analysis, recording_gap=timedelta(0))


if __name__ == "__main__":
    unittest.main()
