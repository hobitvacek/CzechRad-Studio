"""Tests for read-only card discovery and collision-safe archiving."""

import tempfile
import unittest
from pathlib import Path

from czechrad_studio.monitoring import (
    StableFileTracker,
    archive_log,
    archive_ready_logs,
)


class MonitoringTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.card = root / "card"
        self.archive = root / "archive"
        self.card.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def write_log(self, name, content):
        path = self.card / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_requires_two_unchanged_observations(self):
        source = self.write_log("07960720.LOG", "first")
        tracker = StableFileTracker()

        self.assertEqual((), archive_ready_logs(tracker, self.card, self.archive))
        results = archive_ready_logs(tracker, self.card, self.archive)

        self.assertEqual(1, len(results))
        self.assertTrue(results[0].copied)
        self.assertEqual(source.read_bytes(), results[0].destination.read_bytes())

    def test_changed_file_must_become_stable_again(self):
        source = self.write_log("07960720.LOG", "first")
        tracker = StableFileTracker()
        tracker.observe(self.card)
        tracker.observe(self.card)

        source.write_text("first plus new data", encoding="utf-8")

        self.assertEqual((), tracker.observe(self.card))
        self.assertEqual((source,), tracker.observe(self.card))

    def test_identical_content_is_not_copied_twice(self):
        first = self.write_log("07960720.LOG", "same measurement")
        duplicate = self.write_log("COPY.LOG", "same measurement")

        result_one = archive_log(first, self.archive)
        result_two = archive_log(duplicate, self.archive)

        self.assertTrue(result_one.copied)
        self.assertFalse(result_two.copied)
        self.assertEqual(result_one.destination, result_two.destination)

    def test_same_name_with_different_content_gets_numbered(self):
        source = self.write_log("07960720.LOG", "year one")
        first = archive_log(source, self.archive)
        source.write_text("year two", encoding="utf-8")
        second = archive_log(source, self.archive)

        self.assertEqual("07960720.LOG", first.destination.name)
        self.assertEqual("07960720-1.LOG", second.destination.name)
        self.assertEqual("year one", first.destination.read_text(encoding="utf-8"))
        self.assertEqual("year two", second.destination.read_text(encoding="utf-8"))

    def test_changed_cumulative_nogps_is_versioned(self):
        source = self.write_log("NOGPS.LOG", "day one")
        archive_log(source, self.archive)
        source.write_text("day one and day two", encoding="utf-8")

        result = archive_log(source, self.archive)

        self.assertEqual("NOGPS-1.LOG", result.destination.name)


if __name__ == "__main__":
    unittest.main()

