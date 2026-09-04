"""Tests for the local, non-networked SÚRO readiness checks."""

import unittest
from datetime import datetime, timezone

from czechrad_studio.segments import MeasurementSegment, SegmentType
from czechrad_studio.suro import assess_mission, assess_segment


def _segment(**changes):
    values = {
        "id": "segment-1",
        "source_log_id": "source-1",
        "mission_id": "mission-1",
        "start": datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc),
        "segment_type": SegmentType.WALKING,
        "title": "Pěší měření",
        "status": "confirmed",
        "include_in_suro": True,
        "detector_height_m": 1.0,
        "detector_orientation": "dolů",
        "route_description": "Park a okolní ulice",
        "notes": "",
    }
    values.update(changes)
    return MeasurementSegment(**values)


class SuroReadinessTest(unittest.TestCase):
    def test_complete_segment_is_ready(self):
        result = assess_segment(_segment())

        self.assertTrue(result.included)
        self.assertTrue(result.ready)
        self.assertEqual((), result.missing)
        self.assertEqual("Připraveno", result.label)

    def test_missing_user_confirmed_fields_are_reported(self):
        result = assess_segment(
            _segment(
                segment_type=SegmentType.UNCLASSIFIED,
                detector_height_m=None,
                detector_orientation="",
                route_description="",
            )
        )

        self.assertFalse(result.ready)
        self.assertEqual(
            (
                "zvolit způsob měření",
                "výška detektoru",
                "orientace detektoru",
                "popis trasy nebo místa",
            ),
            result.missing,
        )

    def test_segment_not_selected_for_suro_needs_no_metadata(self):
        result = assess_segment(
            _segment(
                include_in_suro=False,
                detector_height_m=None,
                detector_orientation="",
                route_description="",
            )
        )

        self.assertFalse(result.included)
        self.assertFalse(result.ready)
        self.assertEqual((), result.missing)
        self.assertEqual("Nezahrnout", result.label)

    def test_mission_summary_separates_ready_and_incomplete(self):
        summary = assess_mission(
            (
                _segment(id="ready"),
                _segment(id="missing", detector_height_m=None),
                _segment(id="excluded", include_in_suro=False),
            )
        )

        self.assertEqual(3, summary.total_count)
        self.assertEqual(2, summary.included_count)
        self.assertEqual(1, summary.ready_count)
        self.assertEqual(1, summary.incomplete_count)


if __name__ == "__main__":
    unittest.main()
