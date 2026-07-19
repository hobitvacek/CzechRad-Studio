"""Tests for CzechRad dose conversion and stop display aggregation."""

import unittest
from datetime import datetime, timedelta, timezone

from czechrad_studio.core import CzechRadMeasurement, cpm_to_usvh
from czechrad_studio.missions import StopCandidate, summarize_stable_stop


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


if __name__ == "__main__":
    unittest.main()

