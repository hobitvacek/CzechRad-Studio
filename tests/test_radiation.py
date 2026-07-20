"""Tests for CzechRad dose conversion and stop display aggregation."""

import unittest
from datetime import datetime, timedelta, timezone

from czechrad_studio.core import CzechRadMeasurement, cpm_to_usvh
from czechrad_studio.missions import (
    StopCandidate,
    assess_stop_radiation,
    summarize_stable_stop,
)


def measurement(index: int, cpm: int) -> CzechRadMeasurement:
    return CzechRadMeasurement(
        device_id="TEST",
        timestamp=datetime(2026, 7, 19, tzinfo=timezone.utc)
        + timedelta(seconds=index * 5),
        cpm=cpm,
        interval_counts=2,
        total_counts=index,
        gps_status="A",
        latitude=50.0,
        longitude=14.0,
        altitude_m=200.0,
        altitude_status="A",
        satellites=8,
        hdop_raw=100,
        expected_checksum=1,
        calculated_checksum=1,
        raw_line="$CZRA1,test",
    )


def candidate(values):
    items = tuple(measurement(index, value) for index, value in enumerate(values))
    return StopCandidate(
        start=items[0].timestamp,
        end=items[-1].timestamp,
        measurements=items,
        center_latitude=50.0,
        center_longitude=14.0,
        radius_p95_m=2.0,
    )


def contextual_track(stop, before_cpm=40, after_cpm=42):
    before = tuple(
        measurement(-index, before_cpm + index % 2) for index in range(1, 19)
    )
    after_start = len(stop.measurements)
    after = tuple(
        measurement(after_start + index, after_cpm - index % 2)
        for index in range(1, 19)
    )
    return before + stop.measurements + after


class RadiationTest(unittest.TestCase):
    def test_czechrad_calibration_matches_documented_factor(self):
        self.assertAlmostEqual(1.0, cpm_to_usvh(328.5))
        self.assertAlmostEqual(0.18, cpm_to_usvh(59.13))

    def test_stable_stop_is_summarized_without_modifying_measurements(self):
        stop = candidate([40, 41, 39, 42, 40])

        summary = summarize_stable_stop(stop)

        self.assertIsNotNone(summary)
        self.assertEqual(5, summary.sample_count)
        self.assertEqual(39, summary.minimum_cpm)
        self.assertEqual(42, summary.maximum_cpm)
        self.assertEqual(5, len(stop.measurements))

    def test_sudden_radiation_increase_remains_expanded(self):
        self.assertIsNone(summarize_stable_stop(candidate([40, 41, 70, 72])))

    def test_sustained_radiation_rise_remains_expanded(self):
        self.assertIsNone(summarize_stable_stop(candidate([40, 46, 52, 58])))

    def test_ordinary_stop_is_not_marked_against_local_background(self):
        stop = candidate([40, 41, 39, 42, 40, 41] * 6)
        track = contextual_track(stop)

        assessment = assess_stop_radiation(stop, track)

        self.assertIsNotNone(assessment)
        self.assertFalse(assessment.elevated)
        self.assertIsNotNone(summarize_stable_stop(stop, track))

    def test_elevated_stop_is_marked_and_not_aggregated(self):
        stop = candidate([58, 60, 61, 59, 62, 60] * 6)
        track = contextual_track(stop)

        assessment = assess_stop_radiation(stop, track)

        self.assertTrue(assessment.elevated)
        self.assertGreaterEqual(assessment.increase_ratio, 0.30)
        self.assertIsNone(summarize_stable_stop(stop, track))

    def test_single_noisy_peak_does_not_mark_a_stop(self):
        stop = candidate([40] * 15 + [100] + [40] * 20)
        assessment = assess_stop_radiation(stop, contextual_track(stop))

        self.assertFalse(assessment.elevated)

    def test_missing_surrounding_context_is_not_claimed_as_elevated(self):
        stop = candidate([60] * 36)

        self.assertIsNone(assess_stop_radiation(stop, stop.measurements))


if __name__ == "__main__":
    unittest.main()

