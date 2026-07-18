"""Tests for cumulative NOGPS correlation and GPS-loss candidates."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from czechrad_studio.core import CzechRadMeasurement
from czechrad_studio.importer import correlate_nogps
from czechrad_studio.missions import detect_location_loss_episodes


UTC = timezone.utc


def measurement(
    timestamp: datetime,
    *,
    device_id: str = "TEST",
    trusted_location: bool = True,
    total_counts: int = 1,
) -> CzechRadMeasurement:
    return CzechRadMeasurement(
        device_id=device_id,
        timestamp=timestamp,
        cpm=20,
        interval_counts=2,
        total_counts=total_counts,
        gps_status="A",
        latitude=50.0,
        longitude=14.0,
        altitude_m=200.0,
        altitude_status="A",
        satellites=8 if trusted_location else 0,
        hdop_raw=100 if trusted_location else 9999,
        expected_checksum=1,
        calculated_checksum=1,
        raw_line="$CZRA1,test",
    )


class NogpsCorrelationTest(unittest.TestCase):
    def setUp(self):
        self.day = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
        self.track = (
            measurement(self.day, total_counts=10),
            measurement(self.day + timedelta(minutes=30), total_counts=100),
        )

    def test_selects_only_same_device_date_and_recording_window(self):
        startup = measurement(
            self.day - timedelta(seconds=5),
            trusted_location=False,
            total_counts=8,
        )
        old_default_date = measurement(
            datetime(2020, 8, 2, 0, 0, tzinfo=UTC),
            trusted_location=False,
        )
        other_device = replace(startup, device_id="OTHER")
        outside_window = measurement(
            self.day + timedelta(hours=2), trusted_location=False
        )

        result = correlate_nogps(
            self.track,
            (old_default_date, outside_window, other_device, startup),
        )

        self.assertEqual((startup,), result.matched)
        self.assertEqual((old_default_date,), result.untrusted_time)
        self.assertEqual((other_device,), result.different_device)
        self.assertEqual((outside_window,), result.outside_window)

    def test_requires_one_device_and_one_utc_date(self):
        mixed_devices = self.track + (replace(self.track[0], device_id="OTHER"),)
        mixed_dates = self.track + (
            replace(self.track[0], timestamp=self.day + timedelta(days=1)),
        )

        with self.assertRaises(ValueError):
            correlate_nogps(mixed_devices, ())
        with self.assertRaises(ValueError):
            correlate_nogps(mixed_dates, ())


class LocationLossDetectionTest(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
        self.track = tuple(
            measurement(self.start + timedelta(minutes=minute), total_counts=minute)
            for minute in (0, 8, 10, 11, 12, 13, 15, 20, 30)
        )

    def test_bridges_short_recovery_into_one_candidate(self):
        nogps = tuple(
            measurement(
                self.start + timedelta(seconds=int(minute * 60)),
                trusted_location=False,
                total_counts=100 + int(minute * 60),
            )
            for minute in (9, 10.5, 12.5, 14)
        )

        episodes = detect_location_loss_episodes(self.track, nogps)

        self.assertEqual(1, len(episodes))
        self.assertEqual(nogps, episodes[0].measurements)
        self.assertEqual(self.track[1], episodes[0].entry_anchor)
        self.assertEqual(self.track[6], episodes[0].exit_anchor)

    def test_separates_distant_location_losses(self):
        nogps = (
            measurement(
                self.start + timedelta(minutes=9), trusted_location=False
            ),
            measurement(
                self.start + timedelta(minutes=14), trusted_location=False
            ),
        )

        episodes = detect_location_loss_episodes(
            self.track, nogps, bridge_tolerance=timedelta(minutes=2)
        )

        self.assertEqual(2, len(episodes))

    def test_does_not_classify_initial_acquisition_as_indoor(self):
        startup = measurement(
            self.start - timedelta(seconds=5), trusted_location=False
        )

        self.assertEqual(
            (), detect_location_loss_episodes(self.track, (startup,))
        )

    def test_rejects_candidate_with_stale_boundary_position(self):
        stale_track = (
            measurement(self.start),
            measurement(self.start + timedelta(hours=3)),
        )
        obscured = measurement(
            self.start + timedelta(hours=2), trusted_location=False
        )

        self.assertEqual(
            (), detect_location_loss_episodes(stale_track, (obscured,))
        )


if __name__ == "__main__":
    unittest.main()

