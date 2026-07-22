"""Transactional persistence for CzechRad projects and daily imports."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from ..core.models import MeasurementValidation, TimeQuality
from ..importer.session import ImportAnalysis
from ..importer.validation import validate_measurement
from ..missions.model import Mission
from .schema import SCHEMA_VERSION, migrate, utc_now_text


PARSER_VERSION = "czechrad-log-2"


class ImportDisposition(str, Enum):
    CREATED = "created"
    REVISED = "revised"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class StoredImport:
    source_log_id: str
    revision_id: str
    disposition: ImportDisposition
    measurement_count: int


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


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

        device_ids = {item.device_id for item in analysis.track.measurements}
        if len(device_ids) != 1:
            raise ValueError("Denní LOG musí obsahovat právě jedno zařízení.")
        device_serial = next(iter(device_ids))
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
        revision_id = ""

        measurement_count = len(analysis.track_validations) + len(matched_nogps)

        connection = self._connect()
        try:
            migrate(connection)
            with connection:
                if mission_id is not None and connection.execute(
                    "SELECT 1 FROM missions WHERE id = ?", (mission_id,)
                ).fetchone() is None:
                    raise KeyError(f"Mise {mission_id} nebyla nalezena.")

                connection.execute(
                    "INSERT OR IGNORE INTO devices(serial, model, created_at_utc) VALUES (?, 'CzechRad', ?)",
                    (device_serial, imported_at),
                )
                device_id = connection.execute(
                    "SELECT id FROM devices WHERE serial = ?", (device_serial,)
                ).fetchone()[0]
                existing_source = connection.execute(
                    "SELECT id FROM source_logs WHERE device_id = ? AND logical_date = ?",
                    (device_id, analysis.expected_date.isoformat()),
                ).fetchone()
                created = existing_source is None
                if created:
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
                    SELECT id, measurement_count FROM source_log_revisions
                    WHERE source_log_id = ? AND content_sha256 = ?
                      AND COALESCE(nogps_sha256, '') = COALESCE(?, '')
                    """,
                    (source_log_id, content_sha, nogps_sha),
                ).fetchone()
                if same is not None:
                    self._attach_mission(connection, mission_id, source_log_id, started, ended, imported_at)
                    return StoredImport(
                        source_log_id=source_log_id,
                        revision_id=same["id"],
                        disposition=ImportDisposition.UNCHANGED,
                        measurement_count=same["measurement_count"],
                    )

                had_revision = connection.execute(
                    "SELECT 1 FROM source_log_revisions WHERE source_log_id = ? LIMIT 1",
                    (source_log_id,),
                ).fetchone() is not None
                connection.execute(
                    "UPDATE source_log_revisions SET is_current = 0 WHERE source_log_id = ?",
                    (source_log_id,),
                )
                revision_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO source_log_revisions
                    (id, source_log_id, content_sha256, nogps_sha256, source_path,
                     source_filename, size_bytes, modified_at_utc, parser_version,
                     imported_at_utc, started_at_utc, ended_at_utc,
                     measurement_count, parse_failure_count, is_current)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        revision_id, source_log_id, content_sha, nogps_sha,
                        str(track_file), track_file.name, stat.st_size, modified,
                        PARSER_VERSION, imported_at, started, ended,
                        measurement_count, analysis.failure_count,
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
                connection.execute(
                    "UPDATE source_logs SET updated_at_utc = ? WHERE id = ?",
                    (imported_at, source_log_id),
                )
                self._attach_mission(connection, mission_id, source_log_id, started, ended, imported_at)
                return StoredImport(
                    source_log_id=source_log_id,
                    revision_id=revision_id,
                    disposition=ImportDisposition.REVISED if had_revision else ImportDisposition.CREATED,
                    measurement_count=measurement_count,
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
