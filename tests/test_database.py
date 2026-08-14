"""Integration tests for the portable GeoPackage project repository."""

import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from czechrad_studio.database import (
    GeoPackageRepository,
    ImportDisposition,
    SCHEMA_VERSION,
)
from czechrad_studio.database import schema as schema_module
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
            proposal_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(segment_proposals)"
                )
            }
            revision_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(source_log_revisions)"
                )
            }
            recording_tables = connection.execute(
                """
                SELECT COUNT(*) FROM sqlite_master
                WHERE type = 'table' AND name = 'source_recordings'
                """
            ).fetchone()[0]
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
        self.assertIn("status", proposal_columns)
        self.assertIn("resolved_segment_id", proposal_columns)
        self.assertIn("recording_id", revision_columns)
        self.assertEqual(1, recording_tables)

    def test_migrates_existing_version_4_data_to_first_recording(self):
        legacy_database = self.root / "CzechRad_v4.gpkg"
        connection = sqlite3.connect(str(legacy_database))
        try:
            schema_module._create_geopackage_core(connection)
            schema_module._migration_1(connection)
            schema_module._migration_2(connection)
            schema_module._migration_3(connection)
            schema_module._migration_4(connection)
            now = "2026-07-17T18:00:00+00:00"
            connection.execute(
                """
                INSERT INTO devices
                (id, serial, model, created_at_utc, device_type, device_family,
                 calibration_cpm_per_usvh)
                VALUES (1, '0796', 'CzechRad', ?, 'CZRA1', 'CzechRad', 328.5)
                """,
                (now,),
            )
            connection.execute(
                """
                INSERT INTO source_logs
                (id, device_id, logical_date, original_filename,
                 created_at_utc, updated_at_utc)
                VALUES ('log-1', 1, '2026-07-17', '07960717.LOG', ?, ?)
                """,
                (now, now),
            )
            connection.execute(
                """
                INSERT INTO source_log_revisions
                (id, source_log_id, content_sha256, nogps_sha256, source_path,
                 source_filename, size_bytes, modified_at_utc, parser_version,
                 imported_at_utc, started_at_utc, ended_at_utc,
                 measurement_count, parse_failure_count, is_current)
                VALUES ('revision-1', 'log-1', ?, NULL, 'D:/07960717.LOG',
                        '07960717.LOG', 123, ?, '0.5.2', ?, ?, ?, 5, 0, 1)
                """,
                ("a" * 64, now, now, now, "2026-07-17T18:00:20+00:00"),
            )
            connection.execute(
                """
                INSERT INTO measurement_segments
                (id, source_log_id, mission_id, started_at_utc, ended_at_utc,
                 segment_type, title, status, include_in_suro,
                 detector_height_m, detector_orientation, route_description,
                 notes, created_at_utc, updated_at_utc)
                VALUES ('segment-1', 'log-1', NULL, ?, ?, 'walking',
                        'Starç¡ £sek', 'confirmed', 1, 1.0, 'dol…',
                        'Testovac¡ trasa', '', ?, ?)
                """,
                (now, "2026-07-17T18:00:20+00:00", now, now),
            )
            connection.commit()
        finally:
            connection.close()

        repository = GeoPackageRepository(legacy_database)
        self.assertEqual(SCHEMA_VERSION, repository.initialize())

        connection = sqlite3.connect(str(legacy_database))
        try:
            recording = connection.execute(
                """
                SELECT id, source_log_id, sequence_no, original_filename
                FROM source_recordings
                """
            ).fetchone()
            revision_recording = connection.execute(
                "SELECT recording_id, is_current FROM source_log_revisions"
            ).fetchone()
            segment_recording = connection.execute(
                "SELECT recording_id FROM measurement_segments"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(
            ("legacy-log-1", "log-1", 1, "07960717.LOG"), recording
        )
        self.assertEqual(("legacy-log-1", 1), revision_recording)
        self.assertEqual("legacy-log-1", segment_recording)

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
            "V¡kend v OstravØ", "PØç¡ mØýen¡ ve v¡ce denn¡ch LOGech"
        )

        self.assertEqual("V¡kend v OstravØ", mission.name)
        self.assertEqual("active", mission.status)
        self.assertEqual((mission,), self.repository.list_missions())

    def test_user_segment_survives_new_log_revision(self):
        mission = self.repository.create_mission("éseky")
        analysis = analyze_log_files(self.track)
        stored = self.repository.store_import(
            analysis, self.track, mission_id=mission.id
        )
        times = [item.timestamp for item in analysis.track.measurements]
        segment = self.repository.create_segment(
            stored.source_log_id, min(times), max(times), mission_id=mission.id,
            segment_type=SegmentType.WALKING, title="PØç¡ Ÿ st",
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

    def test_mission_proposal_can_be_confirmed_with_suro_metadata(self):
        stationary_track = self.root / "07960723.LOG"
        start = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)
        timestamps = tuple(
            (start + timedelta(seconds=5 * index)).strftime("%H:%M:%S")
            for index in range(37)
        )
        payloads = tuple(
            f"CZRA1,TEST,2026-07-23T{at}Z,40,3,{100 + index},A,"
            "5000.0000,N,01400.0000,E,250.00,A,8,100"
            for index, at in enumerate(timestamps)
        )
        stationary_track.write_text(
            "\n".join(
                f"${payload}*{calculate_checksum(payload):X}"
                for payload in payloads
            ) + "\n",
            encoding="utf-8",
        )
        mission = self.repository.create_mission("Kontrola £sek…")
        stored = self.repository.store_import(
            analyze_log_files(stationary_track),
            stationary_track,
            mission_id=mission.id,
        )

        proposals = self.repository.list_mission_segment_proposals(mission.id)
        self.assertEqual(1, len(proposals))
        self.assertEqual(ProposalType.STATIONARY, proposals[0].proposal_type)
        self.assertEqual("07960723.LOG", proposals[0].source_name)
        self.assertEqual("2026-07-23", proposals[0].logical_date)
        positions = self.repository.list_proposal_positions(proposals[0].id)
        self.assertEqual(37, len(positions))
        self.assertAlmostEqual(14.0, positions[0][0])
        self.assertAlmostEqual(50.0, positions[0][1])

        segment = self.repository.confirm_segment_proposal(
            proposals[0].id,
            mission.id,
            segment_type=SegmentType.STATIONARY,
            title="Kontroln¡ mØýen¡",
            detector_height_m=1.0,
            detector_orientation="dol…",
            route_description="N mØst¡",
            notes="OvØýeno u§ivatelem",
        )

        self.assertEqual(stored.source_log_id, segment.source_log_id)
        self.assertEqual("confirmed", segment.status)
        self.assertEqual(1.0, segment.detector_height_m)
        self.assertEqual("dol…", segment.detector_orientation)
        self.assertEqual((segment,), self.repository.list_mission_segments(mission.id))
        self.assertEqual(
            37, len(self.repository.list_segment_positions(segment.id))
        )

        updated = self.repository.update_segment(
            segment.id,
            segment_type=SegmentType.WALKING,
            title="Opravenì n zev",
            include_in_suro=False,
            detector_height_m=0.8,
            detector_orientation="dopýedu",
            route_description="Opraven  trasa",
            notes="Upraveno po kontrole mapy",
        )
        self.assertEqual(SegmentType.WALKING, updated.segment_type)
        self.assertEqual("Opravenì n zev", updated.title)
        self.assertFalse(updated.include_in_suro)
        self.assertEqual(0.8, updated.detector_height_m)
        self.assertEqual("Opraven  trasa", updated.route_description)
        self.assertEqual((), self.repository.list_mission_segment_proposals(mission.id))
        all_proposals = self.repository.list_mission_segment_proposals(
            mission.id, pending_only=False
        )
        self.assertEqual("accepted", all_proposals[0].status)

    def test_pending_proposal_can_be_dismissed(self):
        mission = self.repository.create_mission("PýeskoŸen¡")
        gap_track = self.root / "07960724.LOG"
        payloads = (
            "CZRA1,TEST,2026-07-24T08:00:00Z,40,3,100,A,"
            "5000.0000,N,01400.0000,E,250.00,A,8,100",
            "CZRA1,TEST,2026-07-24T08:10:00Z,41,4,104,A,"
            "5000.0100,N,01400.0100,E,250.00,A,8,100",
        )
        gap_track.write_text(
            "\n".join(
                f"${payload}*{calculate_checksum(payload):X}"
                for payload in payloads
            ) + "\n",
            encoding="utf-8",
        )
        self.repository.store_import(
            analyze_log_files(gap_track), gap_track, mission_id=mission.id
        )
        proposal = self.repository.list_mission_segment_proposals(mission.id)[0]

        self.repository.dismiss_segment_proposal(proposal.id)

        self.assertEqual((), self.repository.list_mission_segment_proposals(mission.id))
        reviewed = self.repository.list_mission_segment_proposals(
            mission.id, pending_only=False
        )
        self.assertEqual("dismissed", reviewed[0].status)

    def test_same_import_is_not_duplicated_and_changed_file_is_revision(self):
        mission = self.repository.create_mission("Testovac¡ mise")
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

    def test_independent_same_day_recordings_keep_separate_current_revisions(self):
        mission = self.repository.create_mission("DvŲ karty v jednom dni")
        first = self.repository.store_import(
            analyze_log_files(self.track), self.track, mission_id=mission.id
        )

        second_folder = self.root / "second-card"
        second_folder.mkdir()
        second_track = second_folder / self.track.name
        payloads = (
            "CZRA1,TEST,2026-07-17T18:00:00Z,42,3,200,A,"
            "5000.1000,N,01400.1000,E,251.00,A,9,90",
            "CZRA1,TEST,2026-07-17T18:00:05Z,43,4,204,A,"
            "5000.1010,N,01400.1010,E,251.00,A,9,90",
        )
        second_track.write_text(
            "\n".join(
                f"${payload}*{calculate_checksum(payload):X}"
                for payload in payloads
            ) + "\n",
            encoding="utf-8",
        )
        second = self.repository.store_import(
            analyze_log_files(second_track),
            second_track,
            mission_id=mission.id,
        )

        self.assertEqual(ImportDisposition.CREATED, first.disposition)
        self.assertEqual(ImportDisposition.CREATED, second.disposition)
        self.assertEqual(first.source_log_id, second.source_log_id)
        self.assertNotEqual(first.recording_id, second.recording_id)
        self.assertEqual(1, first.recording_sequence)
        self.assertEqual(2, second.recording_sequence)
        self.assertEqual(2, self.repository.revision_count(first.source_log_id))
        self.assertEqual(
            7, self.repository.current_measurement_count(first.source_log_id)
        )

        with self.track.open("a", encoding="utf-8") as handle:
            handle.write("\n# later copy of the first card recording\n")
        revised = self.repository.store_import(
            analyze_log_files(self.track), self.track, mission_id=mission.id
        )

        self.assertEqual(ImportDisposition.REVISED, revised.disposition)
        self.assertEqual(first.recording_id, revised.recording_id)
        self.assertEqual(1, revised.recording_sequence)
        self.assertEqual(3, self.repository.revision_count(first.source_log_id))
        self.assertEqual(
            7, self.repository.current_measurement_count(first.source_log_id)
        )

        connection = sqlite3.connect(str(self.database))
        try:
            recording_count = connection.execute(
                "SELECT COUNT(*) FROM source_recordings"
            ).fetchone()[0]
            current_count = connection.execute(
                "SELECT COUNT(*) FROM source_log_revisions WHERE is_current = 1"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(2, recording_count)
        self.assertEqual(2, current_count)

    def test_manual_segment_targets_selected_same_day_recording(self):
        mission = self.repository.create_mission("RuŸn¡ rozdØlen¡")
        first = self.repository.store_import(
            analyze_log_files(self.track), self.track, mission_id=mission.id
        )

        second_folder = self.root / "overlapping-card"
        second_folder.mkdir()
        second_track = second_folder / self.track.name
        payloads = (
            "CZRA1,TEST,2026-07-17T15:08:43Z,42,3,200,A,"
            "5000.1000,N,01400.1000,E,251.00,A,9,90",
            "CZRA1,TEST,2026-07-17T15:08:48Z,43,4,204,A,"
            "5000.1010,N,01400.1010,E,251.00,A,9,90",
        )
        second_track.write_text(
            "\n".join(
                f"${payload}*{calculate_checksum(payload):X}"
                for payload in payloads
            ) + "\n",
            encoding="utf-8",
        )
        second = self.repository.store_import(
            analyze_log_files(second_track),
            second_track,
            mission_id=mission.id,
        )

        recordings = self.repository.list_mission_recordings(mission.id)
        self.assertEqual(2, len(recordings))
        selected = next(
            item for item in recordings if item.recording_id == second.recording_id
        )
        self.assertIn("mØýen¡ 2", selected.source_name)

        segment = self.repository.create_segment(
            first.source_log_id,
            selected.start,
            selected.end,
            mission_id=mission.id,
            recording_id=selected.recording_id,
            segment_type=SegmentType.WALKING,
            title="Druh  karta",
            status="confirmed",
        )

        self.assertEqual("Druh  karta", segment.title)
        self.assertIn("mØýen¡ 2", segment.source_name)
        with self.assertRaises(ValueError):
            self.repository.create_segment(
                first.source_log_id,
                selected.start - timedelta(seconds=1),
                selected.end,
                mission_id=mission.id,
                recording_id=selected.recording_id,
            )

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
