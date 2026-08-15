"""Transactional persistence for CzechRad projects and daily imports."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from uuid import uuid4

from ..core.models import LocationQuality, MeasurementValidation, TimeQuality
from ..importer.session import ImportAnalysis
from ..importer.validation import validate_measurement
from ..missions.model import Mission
from ..segments import (
    MeasurementSegment,
    ProposalType,
    SegmentProposal,
    SegmentType,
    propose_segments,
)
from .schema import SCHEMA_VERSION, migrate, utc_now_text


PARSER_VERSION = "czechrad-log-2"


class ImportDisposition(str, Enum):
    CREATED = "created"
    REVISED = "revised"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class StoredImport:
    source_log_id: str
    recording_id: str
    recording_sequence: int
    revision_id: str
    disposition: ImportDisposition
    measurement_count: int
    proposal_count: int


@dataclass(frozen=True)
class CurrentRecording:
    """One current recording available for manual segment creation."""

    source_log_id: str
    recording_id: str
    recording_sequence: int
    source_name: str
    logical_date: str
    start: datetime
    end: datetime
    measurement_count: int


@dataclass(frozen=True)
class NearestMeasurement:
    """Trusted measurement selected by snapping a map click to a recording."""

    source_log_id: str
    recording_id: str
    source_name: str
    logical_date: str
    measured_at: datetime
    longitude: float
    latitude: float
    distance_m: float


@dataclass(frozen=True)
class UnassignedMeasurements:
    """Current mission measurements not covered by any user segment."""

    total_count: int
    unassigned_count: int
    mapped_count: int
    positions: tuple[tuple[float, float], ...]


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _distance_m(
    first_longitude: float,
    first_latitude: float,
    second_longitude: float,
    second_latitude: float,
) -> float:
    """Return great-circle distance suitable for map-click snapping."""

    latitude_delta = radians(second_latitude - first_latitude)
    longitude_delta = radians(second_longitude - first_longitude)
    first_latitude_rad = radians(first_latitude)
    second_latitude_rad = radians(second_latitude)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(first_latitude_rad)
        * cos(second_latitude_rad)
        * sin(longitude_delta / 2) ** 2
    )
    return 2 * 6_371_000 * asin(sqrt(haversine))


def _sha256_file(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _matched_nogps_sha(measurements) -> str | None:
    """Identify only NOGPS records relevant to this day, not the cumulative file."""

    if not measurements:
        return None
    digest = hashlib.sha256()
    for measurement in measurements:
        digest.update(measurement.raw_line.encode("utf-8", errors="replace"))
        digest.update(b"\n")
    return digest.hexdigest()


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class GeoPackageRepository:
    """Own one local CzechRad Studio GeoPackage."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> int:
        with self._connection() as connection:
            return migrate(connection)

    @property
    def schema_version(self) -> int:
        with self._connection() as connection:
            migrate(connection)
            return connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM crs_schema_migrations"
            ).fetchone()[0]

    def create_mission(self, name: str, description: str = "") -> Mission:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Název mise nesmí být prázdný.")
        mission_id = str(uuid4())
        now = utc_now_text()
        with self._connection() as connection:
            migrate(connection)
            connection.execute(
                """
                INSERT INTO missions
                (id, name, description, status, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (mission_id, clean_name, description.strip(), now, now),
            )
        return self.get_mission(mission_id)

    def get_mission(self, mission_id: str) -> Mission:
        with self._connection() as connection:
            migrate(connection)
            row = connection.execute(
                "SELECT * FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Mise {mission_id} nebyla nalezena.")
        return self._mission_from_row(row)

    def list_missions(self) -> tuple[Mission, ...]:
        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                "SELECT * FROM missions ORDER BY created_at_utc, name"
            ).fetchall()
        return tuple(self._mission_from_row(row) for row in rows)

    @staticmethod
    def _mission_from_row(row: sqlite3.Row) -> Mission:
        return Mission(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=row["status"],
            started_at_utc=_parse_datetime(row["started_at_utc"]),
            ended_at_utc=_parse_datetime(row["ended_at_utc"]),
            created_at_utc=_parse_datetime(row["created_at_utc"]),
            updated_at_utc=_parse_datetime(row["updated_at_utc"]),
        )

    def store_import(
        self,
        analysis: ImportAnalysis,
        track_path: str | Path,
        nogps_path: str | Path | None = None,
        mission_id: str | None = None,
    ) -> StoredImport:
        """Store one immutable daily revision and optionally attach it to a mission."""

        track_file = Path(track_path).resolve()
        nogps_file = Path(nogps_path).resolve() if nogps_path else None
        if not track_file.is_file():
            raise FileNotFoundError(track_file)
        if nogps_file is not None and not nogps_file.is_file():
            raise FileNotFoundError(nogps_file)

        devices = {
            (item.device_id, item.device_type) for item in analysis.track.measurements
        }
        if len(devices) != 1:
            raise ValueError("Denní LOG musí obsahovat právě jedno zařízení.")
        device_serial, device_type = next(iter(devices))
        first_measurement = analysis.track.measurements[0]
        matched_nogps = (
            analysis.nogps_correlation.matched
            if analysis.nogps_correlation is not None
            else ()
        )
        content_sha = _sha256_file(track_file)
        # NOGPS.LOG is cumulative. New records from another date must not create
        # false revisions of every older daily log.
        nogps_sha = _matched_nogps_sha(matched_nogps)
        stat = track_file.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        imported_at = utc_now_text()
        timestamps = [
            result.measurement.timestamp
            for result in analysis.track_validations
            if result.time_quality is TimeQuality.VALID
        ]
        started = _utc_timestamp(min(timestamps)) if timestamps else None
        ended = _utc_timestamp(max(timestamps)) if timestamps else None
        source_log_id = ""
        recording_id = ""
        recording_sequence = 0
        revision_id = ""

        measurement_count = len(analysis.track_validations) + len(matched_nogps)
        proposals = propose_segments(analysis)

        connection = self._connect()
        try:
            migrate(connection)
            with connection:
                if mission_id is not None and connection.execute(
                    "SELECT 1 FROM missions WHERE id = ?", (mission_id,)
                ).fetchone() is None:
                    raise KeyError(f"Mise {mission_id} nebyla nalezena.")

                connection.execute(
                    """
                    INSERT OR IGNORE INTO devices
                    (serial, model, created_at_utc, device_type, device_family,
                     calibration_cpm_per_usvh)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_serial, first_measurement.device_family, imported_at,
                        device_type, first_measurement.device_family,
                        first_measurement.cpm_per_usvh,
                    ),
                )
                connection.execute(
                    """
                    UPDATE devices SET model = ?, device_type = ?, device_family = ?,
                        calibration_cpm_per_usvh = ? WHERE serial = ?
                    """,
                    (
                        first_measurement.device_family, device_type,
                        first_measurement.device_family,
                        first_measurement.cpm_per_usvh, device_serial,
                    ),
                )
                device_id = connection.execute(
                    "SELECT id FROM devices WHERE serial = ?", (device_serial,)
                ).fetchone()[0]
                existing_source = connection.execute(
                    "SELECT id FROM source_logs WHERE device_id = ? AND logical_date = ?",
                    (device_id, analysis.expected_date.isoformat()),
                ).fetchone()
                if existing_source is None:
                    source_log_id = str(uuid4())
                    connection.execute(
                        """
                        INSERT INTO source_logs
                        (id, device_id, logical_date, original_filename, created_at_utc, updated_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (source_log_id, device_id, analysis.expected_date.isoformat(), track_file.name, imported_at, imported_at),
                    )
                else:
                    source_log_id = existing_source["id"]

                same = connection.execute(
                    """
                    SELECT r.id, r.measurement_count, r.recording_id,
                           sr.sequence_no
                    FROM source_log_revisions r
                    JOIN source_recordings sr ON sr.id = r.recording_id
                    WHERE r.source_log_id = ? AND r.content_sha256 = ?
                      AND COALESCE(nogps_sha256, '') = COALESCE(?, '')
                    """,
                    (source_log_id, content_sha, nogps_sha),
                ).fetchone()
                if same is not None:
                    self._attach_mission(connection, mission_id, source_log_id, started, ended, imported_at)
                    return StoredImport(
                        source_log_id=source_log_id,
                        recording_id=same["recording_id"],
                        recording_sequence=same["sequence_no"],
                        revision_id=same["id"],
                        disposition=ImportDisposition.UNCHANGED,
                        measurement_count=same["measurement_count"],
                        proposal_count=connection.execute(
                            "SELECT COUNT(*) FROM segment_proposals WHERE revision_id = ?",
                            (same["id"],),
                        ).fetchone()[0],
                    )

                new_hashes = {
                    hashlib.sha256(
                        result.measurement.raw_line.encode(
                            "utf-8", errors="replace"
                        )
                    ).hexdigest()
                    for result in analysis.track_validations
                }
                current_rows = connection.execute(
                    """
                    SELECT r.recording_id, sr.sequence_no, m.raw_line_sha256
                    FROM source_log_revisions r
                    JOIN source_recordings sr ON sr.id = r.recording_id
                    LEFT JOIN measurements m
                      ON m.revision_id = r.id AND m.record_kind = 'track'
                    WHERE r.source_log_id = ? AND r.is_current = 1
                    """,
                    (source_log_id,),
                ).fetchall()
                overlaps = {}
                sequences = {}
                for row in current_rows:
                    sequences[row["recording_id"]] = row["sequence_no"]
                    if row["raw_line_sha256"] in new_hashes:
                        overlaps[row["recording_id"]] = (
                            overlaps.get(row["recording_id"], 0) + 1
                        )
                if overlaps:
                    recording_id = max(
                        overlaps,
                        key=lambda candidate: (
                            overlaps[candidate], -sequences[candidate]
                        ),
                    )
                    recording_sequence = sequences[recording_id]
                else:
                    recording_sequence = connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence_no), 0) + 1
                        FROM source_recordings WHERE source_log_id = ?
                        """,
                        (source_log_id,),
                    ).fetchone()[0]
                    recording_id = str(uuid4())
                    connection.execute(
                        """
                        INSERT INTO source_recordings
                        (id, source_log_id, sequence_no, original_filename,
                         started_at_utc, ended_at_utc, created_at_utc,
                         updated_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            recording_id, source_log_id, recording_sequence,
                            track_file.name, started, ended, imported_at,
                            imported_at,
                        ),
                    )

                had_revision = connection.execute(
                    "SELECT 1 FROM source_log_revisions "
                    "WHERE recording_id = ? LIMIT 1",
                    (recording_id,),
                ).fetchone() is not None
                connection.execute(
                    "UPDATE source_log_revisions SET is_current = 0 "
                    "WHERE recording_id = ?",
                    (recording_id,),
                )
                revision_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO source_log_revisions
                    (id, source_log_id, recording_id, content_sha256,
                     nogps_sha256, source_path, source_filename, size_bytes,
                     modified_at_utc, parser_version, imported_at_utc,
                     started_at_utc, ended_at_utc, measurement_count,
                     parse_failure_count, is_current)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        revision_id, source_log_id, recording_id, content_sha,
                        nogps_sha, str(track_file), track_file.name,
                        stat.st_size, modified, PARSER_VERSION, imported_at,
                        started, ended, measurement_count,
                        analysis.failure_count,
                    ),
                )
                for sequence, validation in enumerate(analysis.track_validations):
                    self._insert_measurement(connection, revision_id, "track", sequence, validation)
                for sequence, measurement in enumerate(matched_nogps):
                    self._insert_measurement(
                        connection,
                        revision_id,
                        "nogps",
                        sequence,
                        validate_measurement(measurement, expected_date=analysis.expected_date),
                    )
                self._insert_segment_proposals(
                    connection, source_log_id, revision_id, proposals, imported_at
                )
                connection.execute(
                    "UPDATE source_logs SET updated_at_utc = ? WHERE id = ?",
                    (imported_at, source_log_id),
                )
                connection.execute(
                    """
                    UPDATE source_recordings
                    SET original_filename = ?, started_at_utc = ?,
                        ended_at_utc = ?, updated_at_utc = ?
                    WHERE id = ?
                    """,
                    (
                        track_file.name, started, ended, imported_at,
                        recording_id,
                    ),
                )
                self._attach_mission(connection, mission_id, source_log_id, started, ended, imported_at)
                return StoredImport(
                    source_log_id=source_log_id,
                    recording_id=recording_id,
                    recording_sequence=recording_sequence,
                    revision_id=revision_id,
                    disposition=ImportDisposition.REVISED if had_revision else ImportDisposition.CREATED,
                    measurement_count=measurement_count,
                    proposal_count=len(proposals),
                )
        finally:
            connection.close()

    @staticmethod
    def _insert_measurement(
        connection: sqlite3.Connection,
        revision_id: str,
        kind: str,
        sequence: int,
        validation: MeasurementValidation,
    ) -> None:
        item = validation.measurement
        connection.execute(
            """
            INSERT INTO measurements
            (revision_id, record_kind, sequence_no, source_line_number,
             measured_at_utc, cpm, interval_counts, total_counts,
             radiation_status, gps_status, latitude, longitude, altitude_m,
             satellites, hdop_raw, checksum_valid, time_quality,
             location_quality, radiation_valid, validation_issues, raw_line_sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision_id, kind, sequence, item.line_number,
                _utc_timestamp(item.timestamp), item.cpm, item.interval_counts,
                item.total_counts, item.radiation_status, item.gps_status,
                item.latitude, item.longitude, item.altitude_m, item.satellites,
                item.hdop_raw, int(item.checksum_valid), validation.time_quality.value,
                validation.location_quality.value, int(validation.radiation_valid),
                "|".join(validation.issues),
                hashlib.sha256(item.raw_line.encode("utf-8", errors="replace")).hexdigest(),
            ),
        )

    @staticmethod
    def _attach_mission(
        connection: sqlite3.Connection,
        mission_id: str | None,
        source_log_id: str,
        started: str | None,
        ended: str | None,
        now: str,
    ) -> None:
        if mission_id is None:
            return
        connection.execute(
            "INSERT OR IGNORE INTO mission_source_logs(mission_id, source_log_id, attached_at_utc) VALUES (?, ?, ?)",
            (mission_id, source_log_id, now),
        )
        connection.execute(
            """
            UPDATE missions SET
                started_at_utc = CASE
                    WHEN started_at_utc IS NULL OR ? < started_at_utc THEN ?
                    ELSE started_at_utc END,
                ended_at_utc = CASE
                    WHEN ended_at_utc IS NULL OR ? > ended_at_utc THEN ?
                    ELSE ended_at_utc END,
                updated_at_utc = ?
            WHERE id = ?
            """,
            (started, started, ended, ended, now, mission_id),
        )

    @staticmethod
    def _insert_segment_proposals(
        connection: sqlite3.Connection,
        source_log_id: str,
        revision_id: str,
        proposals: tuple[SegmentProposal, ...],
        created_at: str,
    ) -> None:
        for proposal in proposals:
            connection.execute(
                """
                INSERT INTO segment_proposals
                (id, source_log_id, revision_id, proposal_type, started_at_utc,
                 ended_at_utc, confidence, reason, sample_count, center_latitude,
                 center_longitude, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()), source_log_id, revision_id,
                    proposal.proposal_type.value,
                    _utc_timestamp(proposal.start), _utc_timestamp(proposal.end),
                    proposal.confidence, proposal.reason, proposal.sample_count,
                    proposal.center_latitude, proposal.center_longitude, created_at,
                ),
            )

    def list_current_segment_proposals(
        self, source_log_id: str
    ) -> tuple[SegmentProposal, ...]:
        """Return proposals belonging only to the current LOG revision."""

        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                """
                SELECT p.*,
                       CASE WHEN sr.sequence_no > 1
                            THEN sr.original_filename || ' (měření ' ||
                                 sr.sequence_no || ')'
                            ELSE sr.original_filename END AS original_filename,
                       s.logical_date
                FROM segment_proposals p
                JOIN source_log_revisions r ON r.id = p.revision_id
                JOIN source_recordings sr ON sr.id = r.recording_id
                JOIN source_logs s ON s.id = p.source_log_id
                WHERE p.source_log_id = ? AND r.is_current = 1
                ORDER BY p.started_at_utc, p.proposal_type
                """,
                (source_log_id,),
            ).fetchall()
        return tuple(self._proposal_from_row(row) for row in rows)

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> SegmentProposal:
        return SegmentProposal(
            id=row["id"],
            source_log_id=row["source_log_id"],
            revision_id=row["revision_id"],
            proposal_type=ProposalType(row["proposal_type"]),
            start=_parse_datetime(row["started_at_utc"]),
            end=_parse_datetime(row["ended_at_utc"]),
            confidence=row["confidence"],
            reason=row["reason"],
            sample_count=row["sample_count"],
            center_latitude=row["center_latitude"],
            center_longitude=row["center_longitude"],
            source_name=row["original_filename"],
            logical_date=row["logical_date"],
            status=row["status"],
        )

    def list_mission_segment_proposals(
        self, mission_id: str, *, pending_only: bool = True
    ) -> tuple[SegmentProposal, ...]:
        """List proposals from current revisions attached to one mission."""

        status_clause = "AND p.status = 'pending'" if pending_only else ""
        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                f"""
                SELECT p.*,
                       CASE WHEN sr.sequence_no > 1
                            THEN sr.original_filename || ' (měření ' ||
                                 sr.sequence_no || ')'
                            ELSE sr.original_filename END AS original_filename,
                       s.logical_date
                FROM segment_proposals p
                JOIN source_log_revisions r
                    ON r.id = p.revision_id AND r.is_current = 1
                JOIN source_recordings sr ON sr.id = r.recording_id
                JOIN source_logs s ON s.id = p.source_log_id
                JOIN mission_source_logs ms ON ms.source_log_id = s.id
                WHERE ms.mission_id = ? {status_clause}
                ORDER BY s.logical_date, p.started_at_utc, p.proposal_type
                """,
                (mission_id,),
            ).fetchall()
        return tuple(self._proposal_from_row(row) for row in rows)

    def list_mission_recordings(
        self, mission_id: str
    ) -> tuple[CurrentRecording, ...]:
        """List current recording ranges which can be split manually."""

        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                """
                SELECT s.id AS source_log_id, r.recording_id,
                       sr.sequence_no, sr.original_filename, s.logical_date,
                       r.started_at_utc, r.ended_at_utc, r.measurement_count
                FROM mission_source_logs ms
                JOIN source_logs s ON s.id = ms.source_log_id
                JOIN source_recordings sr ON sr.source_log_id = s.id
                JOIN source_log_revisions r
                    ON r.recording_id = sr.id AND r.is_current = 1
                WHERE ms.mission_id = ?
                ORDER BY s.logical_date, r.started_at_utc, sr.sequence_no
                """,
                (mission_id,),
            ).fetchall()
        result = []
        for row in rows:
            start = _parse_datetime(row["started_at_utc"])
            end = _parse_datetime(row["ended_at_utc"])
            if start is None or end is None:
                continue
            source_name = row["original_filename"]
            if row["sequence_no"] > 1:
                source_name += f" (měření {row['sequence_no']})"
            result.append(
                CurrentRecording(
                    source_log_id=row["source_log_id"],
                    recording_id=row["recording_id"],
                    recording_sequence=row["sequence_no"],
                    source_name=source_name,
                    logical_date=row["logical_date"],
                    start=start,
                    end=end,
                    measurement_count=row["measurement_count"],
                )
            )
        return tuple(result)

    def nearest_mission_measurement(
        self,
        mission_id: str,
        longitude: float,
        latitude: float,
        *,
        recording_id: str | None = None,
    ) -> NearestMeasurement:
        """Snap a WGS 84 map position to a trusted current measurement.

        The optional recording filter is used for the second boundary so two
        clicks can never silently combine independent card recordings from
        the same day.
        """

        parameters = [mission_id, LocationQuality.VALID.value]
        recording_clause = ""
        if recording_id is not None:
            recording_clause = " AND r.recording_id = ?"
            parameters.append(recording_id)
        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                f"""
                SELECT s.id AS source_log_id, r.recording_id,
                       sr.sequence_no, sr.original_filename, s.logical_date,
                       m.measured_at_utc, m.longitude, m.latitude
                FROM mission_source_logs ms
                JOIN source_logs s ON s.id = ms.source_log_id
                JOIN source_recordings sr ON sr.source_log_id = s.id
                JOIN source_log_revisions r
                    ON r.recording_id = sr.id AND r.is_current = 1
                JOIN measurements m ON m.revision_id = r.id
                WHERE ms.mission_id = ?
                  AND m.location_quality = ?
                  AND m.longitude IS NOT NULL AND m.latitude IS NOT NULL
                  {recording_clause}
                """,
                tuple(parameters),
            ).fetchall()
        if not rows:
            if recording_id is None:
                raise ValueError(
                    "Aktivní mise nemá žádné platné body pro výběr v mapě."
                )
            raise ValueError(
                "Vybrané měření nemá žádné platné body pro druhou hranici."
            )

        nearest_row = min(
            rows,
            key=lambda row: _distance_m(
                longitude,
                latitude,
                row["longitude"],
                row["latitude"],
            ),
        )
        measured_at = _parse_datetime(nearest_row["measured_at_utc"])
        if measured_at is None:  # The schema requires a value; keep it explicit.
            raise ValueError("Nejbližší měření nemá platný čas UTC.")
        source_name = nearest_row["original_filename"]
        if nearest_row["sequence_no"] > 1:
            source_name += f" (měření {nearest_row['sequence_no']})"
        return NearestMeasurement(
            source_log_id=nearest_row["source_log_id"],
            recording_id=nearest_row["recording_id"],
            source_name=source_name,
            logical_date=nearest_row["logical_date"],
            measured_at=measured_at,
            longitude=nearest_row["longitude"],
            latitude=nearest_row["latitude"],
            distance_m=_distance_m(
                longitude,
                latitude,
                nearest_row["longitude"],
                nearest_row["latitude"],
            ),
        )

    def unassigned_mission_measurements(
        self, mission_id: str
    ) -> UnassignedMeasurements:
        """Return current measurements which are not covered by a segment.

        Records without trusted geometry remain part of the counts, while only
        trusted WGS 84 positions are returned for QGIS highlighting.
        """

        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                """
                SELECT m.longitude, m.latitude, m.location_quality,
                       EXISTS (
                           SELECT 1 FROM measurement_segments segment
                           WHERE segment.mission_id = mission_link.mission_id
                             AND segment.recording_id = revision.recording_id
                             AND m.measured_at_utc BETWEEN
                                 segment.started_at_utc
                                 AND segment.ended_at_utc
                       ) AS is_assigned
                FROM mission_source_logs mission_link
                JOIN source_log_revisions revision
                    ON revision.source_log_id = mission_link.source_log_id
                   AND revision.is_current = 1
                JOIN measurements m ON m.revision_id = revision.id
                WHERE mission_link.mission_id = ?
                ORDER BY m.measured_at_utc, m.sequence_no
                """,
                (mission_id,),
            ).fetchall()
        unassigned = tuple(row for row in rows if not row["is_assigned"])
        positions = tuple(
            (row["longitude"], row["latitude"])
            for row in unassigned
            if row["location_quality"] == LocationQuality.VALID.value
            and row["longitude"] is not None
            and row["latitude"] is not None
        )
        return UnassignedMeasurements(
            total_count=len(rows),
            unassigned_count=len(unassigned),
            mapped_count=len(positions),
            positions=positions,
        )

    @staticmethod
    def _recording_for_interval(
        connection: sqlite3.Connection,
        source_log_id: str,
        start: datetime,
        end: datetime,
    ) -> str:
        """Choose the current recording which best overlaps a manual segment."""

        rows = connection.execute(
            """
            SELECT recording_id, started_at_utc, ended_at_utc
            FROM source_log_revisions
            WHERE source_log_id = ? AND is_current = 1
            """,
            (source_log_id,),
        ).fetchall()
        candidates = []
        for row in rows:
            recording_start = _parse_datetime(row["started_at_utc"])
            recording_end = _parse_datetime(row["ended_at_utc"])
            if recording_start is None or recording_end is None:
                continue
            overlap = (
                min(end, recording_end) - max(start, recording_start)
            ).total_seconds()
            if overlap >= 0:
                candidates.append((overlap, row["recording_id"]))
        if not candidates:
            raise ValueError(
                "Čas úseku nepatří do žádného aktuálního měření tohoto dne."
            )
        return max(candidates, key=lambda item: item[0])[1]

    def create_segment(
        self,
        source_log_id: str,
        start: datetime,
        end: datetime,
        *,
        mission_id: str | None = None,
        recording_id: str | None = None,
        segment_type: SegmentType = SegmentType.UNCLASSIFIED,
        title: str = "",
        status: str = "draft",
        include_in_suro: bool = True,
        detector_height_m: float | None = None,
        detector_orientation: str = "",
        route_description: str = "",
        notes: str = "",
    ) -> MeasurementSegment:
        """Create a stable draft segment which survives later LOG revisions."""

        if end < start:
            raise ValueError("Konec úseku nesmí být před jeho začátkem.")
        if detector_height_m is not None and detector_height_m < 0:
            raise ValueError("Výška detektoru nesmí být záporná.")
        if status not in {"draft", "confirmed", "excluded"}:
            raise ValueError(f"Neznámý stav úseku: {status}")
        segment_id = str(uuid4())
        now = utc_now_text()
        with self._connection() as connection:
            migrate(connection)
            if connection.execute(
                "SELECT 1 FROM source_logs WHERE id = ?", (source_log_id,)
            ).fetchone() is None:
                raise KeyError(f"Zdrojový LOG {source_log_id} nebyl nalezen.")
            if mission_id is not None and connection.execute(
                "SELECT 1 FROM missions WHERE id = ?", (mission_id,)
            ).fetchone() is None:
                raise KeyError(f"Mise {mission_id} nebyla nalezena.")
            if recording_id is None:
                selected_recording_id = self._recording_for_interval(
                    connection, source_log_id, start, end
                )
            else:
                recording = connection.execute(
                    """
                    SELECT started_at_utc, ended_at_utc
                    FROM source_log_revisions
                    WHERE source_log_id = ? AND recording_id = ?
                      AND is_current = 1
                    """,
                    (source_log_id, recording_id),
                ).fetchone()
                if recording is None:
                    raise KeyError("Vybrané měření nebylo nalezeno.")
                recording_start = _parse_datetime(recording["started_at_utc"])
                recording_end = _parse_datetime(recording["ended_at_utc"])
                if recording_start is None or recording_end is None:
                    raise ValueError("Vybrané měření nemá platný časový rozsah.")
                if start < recording_start or end > recording_end:
                    raise ValueError(
                        "Časové hranice úseku musí ležet uvnitř vybraného měření."
                    )
                selected_recording_id = recording_id
            connection.execute(
                """
                INSERT INTO measurement_segments
                (id, source_log_id, recording_id, mission_id, started_at_utc,
                 ended_at_utc, segment_type, title, status, include_in_suro,
                 detector_height_m, detector_orientation, route_description,
                 notes, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    segment_id, source_log_id, selected_recording_id, mission_id,
                    _utc_timestamp(start), _utc_timestamp(end),
                    segment_type.value, title.strip(), status,
                    int(include_in_suro), detector_height_m,
                    detector_orientation.strip(), route_description.strip(),
                    notes.strip(), now, now,
                ),
            )
        return next(
            item for item in self.list_segments(source_log_id)
            if item.id == segment_id
        )

    def confirm_segment_proposal(
        self,
        proposal_id: str,
        mission_id: str,
        *,
        segment_type: SegmentType,
        title: str = "",
        include_in_suro: bool = True,
        detector_height_m: float | None = None,
        detector_orientation: str = "",
        route_description: str = "",
        notes: str = "",
    ) -> MeasurementSegment:
        """Atomically accept a current proposal and create a confirmed segment."""

        if detector_height_m is not None and detector_height_m < 0:
            raise ValueError("Výška detektoru nesmí být záporná.")
        segment_id = str(uuid4())
        now = utc_now_text()
        with self._connection() as connection:
            migrate(connection)
            row = connection.execute(
                """
                SELECT p.*, r.recording_id FROM segment_proposals p
                JOIN source_log_revisions r
                    ON r.id = p.revision_id AND r.is_current = 1
                JOIN mission_source_logs ms
                    ON ms.source_log_id = p.source_log_id
                   AND ms.mission_id = ?
                WHERE p.id = ? AND p.status = 'pending'
                """,
                (mission_id, proposal_id),
            ).fetchone()
            if row is None:
                raise KeyError(
                    "Návrh nebyl nalezen, už byl zpracován nebo nepatří "
                    "do aktivní mise."
                )
            if row["proposal_type"] == ProposalType.RECORDING_GAP.value:
                raise ValueError(
                    "Mezera v záznamu je pouze návrh hranice, ne měřicí úsek."
                )
            connection.execute(
                """
                INSERT INTO measurement_segments
                (id, source_log_id, recording_id, mission_id, started_at_utc,
                 ended_at_utc, segment_type, title, status, include_in_suro,
                 detector_height_m, detector_orientation, route_description,
                 notes, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    segment_id, row["source_log_id"], row["recording_id"],
                    mission_id,
                    row["started_at_utc"], row["ended_at_utc"],
                    segment_type.value, title.strip(), int(include_in_suro),
                    detector_height_m, detector_orientation.strip(),
                    route_description.strip(), notes.strip(), now, now,
                ),
            )
            connection.execute(
                """
                UPDATE segment_proposals
                SET status = 'accepted', resolved_segment_id = ?,
                    resolved_at_utc = ?
                WHERE id = ?
                """,
                (segment_id, now, proposal_id),
            )
        return next(
            segment
            for segment in self.list_segments(row["source_log_id"])
            if segment.id == segment_id
        )

    def dismiss_segment_proposal(self, proposal_id: str) -> None:
        """Mark one pending proposal as intentionally skipped."""

        with self._connection() as connection:
            migrate(connection)
            cursor = connection.execute(
                """
                UPDATE segment_proposals
                SET status = 'dismissed', resolved_at_utc = ?
                WHERE id = ? AND status = 'pending'
                """,
                (utc_now_text(), proposal_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("Návrh nebyl nalezen nebo už byl zpracován.")

    def list_proposal_positions(
        self, proposal_id: str
    ) -> tuple[tuple[float, float], ...]:
        """Return trusted current-revision map positions inside a proposal.

        Coordinates are returned as ``(longitude, latitude)`` so the QGIS
        presentation layer can create WGS 84 geometries without depending on
        database implementation details.
        """

        with self._connection() as connection:
            migrate(connection)
            row = connection.execute(
                """
                SELECT p.revision_id, p.started_at_utc, p.ended_at_utc
                FROM segment_proposals p
                JOIN source_log_revisions r
                    ON r.id = p.revision_id AND r.is_current = 1
                WHERE p.id = ?
                """,
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Návrh nebyl nalezen v aktuální revizi LOGu.")
            positions = connection.execute(
                """
                SELECT longitude, latitude FROM measurements
                WHERE revision_id = ?
                  AND measured_at_utc BETWEEN ? AND ?
                  AND latitude IS NOT NULL AND longitude IS NOT NULL
                  AND location_quality = ?
                ORDER BY measured_at_utc, sequence_no
                """,
                (
                    row["revision_id"], row["started_at_utc"],
                    row["ended_at_utc"], LocationQuality.VALID.value,
                ),
            ).fetchall()
        return tuple(
            (position["longitude"], position["latitude"])
            for position in positions
        )

    def list_segments(self, source_log_id: str) -> tuple[MeasurementSegment, ...]:
        """List stable user segments independently from automatic proposals."""

        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                """
                SELECT ms.*,
                       CASE WHEN sr.sequence_no > 1
                            THEN sr.original_filename || ' (měření ' ||
                                 sr.sequence_no || ')'
                            ELSE sr.original_filename END AS original_filename,
                       s.logical_date
                FROM measurement_segments ms
                JOIN source_logs s ON s.id = ms.source_log_id
                JOIN source_recordings sr ON sr.id = ms.recording_id
                WHERE ms.source_log_id = ?
                ORDER BY started_at_utc, ended_at_utc, id
                """,
                (source_log_id,),
            ).fetchall()
        return tuple(self._segment_from_row(row) for row in rows)

    @staticmethod
    def _segment_from_row(row: sqlite3.Row) -> MeasurementSegment:
        return MeasurementSegment(
            id=row["id"], source_log_id=row["source_log_id"],
            mission_id=row["mission_id"],
            start=_parse_datetime(row["started_at_utc"]),
            end=_parse_datetime(row["ended_at_utc"]),
            segment_type=SegmentType(row["segment_type"]),
            title=row["title"], status=row["status"],
            include_in_suro=bool(row["include_in_suro"]),
            detector_height_m=row["detector_height_m"],
            detector_orientation=row["detector_orientation"],
            route_description=row["route_description"], notes=row["notes"],
            source_name=row["original_filename"],
            logical_date=row["logical_date"],
        )

    def list_mission_segments(
        self, mission_id: str
    ) -> tuple[MeasurementSegment, ...]:
        """List stable confirmed or draft segments in one mission."""

        with self._connection() as connection:
            migrate(connection)
            rows = connection.execute(
                """
                SELECT ms.*,
                       CASE WHEN sr.sequence_no > 1
                            THEN sr.original_filename || ' (měření ' ||
                                 sr.sequence_no || ')'
                            ELSE sr.original_filename END AS original_filename,
                       s.logical_date
                FROM measurement_segments ms
                JOIN source_logs s ON s.id = ms.source_log_id
                JOIN source_recordings sr ON sr.id = ms.recording_id
                WHERE ms.mission_id = ?
                ORDER BY s.logical_date, ms.started_at_utc, ms.ended_at_utc, ms.id
                """,
                (mission_id,),
            ).fetchall()
        return tuple(self._segment_from_row(row) for row in rows)

    def update_segment(
        self,
        segment_id: str,
        *,
        segment_type: SegmentType,
        title: str = "",
        include_in_suro: bool = True,
        detector_height_m: float | None = None,
        detector_orientation: str = "",
        route_description: str = "",
        notes: str = "",
    ) -> MeasurementSegment:
        """Update user-owned metadata without changing segment boundaries."""

        if detector_height_m is not None and detector_height_m < 0:
            raise ValueError("Výška detektoru nesmí být záporná.")
        with self._connection() as connection:
            migrate(connection)
            row = connection.execute(
                "SELECT source_log_id FROM measurement_segments WHERE id = ?",
                (segment_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Úsek nebyl nalezen.")
            connection.execute(
                """
                UPDATE measurement_segments
                SET segment_type = ?, title = ?, include_in_suro = ?,
                    detector_height_m = ?, detector_orientation = ?,
                    route_description = ?, notes = ?, updated_at_utc = ?
                WHERE id = ?
                """,
                (
                    segment_type.value, title.strip(), int(include_in_suro),
                    detector_height_m, detector_orientation.strip(),
                    route_description.strip(), notes.strip(), utc_now_text(),
                    segment_id,
                ),
            )
        return next(
            item for item in self.list_segments(row["source_log_id"])
            if item.id == segment_id
        )

    def list_segment_positions(
        self, segment_id: str
    ) -> tuple[tuple[float, float], ...]:
        """Return current map positions for one stable segment.

        If a GPS-loss segment has no usable geometry, its original proposal
        anchor is returned so the user can still locate the likely entrance.
        """

        with self._connection() as connection:
            migrate(connection)
            row = connection.execute(
                """
                SELECT ms.source_log_id, ms.recording_id, ms.started_at_utc,
                       ms.ended_at_utc,
                       p.center_longitude, p.center_latitude
                FROM measurement_segments ms
                LEFT JOIN segment_proposals p
                    ON p.resolved_segment_id = ms.id
                WHERE ms.id = ?
                """,
                (segment_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Úsek nebyl nalezen.")
            positions = connection.execute(
                """
                SELECT m.longitude, m.latitude FROM measurements m
                JOIN source_log_revisions r ON r.id = m.revision_id
                WHERE r.source_log_id = ? AND r.recording_id = ?
                  AND r.is_current = 1
                  AND m.measured_at_utc BETWEEN ? AND ?
                  AND m.latitude IS NOT NULL AND m.longitude IS NOT NULL
                  AND m.location_quality = ?
                ORDER BY m.measured_at_utc, m.sequence_no
                """,
                (
                    row["source_log_id"], row["recording_id"],
                    row["started_at_utc"], row["ended_at_utc"],
                    LocationQuality.VALID.value,
                ),
            ).fetchall()
        result = tuple(
            (position["longitude"], position["latitude"])
            for position in positions
        )
        if result:
            return result
        if row["center_longitude"] is not None:
            return ((row["center_longitude"], row["center_latitude"]),)
        return ()

    def current_measurement_count(self, source_log_id: str) -> int:
        with self._connection() as connection:
            migrate(connection)
            return connection.execute(
                """
                SELECT COUNT(*) FROM measurements m
                JOIN source_log_revisions r ON r.id = m.revision_id
                WHERE r.source_log_id = ? AND r.is_current = 1
                """,
                (source_log_id,),
            ).fetchone()[0]

    def revision_count(self, source_log_id: str) -> int:
        with self._connection() as connection:
            migrate(connection)
            return connection.execute(
                "SELECT COUNT(*) FROM source_log_revisions WHERE source_log_id = ?",
                (source_log_id,),
            ).fetchone()[0]
