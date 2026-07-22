"""Tests for conservative, QGIS-independent stop candidate detection."""

import unittest
from datetime import datetime, timedelta, timezone

from czechrad_studio.core import CzechRadMeasurement
from czechrad_studio.missions import detect_stop_candidates


UTC = timezone.utc


def point(
    timestamp: datetime,
    latitude: float,
    longitude: float,
    *,
    trusted: bool = True,
) -> CzechRadMeasurement:
    return CzechRadMeasurement(
        device_id="TEST",
        timestamp=timestamp,
        cpm=20,
        interval_counts=2,
        total_counts=int(timestamp.timestamp()),
        radiation_status="A",
        gps_status="A",
        latitude=latitude,
        longitude=longitude,
        altitude_m=200.0,
        satellites=8 if trusted else 0,
        hdop_raw=100 if trusted else 9999,
        expected_checksum=1,
        calculated_checksum=1,
        raw_line="$CZRA1,test",
    )


def sequence(start, count, coordinate):
    return tuple(
        point(
            start + timedelta(seconds=index * 5),
            coordinate[0] + (index % 3 - 1) * 0.00001,
            coordinate[1] + (index % 5 - 2) * 0.00001,
        )
        for index in range(count)
    )


class StopDetectionTest(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)

    def test_detects_ten_minute_stationary_cluster(self):
        track = sequence(self.start, 121, (50.0, 14.0))

        candidates = detect_stop_candidates(track)

        self.assertEqual(1, len(candidates))
        self.assertEqual(timedelta(minutes=10), candidates[0].duration)
        self.assertLess(candidates[0].radius_p95_m, 5)

    def test_short_public_transport_stop_is_ignored(self):
        track = sequence(self.start, 25, (50.0, 14.0))

        self.assertEqual((), detect_stop_candidates(track))

    def test_continuous_movement_is_not_a_stop(self):
        track = tuple(
            point(
                self.start + timedelta(seconds=index * 5),
                50.0 + index * 0.0001,
                14.0,
            )
            for index in range(121)
        )

        self.assertEqual((), detect_stop_candidates(track))

    def test_recording_gap_does_not_bridge_two_short_visits(self):
        first = sequence(self.start, 25, (50.0, 14.0))
        second = sequence(
            self.start + timedelta(minutes=20), 25, (50.0, 14.0)
        )

        self.assertEqual((), detect_stop_candidates(first + second))

    def test_merges_adjacent_fragments_caused_by_gps_drift(self):
        first = sequence(self.start, 49, (50.0, 14.0))
        second = sequence(
            self.start + timedelta(seconds=245),
            49,
            (50.00032, 14.0),
        )

        candidates = detect_stop_candidates(first + second)

        self.assertEqual(1, len(candidates))
        self.assertGreaterEqual(candidates[0].duration, timedelta(minutes=7))

    def test_invalid_gps_cannot_form_stop(self):
        track = tuple(
            point(
                self.start + timedelta(seconds=index * 5),
                50.0,
                14.0,
                trusted=False,
            )
            for index in range(121)
        )

        self.assertEqual((), detect_stop_candidates(track))

    def test_rejects_multiple_dates(self):
        track = (
            point(self.start, 50.0, 14.0),
            point(self.start + timedelta(days=1), 50.0, 14.0),
        )

        with self.assertRaises(ValueError):
            detect_stop_candidates(track)


if __name__ == "__main__":
    unittest.main()
