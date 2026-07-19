"""Tests for the portable daily import orchestration."""

import unittest
from datetime import date
from pathlib import Path

from czechrad_studio.importer import analyze_log_lines


FIXTURE = Path(__file__).parent / "fixtures" / "czechrad_sample.log"


class ImportAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.lines = FIXTURE.read_text(encoding="utf-8").splitlines()

    def test_selects_majority_trusted_date_and_rejects_device_default(self):
        analysis = analyze_log_lines(self.lines)

        self.assertEqual(date(2026, 7, 17), analysis.expected_date)
        self.assertEqual(5, len(analysis.track.measurements))
        self.assertEqual(1, len(analysis.geometry_measurements))
        self.assertEqual(3, analysis.without_geometry_count)
        self.assertEqual(0, analysis.failure_count)

    def test_optional_nogps_is_correlated_without_creating_geometry(self):
        analysis = analyze_log_lines(self.lines, self.lines[4:6])

        self.assertIsNotNone(analysis.nogps_correlation)
        self.assertEqual(2, len(analysis.nogps_correlation.matched))
        self.assertEqual(5, analysis.without_geometry_count)

    def test_empty_daily_log_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "neobsahuje žádné měření"):
            analyze_log_lines(["# empty"])


if __name__ == "__main__":
    unittest.main()

