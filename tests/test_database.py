"""Integration tests for the portable GeoPackage project repository."""

import shutil
import sqlite3
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

from czechrad_studio.database import (
    GeoPackageRepository,
    ImportDisposition,
    SCHEMA_VERSION,
)
from czechrad_studio.database.schema import GPKG_APPLICATION_ID
from czechrad_studio.importer import analyze_log_files, calculate_checksum
from czechrad_studio.segments import ProposalType, SegmentType


FIXTURE = Path(__file__).parent / "fixtures" / "czechrad_sample.log"


class GeoPackageRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.track = self.root / "07960717.LOG"
        shutil.copyfile(FIXTURE, self.track)
        self.database = self.root / "CzechRad_test.gpkg"
        self.repository = GeoPackageRepository(self.database)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initializes_versioned_geopackage_idempotently(self):
        self.assertEqual(SCHEMA_VERSION, self.repository.initialize())
        self.assertEqual(SCHEMA_VERSION, self.repository.initialize())

        connection = sqlite3.connect(str(self.database))
        try:
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            contents = {
                row[0]
                for row in connection.execute("SELECT table_name FROM gpkg_contents")
            }
            device_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(devices)")
            }
        finally:
            connection.close()

        self.assertEqual(GPKG_APPLICATION_ID, application_id)
        self.assertIn("measurements", contents)
        self.assertIn("missions", contents)
        self.assertIn("segment_proposals", contents)
        self.assertIn("measurement_segments", contents)
        self.assertIn("device_type", device_columns)
        self.assertIn("device_family", device_columns)
        self.assertIn("calibration_cpm_per_usvh", device_columns)

    def test_import_stores_detected_device_metadata(self):
        analysis = analyze_log_files(self.track)
        self.repository.store_import(analysis, self.track)

        connection = sqlite3.connect(str(self.database))
        try:
            row = connection.execute(
                "SELECT device_type, device_family, calibration_cpm_per_usvh FROM devices"
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual("CZRA1", row[0])
        self.assertEqual("CzechRad", row[1])
        self.assertAlmostEqual(328.5, row[2])

    def test_creates_and_lists_missions(self):
        mission = self.repository.create_mission(
            "Víkend v Ostravě", "Pěší měření ve více denních LOGech"
        )

        self.assertEqual("Víkend v Ostravě", mission.name)
        self.assertEqual("active", mission.status)
        self.assertEqual((mission,), self.repository.list_missions())

    def test_user_segment_survives_new_log_revision(self):
        mission = self.repository.create_mission("Úseky")
        analysis = analyze_log_files(self.track)
        stored = self.repository.store_import(
            analysis, self.track, mission_id=mission.id
        )
        times = [item.timestamp for item in analysis.track.measurements]
        segment = self.repository.create_segment(
            stored.source_log_id, min(times), max(times), mission_id=mission.id,
            segment_type=SegmentType.WALKING, title="Pěší část",
        )

        with self.track.open("a", encoding="utf-8") as handle:
            handle.write("\n# expanded daily revision\n")
        revised = self.repository.store_import(
            analyze_log_files(self.track), self.track, mission_id=mission.id
        )

        self.assertEqual(ImportDisposition.REVISED, revised.disposition)
        segments = self.repository.list_segments(stored.source_log_id)
        self.assertEqual(1, len(segments))
        self.assertEqual(segment.id, segments[0].id)
        self.assertEqual(SegmentType.WALKING, segments[0].segment_type)
        self.assertEqual(timezone.utc, segments[0].start.tzinfo)

    def test_recording_gap_proposal_is_stored_for_current_revision(self):
        gap_track = self.root / "07960722.LOG"
        payloads = (
            "CZRA1,TEST,2026-07-22T08:00:00Z,40,3,100,A,"
            "5000.0000,N,01400.0000,E,250.00,A,8,100",
            "CZRA1,TEST,2026-07-22T08:10:00Z,41,4,104,A,"
            "5000.0100,N,01400.0100,E,250.00,A,8,100",
        )
        gap_track.write_text(
            "\n".join(
                f"${payload}*{calculate_checksum(payload):X}"
                for payload in payloads
            ) + "\n",
            encoding="utf-8",
        )

        stored = self.repository.store_import(
            analyze_log_files(gap_track), gap_track
        )
        proposals = self.repository.list_current_segment_proposals(
            stored.source_log_id
        )

        self.assertEqual(1, stored.proposal_count)
        self.assertEqual(1, len(proposals))
        self.assertEqual(ProposalType.RECORDING_GAP, proposals[0].proposal_type)
        self.assertEqual(stored.revision_id, proposals[0].revision_id)

    def test_same_import_is_not_duplicated_and_changed_file_is_revision(self):
        mission = self.repository.create_mission("Testovací mise")
        analysis = analyze_log_files(self.track)

        first = self.repository.store_import(
            analysis, self.track, mission_id=mission.id
        )
        second = self.repository.store_import(
            analysis, self.track, mission_id=mission.id
        )

        self.assertEqual(ImportDisposition.CREATED, first.disposition)
        self.assertEqual(ImportDisposition.UNCHANGED, second.disposition)
        self.assertEqual(first.revision_id, second.revision_id)
        self.assertEqual(1, self.repository.revision_count(first.source_log_id))
        self.assertEqual(5, self.repository.current_measurement_count(first.source_log_id))

        with self.track.open("a", encoding="utf-8") as handle:
            handle.write("\n# later card copy of the same daily log\n")
        revised_analysis = analyze_log_files(self.track)
        revised = self.repository.store_import(
            revised_analysis, self.track, mission_id=mission.id
        )

        self.assertEqual(ImportDisposition.REVISED, revised.disposition)
        self.assertEqual(first.source_log_id, revised.source_log_id)
        self.assertNotEqual(first.revision_id, revised.revision_id)
        self.assertEqual(2, self.repository.revision_count(first.source_log_id))
        self.assertEqual(5, self.repository.current_measurement_count(first.source_log_id))

    def test_tracks_mission_range_and_stores_no_raw_gps_lines(self):
        mission = self.repository.create_mission("Audit")
        analysis = analyze_log_files(self.track)
        stored = self.repository.store_import(
            analysis, self.track, mission_id=mission.id
        )
        updated = self.repository.get_mission(mission.id)

        self.assertIsNotNone(updated.started_at_utc)
        self.assertIsNotNone(updated.ended_at_utc)
        self.assertEqual(2026, updated.started_at_utc.year)

        connection = sqlite3.connect(str(self.database))
        try:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(measurements)")
            }
            attached = connection.execute(
                "SELECT COUNT(*) FROM mission_source_logs WHERE mission_id = ?",
                (mission.id,),
            ).fetchone()[0]
            hashes = connection.execute(
                "SELECT raw_line_sha256 FROM measurements WHERE revision_id = ?",
                (stored.revision_id,),
            ).fetchall()
        finally:
            connection.close()

        self.assertNotIn("raw_line", columns)
        self.assertEqual(1, attached)
        self.assertTrue(all(len(row[0]) == 64 for row in hashes))

    def test_unknown_mission_rolls_back_import(self):
        analysis = analyze_log_files(self.track)
        with self.assertRaises(KeyError):
            self.repository.store_import(
                analysis, self.track, mission_id="missing-mission"
            )

        connection = sqlite3.connect(str(self.database))
        try:
            count = connection.execute("SELECT COUNT(*) FROM source_logs").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(0, count)

    def test_unrelated_growth_of_cumulative_nogps_does_not_revise_old_day(self):
        mission = self.repository.create_mission("NOGPS mise")
        nogps = self.root / "NOGPS.LOG"
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        nogps.write_text("\n".join(lines[4:6]) + "\n", encoding="utf-8")
        analysis = analyze_log_files(self.track, nogps)
        first = self.repository.store_import(
            analysis, self.track, nogps_path=nogps, mission_id=mission.id
        )

        with nogps.open("a", encoding="utf-8") as handle:
            handle.write("# unrelated later-day NOGPS data would follow\n")
        unchanged_analysis = analyze_log_files(self.track, nogps)
        second = self.repository.store_import(
            unchanged_analysis, self.track, nogps_path=nogps, mission_id=mission.id
        )

        self.assertEqual(ImportDisposition.UNCHANGED, second.disposition)
        self.assertEqual(first.revision_id, second.revision_id)
        self.assertEqual(1, self.repository.revision_count(first.source_log_id))


if __name__ == "__main__":
    unittest.main()
