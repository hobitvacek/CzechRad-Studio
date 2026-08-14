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
            raise ValueError("NÃ¡zev mise nesmÃ­ bÃ½t prÃ¡zdnÃ½.")
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
            raise ValueError("DennÃ­ LOG musÃ­ obsahovat prÃ¡vÄ› jedno zaÅ™Ã­zenÃ­.")
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
                 ã¿=¶‰ËkºwµçU1PÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ°•¹‘•‘}…Ñ}ÕÑŒ(€€€€€€€€€€€€€€€€€€€I=4Í½ÕÉ•}±½}É•Ù¥Í¥½¹Ì(€€€€€€€€€€€€€€€€€€€]!IÍ½ÕÉ•}±½}¥€ô€ü9É•½É‘¥¹}¥€ô€ü(€€€€€€€€€€€€€€€€€€€€€9¥Í}ÕÉÉ•¹Ğ€ô€Ä(€€€€€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€€€€€¡Í½ÕÉ•}±½}¥°É•½É‘¥¹}¥¤°(€€€€€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¤(€€€€€€€€€€€€€€€¥˜É•½É‘¥¹œ¥Ì9½¹”è(€€€€€€€€€€€€€€€€€€€É…¥Í”-•åÉÉ½È ‰Yå‰É…»¤·oe•»´¹•‰å±¼¹…±•é•¹¼¸ˆ¤(€€€€€€€€€€€€€€€É•½É‘¥¹}ÍÑ…ÉĞ€ô}Á…ÉÍ•}‘…Ñ•Ñ¥µ”¡É•½É‘¥¹l‰ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ‰t¤(€€€€€€€€€€€€€€€É•½É‘¥¹}•¹€ô}Á…ÉÍ•}‘…Ñ•Ñ¥µ”¡É•½É‘¥¹l‰•¹‘•‘}…Ñ}ÕÑŒ‰t¤(€€€€€€€€€€€€€€€¥˜É•½É‘¥¹}ÍÑ…ÉĞ¥Ì9½¹”½ÈÉ•½É‘¥¹}•¹¥Ì9½¹”è(€€€€€€€€€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È ‰Yå‰É…»¤·oe•»´¹•·„Á±…Ñ»ôƒ5…Í½ÛôÉ½éÍ… ¸ˆ¤(€€€€€€€€€€€€€€€¥˜ÍÑ…ÉĞ€ğÉ•½É‘¥¹}ÍÑ…ÉĞ½È•¹€øÉ•½É‘¥¹}•¹è(€€€€€€€€€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È (€€€€€€€€€€€€€€€€€€€€€€€€‹1…Í½Û¤¡É…¹¥”ƒéÍ•­ÔµÕÏ´±—ù•ĞÕÙ¹¥ÓdÙå‰É…»¥¡¼·oe•»´¸ˆ(€€€€€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±•Ñ•‘}É•½É‘¥¹}¥€ôÉ•½É‘¥¹}¥(€€€€€€€€€€€½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€%9MIP%9Q<µ•…ÍÕÉ•µ•¹Ñ}Í•µ•¹ÑÌ(€€€€€€€€€€€€€€€€¡¥°Í½ÕÉ•}±½}¥°É•½É‘¥¹}¥°µ¥ÍÍ¥½¹}¥°ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ°(€€€€€€€€€€€€€€€€•¹‘•‘}…Ñ}ÕÑŒ°Í•µ•¹Ñ}ÑåÁ”°Ñ¥Ñ±”°ÍÑ…ÑÕÌ°¥¹±Õ‘•}¥¹}ÍÕÉ¼°(€€€€€€€€€€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´°‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸°É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸°(€€€€€€€€€€€€€€€€¹½Ñ•Ì°É•…Ñ•‘}…Ñ}ÕÑŒ°ÕÁ‘…Ñ•‘}…Ñ}ÕÑŒ¤(€€€€€€€€€€€€€€€Y1UL€ ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü¤(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€€€€Í•µ•¹Ñ}¥°Í½ÕÉ•}±½}¥°Í•±•Ñ•‘}É•½É‘¥¹}¥°µ¥ÍÍ¥½¹}¥°(€€€€€€€€€€€€€€€€€€€}ÕÑ}Ñ¥µ•ÍÑ…µÀ¡ÍÑ…ÉĞ¤°}ÕÑ}Ñ¥µ•ÍÑ…µÀ¡•¹¤°(€€€€€€€€€€€€€€€€€€€Í•µ•¹Ñ}ÑåÁ”¹Ù…±Õ”°Ñ¥Ñ±”¹ÍÑÉ¥À ¤°ÍÑ…ÑÕÌ°(€€€€€€€€€€€€€€€€€€€¥¹Ğ¡¥¹±Õ‘•}¥¹}ÍÕÉ¼¤°‘•Ñ•Ñ½É}¡•¥¡Ñ}´°(€€€€€€€€€€€€€€€€€€€‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸¹ÍÑÉ¥À ¤°É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸¹ÍÑÉ¥À ¤°(€€€€€€€€€€€€€€€€€€€¹½Ñ•Ì¹ÍÑÉ¥À ¤°¹½Ü°¹½Ü°(€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€¤(€€€€€€€É•ÑÕÉ¸¹•áĞ (€€€€€€€€€€€¥Ñ•´™½È¥Ñ•´¥¸Í•±˜¹±¥ÍÑ}Í•µ•¹ÑÌ¡Í½ÕÉ•}±½}¥¤(€€€€€€€€€€€¥˜¥Ñ•´¹¥€ôôÍ•µ•¹Ñ}¥(€€€€€€€€¤((€€€‘•˜½¹™¥Éµ}Í•µ•¹Ñ}ÁÉ½Á½Í…° (€€€€€€€Í•±˜°(€€€€€€€ÁÉ½Á½Í…±}¥èÍÑÈ°(€€€€€€€µ¥ÍÍ¥½¹}¥èÍÑÈ°(€€€€€€€€¨°(€€€€€€€Í•µ•¹Ñ}ÑåÁ”èM•µ•¹ÑQåÁ”°(€€€€€€€Ñ¥Ñ±”èÍÑÈ€ô€ˆˆ°(€€€€€€€¥¹±Õ‘•}¥¹}ÍÕÉ¼è‰½½°€ôQÉÕ”°(€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´è™±½…Ğğ9½¹”€ô9½¹”°(€€€€€€€‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸èÍÑÈ€ô€ˆˆ°(€€€€€€€É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸èÍÑÈ€ô€ˆˆ°(€€€€€€€¹½Ñ•ÌèÍÑÈ€ô€ˆˆ°(€€€€¤€´ø5•…ÍÕÉ•µ•¹ÑM•µ•¹Ğè(€€€€€€€€ˆˆ‰Ñ½µ¥…±±ä…•ÁĞ„ÕÉÉ•¹ĞÁÉ½Á½Í…°…¹É•…Ñ”„½¹™¥Éµ•Í•µ•¹Ğ¸ˆˆˆ((€€€€€€€¥˜‘•Ñ•Ñ½É}¡•¥¡Ñ}´¥Ì¹½Ğ9½¹”…¹‘•Ñ•Ñ½É}¡•¥¡Ñ}´€ğ€Àè(€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È ‰[÷…­„‘•Ñ•­Ñ½ÉÔ¹•Í·´‹õĞë…Á½É»„¸ˆ¤(€€€€€€€Í•µ•¹Ñ}¥€ôÍÑÈ¡ÕÕ¥Ğ ¤¤(€€€€€€€¹½Ü€ôÕÑ}¹½İ}Ñ•áĞ ¤(€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É½Ü€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1PÀ¸¨°È¹É•½É‘¥¹}¥I=4Í•µ•¹Ñ}ÁÉ½Á½Í…±ÌÀ(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}±½}É•Ù¥Í¥½¹ÌÈ(€€€€€€€€€€€€€€€€€€€=8È¹¥€ôÀ¹É•Ù¥Í¥½¹}¥9È¹¥Í}ÕÉÉ•¹Ğ€ô€Ä(€€€€€€€€€€€€€€€)=%8µ¥ÍÍ¥½¹}Í½ÕÉ•}±½ÌµÌ(€€€€€€€€€€€€€€€€€€€=8µÌ¹Í½ÕÉ•}±½}¥€ôÀ¹Í½ÕÉ•}±½}¥(€€€€€€€€€€€€€€€€€€9µÌ¹µ¥ÍÍ¥½¹}¥€ô€ü(€€€€€€€€€€€€€€€]!IÀ¹¥€ô€ü9À¹ÍÑ…ÑÕÌ€ô€Á•¹‘¥¹œœ(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡µ¥ÍÍ¥½¹}¥°ÁÉ½Á½Í…±}¥¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¤(€€€€€€€€€€€¥˜É½Ü¥Ì9½¹”è(€€€€€€€€€€€€€€€É…¥Í”-•åÉÉ½È (€€€€€€€€€€€€€€€€€€€€‰;…ÙÉ ¹•‰å°¹…±•é•¸°×ø‰å°éÁÉ…½Û…¸¹•‰¼¹•Á…Óg´€ˆ(€€€€€€€€€€€€€€€€€€€€‰‘¼…­Ñ¥Ù»´µ¥Í”¸ˆ(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€¥˜É½İl‰ÁÉ½Á½Í…±}ÑåÁ”‰t€ôôAÉ½Á½Í…±QåÁ”¹I=I%9}@¹Ù…±Õ”è(€€€€€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È (€€€€€€€€€€€€€€€€€€€€‰5•é•É„Øë…é¹…µÔ©”Á½Õé”»…ÙÉ ¡É…¹¥”°¹”·oe¥´ƒéÍ•¬¸ˆ(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€%9MIP%9Q<µ•…ÍÕÉ•µ•¹Ñ}Í•µ•¹ÑÌ(€€€€€€€€€€€€€€€€¡¥°Í½ÕÉ•}±½}¥°É•½É‘¥¹}¥°µ¥ÍÍ¥½¹}¥°ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ°(€€€€€€€€€€€€€€€€•¹‘•‘}…Ñ}ÕÑŒ°Í•µ•¹Ñ}ÑåÁ”°Ñ¥Ñ±”°ÍÑ…ÑÕÌ°¥¹±Õ‘•}¥¹}ÍÕÉ¼°(€€€€€€€€€€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´°‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸°É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸°(€€€€€€€€€€€€€€€€¹½Ñ•Ì°É•…Ñ•‘}…Ñ}ÕÑŒ°ÕÁ‘…Ñ•‘}…Ñ}ÕÑŒ¤(€€€€€€€€€€€€€€€Y1UL€ ü°€ü°€ü°€ü°€ü°€ü°€ü°€ü°€½¹™¥Éµ•œ°€ü°€ü°€ü°€ü°€ü°€ü°€ü¤(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€€€€Í•µ•¹Ñ}¥°É½İl‰Í½ÕÉ•}±½}¥‰t°É½İl‰É•½É‘¥¹}¥‰t°(€€€€€€€€€€€€€€€€€€€µ¥ÍÍ¥½¹}¥°(€€€€€€€€€€€€€€€€€€€É½İl‰ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ‰t°É½İl‰•¹‘•‘}…Ñ}ÕÑŒ‰t°(€€€€€€€€€€€€€€€€€€€Í•µ•¹Ñ}ÑåÁ”¹Ù…±Õ”°Ñ¥Ñ±”¹ÍÑÉ¥À ¤°¥¹Ğ¡¥¹±Õ‘•}¥¹}ÍÕÉ¼¤°(€€€€€€€€€€€€€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´°‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸¹ÍÑÉ¥À ¤°(€€€€€€€€€€€€€€€€€€€É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸¹ÍÑÉ¥À ¤°¹½Ñ•Ì¹ÍÑÉ¥À ¤°¹½Ü°¹½Ü°(€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€¤(€€€€€€€€€€€½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€UAQÍ•µ•¹Ñ}ÁÉ½Á½Í…±Ì(€€€€€€€€€€€€€€€MPÍÑ…ÑÕÌ€ô€…•ÁÑ•œ°É•Í½±Ù•‘}Í•µ•¹Ñ}¥€ô€ü°(€€€€€€€€€€€€€€€€€€€É•Í½±Ù•‘}…Ñ}ÕÑŒ€ô€ü(€€€€€€€€€€€€€€€]!I¥€ô€ü(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡Í•µ•¹Ñ}¥°¹½Ü°ÁÉ½Á½Í…±}¥¤°(€€€€€€€€€€€€¤(€€€€€€€É•ÑÕÉ¸¹•áĞ (€€€€€€€€€€€Í•µ•¹Ğ(€€€€€€€€€€€™½ÈÍ•µ•¹Ğ¥¸Í•±˜¹±¥ÍÑ}Í•µ•¹ÑÌ¡É½İl‰Í½ÕÉ•}±½}¥‰t¤(€€€€€€€€€€€¥˜Í•µ•¹Ğ¹¥€ôôÍ•µ•¹Ñ}¥(€€€€€€€€¤((€€€‘•˜‘¥Íµ¥ÍÍ}Í•µ•¹Ñ}ÁÉ½Á½Í…°¡Í•±˜°ÁÉ½Á½Í…±}¥èÍÑÈ¤€´ø9½¹”è(€€€€€€€€ˆˆ‰5…É¬½¹”Á•¹‘¥¹œÁÉ½Á½Í…°…Ì¥¹Ñ•¹Ñ¥½¹…±±äÍ­¥ÁÁ•¸ˆˆˆ((€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€ÕÉÍ½È€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€UAQÍ•µ•¹Ñ}ÁÉ½Á½Í…±Ì(€€€€€€€€€€€€€€€MPÍÑ…ÑÕÌ€ô€‘¥Íµ¥ÍÍ•œ°É•Í½±Ù•‘}…Ñ}ÕÑŒ€ô€ü(€€€€€€€€€€€€€€€]!I¥€ô€ü9ÍÑ…ÑÕÌ€ô€Á•¹‘¥¹œœ(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡ÕÑ}¹½İ}Ñ•áĞ ¤°ÁÉ½Á½Í…±}¥¤°(€€€€€€€€€€€€¤(€€€€€€€€€€€¥˜ÕÉÍ½È¹É½İ½Õ¹Ğ€„ô€Äè(€€€€€€€€€€€€€€€É…¥Í”-•åÉÉ½È ‰;…ÙÉ ¹•‰å°¹…±•é•¸¹•‰¼×ø‰å°éÁÉ…½Û…¸¸ˆ¤((€€€‘•˜±¥ÍÑ}ÁÉ½Á½Í…±}Á½Í¥Ñ¥½¹Ì (€€€€€€€Í•±˜°ÁÉ½Á½Í…±}¥èÍÑÈ(€€€€¤€´øÑÕÁ±•mÑÕÁ±•m™±½…Ğ°™±½…Ñt°€¸¸¹tè(€€€€€€€€ˆˆ‰I•ÑÕÉ¸ÑÉÕÍÑ•ÕÉÉ•¹ĞµÉ•Ù¥Í¥½¸µ…ÀÁ½Í¥Ñ¥½¹Ì¥¹Í¥‘”„ÁÉ½Á½Í…°¸((€€€€€€€½½É‘¥¹…Ñ•Ì…É”É•ÑÕÉ¹•…Ì€¡±½¹¥ÑÕ‘”°±…Ñ¥ÑÕ‘”¥€Í¼Ñ¡”E%L(€€€€€€€ÁÉ•Í•¹Ñ…Ñ¥½¸±…å•È…¸É•…Ñ”]L€àĞ•½µ•ÑÉ¥•Ìİ¥Ñ¡½ÕĞ‘•Á•¹‘¥¹œ½¸(€€€€€€€‘…Ñ…‰…Í”¥µÁ±•µ•¹Ñ…Ñ¥½¸‘•Ñ…¥±Ì¸(€€€€€€€€ˆˆˆ((€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É½Ü€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1PÀ¹É•Ù¥Í¥½¹}¥°À¹ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ°À¹•¹‘•‘}…Ñ}ÕÑŒ(€€€€€€€€€€€€€€€I=4Í•µ•¹Ñ}ÁÉ½Á½Í…±ÌÀ(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}±½}É•Ù¥Í¥½¹ÌÈ(€€€€€€€€€€€€€€€€€€€=8È¹¥€ôÀ¹É•Ù¥Í¥½¹}¥9È¹¥Í}ÕÉÉ•¹Ğ€ô€Ä(€€€€€€€€€€€€€€€]!IÀ¹¥€ô€ü(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡ÁÉ½Á½Í…±}¥°¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¤(€€€€€€€€€€€¥˜É½Ü¥Ì9½¹”è(€€€€€€€€€€€€€€€É…¥Í”-•åÉÉ½È ‰;…ÙÉ ¹•‰å°¹…±•é•¸Ø…­Ñ×…±»´É•Ù¥é¤1=Ô¸ˆ¤(€€€€€€€€€€€Á½Í¥Ñ¥½¹Ì€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1P±½¹¥ÑÕ‘”°±…Ñ¥ÑÕ‘”I=4µ•…ÍÕÉ•µ•¹ÑÌ(€€€€€€€€€€€€€€€]!IÉ•Ù¥Í¥½¹}¥€ô€ü(€€€€€€€€€€€€€€€€€9µ•…ÍÕÉ•‘}…Ñ}ÕÑŒ	Q]8€ü9€ü(€€€€€€€€€€€€€€€€€9±…Ñ¥ÑÕ‘”%L9=P9U109±½¹¥ÑÕ‘”%L9=P9U10(€€€€€€€€€€€€€€€€€9±½…Ñ¥½¹}ÅÕ…±¥Ñä€ô€ü(€€€€€€€€€€€€€€€=IH	dµ•…ÍÕÉ•‘}…Ñ}ÕÑŒ°Í•ÅÕ•¹•}¹¼(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€€€€É½İl‰É•Ù¥Í¥½¹}¥‰t°É½İl‰ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ‰t°(€€€€€€€€€€€€€€€€€€€É½İl‰•¹‘•‘}…Ñ}ÕÑŒ‰t°1½…Ñ¥½¹EÕ…±¥Ñä¹Y1%¹Ù…±Õ”°(€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸ÑÕÁ±” (€€€€€€€€€€€€¡Á½Í¥Ñ¥½¹l‰±½¹¥ÑÕ‘”‰t°Á½Í¥Ñ¥½¹l‰±…Ñ¥ÑÕ‘”‰t¤(€€€€€€€€€€€™½ÈÁ½Í¥Ñ¥½¸¥¸Á½Í¥Ñ¥½¹Ì(€€€€€€€€¤((€€€‘•˜±¥ÍÑ}Í•µ•¹ÑÌ¡Í•±˜°Í½ÕÉ•}±½}¥èÍÑÈ¤€´øÑÕÁ±•m5•…ÍÕÉ•µ•¹ÑM•µ•¹Ğ°€¸¸¹tè(€€€€€€€€ˆˆ‰1¥ÍĞÍÑ…‰±”ÕÍ•ÈÍ•µ•¹ÑÌ¥¹‘•Á•¹‘•¹Ñ±ä™É½´…ÕÑ½µ…Ñ¥ŒÁÉ½Á½Í…±Ì¸ˆˆˆ((€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É½İÌ€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1PµÌ¸¨°(€€€€€€€€€€€€€€€€€€€€€€M]!8ÍÈ¹Í•ÅÕ•¹•}¹¼€ø€Ä(€€€€€€€€€€€€€€€€€€€€€€€€€€€Q!8ÍÈ¹½É¥¥¹…±}™¥±•¹…µ”ñğ€œ€¡·oe•»´€œñğ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€ÍÈ¹Í•ÅÕ•¹•}¹¼ñğ€œ¤œ(€€€€€€€€€€€€€€€€€€€€€€€€€€€1MÍÈ¹½É¥¥¹…±}™¥±•¹…µ”9L½É¥¥¹…±}™¥±•¹…µ”°(€€€€€€€€€€€€€€€€€€€€€€Ì¹±½¥…±}‘…Ñ”(€€€€€€€€€€€€€€€I=4µ•…ÍÕÉ•µ•¹Ñ}Í•µ•¹ÑÌµÌ(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}±½ÌÌ=8Ì¹¥€ôµÌ¹Í½ÕÉ•}±½}¥(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}É•½É‘¥¹ÌÍÈ=8ÍÈ¹¥€ôµÌ¹É•½É‘¥¹}¥(€€€€€€€€€€€€€€€]!IµÌ¹Í½ÕÉ•}±½}¥€ô€ü(€€€€€€€€€€€€€€€=IH	dÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ°•¹‘•‘}…Ñ}ÕÑŒ°¥(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡Í½ÕÉ•}±½}¥°¤°(€€€€€€€€€€€€¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸ÑÕÁ±”¡Í•±˜¹}Í•µ•¹Ñ}™É½µ}É½Ü¡É½Ü¤™½ÈÉ½Ü¥¸É½İÌ¤((€€€ÍÑ…Ñ¥µ•Ñ¡½(€€€‘•˜}Í•µ•¹Ñ}™É½µ}É½Ü¡É½ÜèÍÅ±¥Ñ”Ì¹I½Ü¤€´ø5•…ÍÕÉ•µ•¹ÑM•µ•¹Ğè(€€€€€€€É•ÑÕÉ¸5•…ÍÕÉ•µ•¹ÑM•µ•¹Ğ (€€€€€€€€€€€¥õÉ½İl‰¥‰t°Í½ÕÉ•}±½}¥õÉ½İl‰Í½ÕÉ•}±½}¥‰t°(€€€€€€€€€€€µ¥ÍÍ¥½¹}¥õÉ½İl‰µ¥ÍÍ¥½¹}¥‰t°(€€€€€€€€€€€ÍÑ…ÉĞõ}Á…ÉÍ•}‘…Ñ•Ñ¥µ”¡É½İl‰ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ‰t¤°(€€€€€€€€€€€•¹õ}Á…ÉÍ•}‘…Ñ•Ñ¥µ”¡É½İl‰•¹‘•‘}…Ñ}ÕÑŒ‰t¤°(€€€€€€€€€€€Í•µ•¹Ñ}ÑåÁ”õM•µ•¹ÑQåÁ”¡É½İl‰Í•µ•¹Ñ}ÑåÁ”‰t¤°(€€€€€€€€€€€Ñ¥Ñ±”õÉ½İl‰Ñ¥Ñ±”‰t°ÍÑ…ÑÕÌõÉ½İl‰ÍÑ…ÑÕÌ‰t°(€€€€€€€€€€€¥¹±Õ‘•}¥¹}ÍÕÉ¼õ‰½½°¡É½İl‰¥¹±Õ‘•}¥¹}ÍÕÉ¼‰t¤°(€€€€€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´õÉ½İl‰‘•Ñ•Ñ½É}¡•¥¡Ñ}´‰t°(€€€€€€€€€€€‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸õÉ½İl‰‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸‰t°(€€€€€€€€€€€É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸õÉ½İl‰É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸‰t°¹½Ñ•ÌõÉ½İl‰¹½Ñ•Ì‰t°(€€€€€€€€€€€Í½ÕÉ•}¹…µ”õÉ½İl‰½É¥¥¹…±}™¥±•¹…µ”‰t°(€€€€€€€€€€€±½¥…±}‘…Ñ”õÉ½İl‰±½¥…±}‘…Ñ”‰t°(€€€€€€€€¤((€€€‘•˜±¥ÍÑ}µ¥ÍÍ¥½¹}Í•µ•¹ÑÌ (€€€€€€€Í•±˜°µ¥ÍÍ¥½¹}¥èÍÑÈ(€€€€¤€´øÑÕÁ±•m5•…ÍÕÉ•µ•¹ÑM•µ•¹Ğ°€¸¸¹tè(€€€€€€€€ˆˆ‰1¥ÍĞÍÑ…‰±”½¹™¥Éµ•½È‘É…™ĞÍ•µ•¹ÑÌ¥¸½¹”µ¥ÍÍ¥½¸¸ˆˆˆ((€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É½İÌ€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1PµÌ¸¨°(€€€€€€€€€€€€€€€€€€€€€€M]!8ÍÈ¹Í•ÅÕ•¹•}¹¼€ø€Ä(€€€€€€€€€€€€€€€€€€€€€€€€€€€Q!8ÍÈ¹½É¥¥¹…±}™¥±•¹…µ”ñğ€œ€¡·oe•»´€œñğ(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€ÍÈ¹Í•ÅÕ•¹•}¹¼ñğ€œ¤œ(€€€€€€€€€€€€€€€€€€€€€€€€€€€1MÍÈ¹½É¥¥¹…±}™¥±•¹…µ”9L½É¥¥¹…±}™¥±•¹…µ”°(€€€€€€€€€€€€€€€€€€€€€€Ì¹±½¥…±}‘…Ñ”(€€€€€€€€€€€€€€€I=4µ•…ÍÕÉ•µ•¹Ñ}Í•µ•¹ÑÌµÌ(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}±½ÌÌ=8Ì¹¥€ôµÌ¹Í½ÕÉ•}±½}¥(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}É•½É‘¥¹ÌÍÈ=8ÍÈ¹¥€ôµÌ¹É•½É‘¥¹}¥(€€€€€€€€€€€€€€€]!IµÌ¹µ¥ÍÍ¥½¹}¥€ô€ü(€€€€€€€€€€€€€€€=IH	dÌ¹±½¥…±}‘…Ñ”°µÌ¹ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ°µÌ¹•¹‘•‘}…Ñ}ÕÑŒ°µÌ¹¥(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡µ¥ÍÍ¥½¹}¥°¤°(€€€€€€€€€€€€¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÑÕÉ¸ÑÕÁ±”¡Í•±˜¹}Í•µ•¹Ñ}™É½µ}É½Ü¡É½Ü¤™½ÈÉ½Ü¥¸É½İÌ¤((€€€‘•˜ÕÁ‘…Ñ•}Í•µ•¹Ğ (€€€€€€€Í•±˜°(€€€€€€€Í•µ•¹Ñ}¥èÍÑÈ°(€€€€€€€€¨°(€€€€€€€Í•µ•¹Ñ}ÑåÁ”èM•µ•¹ÑQåÁ”°(€€€€€€€Ñ¥Ñ±”èÍÑÈ€ô€ˆˆ°(€€€€€€€¥¹±Õ‘•}¥¹}ÍÕÉ¼è‰½½°€ôQÉÕ”°(€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´è™±½…Ğğ9½¹”€ô9½¹”°(€€€€€€€‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸èÍÑÈ€ô€ˆˆ°(€€€€€€€É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸èÍÑÈ€ô€ˆˆ°(€€€€€€€¹½Ñ•ÌèÍÑÈ€ô€ˆˆ°(€€€€¤€´ø5•…ÍÕÉ•µ•¹ÑM•µ•¹Ğè(€€€€€€€€ˆˆ‰UÁ‘…Ñ”ÕÍ•Èµ½İ¹•µ•Ñ…‘…Ñ„İ¥Ñ¡½ÕĞ¡…¹¥¹œÍ•µ•¹Ğ‰½Õ¹‘…É¥•Ì¸ˆˆˆ((€€€€€€€¥˜‘•Ñ•Ñ½É}¡•¥¡Ñ}´¥Ì¹½Ğ9½¹”…¹‘•Ñ•Ñ½É}¡•¥¡Ñ}´€ğ€Àè(€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È ‰[÷…­„‘•Ñ•­Ñ½ÉÔ¹•Í·´‹õĞë…Á½É»„¸ˆ¤(€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É½Ü€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€‰M1PÍ½ÕÉ•}±½}¥I=4µ•…ÍÕÉ•µ•¹Ñ}Í•µ•¹ÑÌ]!I¥€ô€üˆ°(€€€€€€€€€€€€€€€€¡Í•µ•¹Ñ}¥°¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¤(€€€€€€€€€€€¥˜É½Ü¥Ì9½¹”è(€€€€€€€€€€€€€€€É…¥Í”-•åÉÉ½È ‹iÍ•¬¹•‰å°¹…±•é•¸¸ˆ¤(€€€€€€€€€€€½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€UAQµ•…ÍÕÉ•µ•¹Ñ}Í•µ•¹ÑÌ(€€€€€€€€€€€€€€€MPÍ•µ•¹Ñ}ÑåÁ”€ô€ü°Ñ¥Ñ±”€ô€ü°¥¹±Õ‘•}¥¹}ÍÕÉ¼€ô€ü°(€€€€€€€€€€€€€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´€ô€ü°‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸€ô€ü°(€€€€€€€€€€€€€€€€€€€É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸€ô€ü°¹½Ñ•Ì€ô€ü°ÕÁ‘…Ñ•‘}…Ñ}ÕÑŒ€ô€ü(€€€€€€€€€€€€€€€]!I¥€ô€ü(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€€€€Í•µ•¹Ñ}ÑåÁ”¹Ù…±Õ”°Ñ¥Ñ±”¹ÍÑÉ¥À ¤°¥¹Ğ¡¥¹±Õ‘•}¥¹}ÍÕÉ¼¤°(€€€€€€€€€€€€€€€€€€€‘•Ñ•Ñ½É}¡•¥¡Ñ}´°‘•Ñ•Ñ½É}½É¥•¹Ñ…Ñ¥½¸¹ÍÑÉ¥À ¤°(€€€€€€€€€€€€€€€€€€€É½ÕÑ•}‘•ÍÉ¥ÁÑ¥½¸¹ÍÑÉ¥À ¤°¹½Ñ•Ì¹ÍÑÉ¥À ¤°ÕÑ}¹½İ}Ñ•áĞ ¤°(€€€€€€€€€€€€€€€€€€€Í•µ•¹Ñ}¥°(€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€¤(€€€€€€€É•ÑÕÉ¸¹•áĞ (€€€€€€€€€€€¥Ñ•´™½È¥Ñ•´¥¸Í•±˜¹±¥ÍÑ}Í•µ•¹ÑÌ¡É½İl‰Í½ÕÉ•}±½}¥‰t¤(€€€€€€€€€€€¥˜¥Ñ•´¹¥€ôôÍ•µ•¹Ñ}¥(€€€€€€€€¤((€€€‘•˜±¥ÍÑ}Í•µ•¹Ñ}Á½Í¥Ñ¥½¹Ì (€€€€€€€Í•±˜°Í•µ•¹Ñ}¥èÍÑÈ(€€€€¤€´øÑÕÁ±•mÑÕÁ±•m™±½…Ğ°™±½…Ñt°€¸¸¹tè(€€€€€€€€ˆˆ‰I•ÑÕÉ¸ÕÉÉ•¹Ğµ…ÀÁ½Í¥Ñ¥½¹Ì™½È½¹”ÍÑ…‰±”Í•µ•¹Ğ¸((€€€€€€€%˜„ALµ±½ÍÌÍ•µ•¹Ğ¡…Ì¹¼ÕÍ…‰±”•½µ•ÑÉä°¥ÑÌ½É¥¥¹…°ÁÉ½Á½Í…°(€€€€€€€…¹¡½È¥ÌÉ•ÑÕÉ¹•Í¼Ñ¡”ÕÍ•È…¸ÍÑ¥±°±½…Ñ”Ñ¡”±¥­•±ä•¹ÑÉ…¹”¸(€€€€€€€€ˆˆˆ((€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É½Ü€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1PµÌ¹Í½ÕÉ•}±½}¥°µÌ¹É•½É‘¥¹}¥°µÌ¹ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ°(€€€€€€€€€€€€€€€€€€€€€€µÌ¹•¹‘•‘}…Ñ}ÕÑŒ°(€€€€€€€€€€€€€€€€€€€€€€À¹•¹Ñ•É}±½¹¥ÑÕ‘”°À¹•¹Ñ•É}±…Ñ¥ÑÕ‘”(€€€€€€€€€€€€€€€I=4µ•…ÍÕÉ•µ•¹Ñ}Í•µ•¹ÑÌµÌ(€€€€€€€€€€€€€€€1P)=%8Í•µ•¹Ñ}ÁÉ½Á½Í…±ÌÀ(€€€€€€€€€€€€€€€€€€€=8À¹É•Í½±Ù•‘}Í•µ•¹Ñ}¥€ôµÌ¹¥(€€€€€€€€€€€€€€€]!IµÌ¹¥€ô€ü(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡Í•µ•¹Ñ}¥°¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¤(€€€€€€€€€€€¥˜É½Ü¥Ì9½¹”è(€€€€€€€€€€€€€€€É…¥Í”-•åÉÉ½È ‹iÍ•¬¹•‰å°¹…±•é•¸¸ˆ¤(€€€€€€€€€€€Á½Í¥Ñ¥½¹Ì€ô½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1P´¹±½¹¥ÑÕ‘”°´¹±…Ñ¥ÑÕ‘”I=4µ•…ÍÕÉ•µ•¹ÑÌ´(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}±½}É•Ù¥Í¥½¹ÌÈ=8È¹¥€ô´¹É•Ù¥Í¥½¹}¥(€€€€€€€€€€€€€€€]!IÈ¹Í½ÕÉ•}±½}¥€ô€ü9È¹É•½É‘¥¹}¥€ô€ü(€€€€€€€€€€€€€€€€€9È¹¥Í}ÕÉÉ•¹Ğ€ô€Ä(€€€€€€€€€€€€€€€€€9´¹µ•…ÍÕÉ•‘}…Ñ}ÕÑŒ	Q]8€ü9€ü(€€€€€€€€€€€€€€€€€9´¹±…Ñ¥ÑÕ‘”%L9=P9U109´¹±½¹¥ÑÕ‘”%L9=P9U10(€€€€€€€€€€€€€€€€€9´¹±½…Ñ¥½¹}ÅÕ…±¥Ñä€ô€ü(€€€€€€€€€€€€€€€=IH	d´¹µ•…ÍÕÉ•‘}…Ñ}ÕÑŒ°´¹Í•ÅÕ•¹•}¹¼(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€€€€É½İl‰Í½ÕÉ•}±½}¥‰t°É½İl‰É•½É‘¥¹}¥‰t°(€€€€€€€€€€€€€€€€€€€É½İl‰ÍÑ…ÉÑ•‘}…Ñ}ÕÑŒ‰t°É½İl‰•¹‘•‘}…Ñ}ÕÑŒ‰t°(€€€€€€€€€€€€€€€€€€€1½…Ñ¥½¹EÕ…±¥Ñä¹Y1%¹Ù…±Õ”°(€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€¤¹™•Ñ¡…±° ¤(€€€€€€€É•ÍÕ±Ğ€ôÑÕÁ±” (€€€€€€€€€€€€¡Á½Í¥Ñ¥½¹l‰±½¹¥ÑÕ‘”‰t°Á½Í¥Ñ¥½¹l‰±…Ñ¥ÑÕ‘”‰t¤(€€€€€€€€€€€™½ÈÁ½Í¥Ñ¥½¸¥¸Á½Í¥Ñ¥½¹Ì(€€€€€€€€¤(€€€€€€€¥˜É•ÍÕ±Ğè(€€€€€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ğ(€€€€€€€¥˜É½İl‰•¹Ñ•É}±½¹¥ÑÕ‘”‰t¥Ì¹½Ğ9½¹”è(€€€€€€€€€€€É•ÑÕÉ¸€ ¡É½İl‰•¹Ñ•É}±½¹¥ÑÕ‘”‰t°É½İl‰•¹Ñ•É}±…Ñ¥ÑÕ‘”‰t¤°¤(€€€€€€€É•ÑÕÉ¸€ ¤((€€€‘•˜ÕÉÉ•¹Ñ}µ•…ÍÕÉ•µ•¹Ñ}½Õ¹Ğ¡Í•±˜°Í½ÕÉ•}±½}¥èÍÑÈ¤€´ø¥¹Ğè(€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É•ÑÕÉ¸½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€ˆˆˆ(€€€€€€€€€€€€€€€M1P=U9P ¨¤I=4µ•…ÍÕÉ•µ•¹ÑÌ´(€€€€€€€€€€€€€€€)=%8Í½ÕÉ•}±½}É•Ù¥Í¥½¹ÌÈ=8È¹¥€ô´¹É•Ù¥Í¥½¹}¥(€€€€€€€€€€€€€€€]!IÈ¹Í½ÕÉ•}±½}¥€ô€ü9È¹¥Í}ÕÉÉ•¹Ğ€ô€Ä(€€€€€€€€€€€€€€€€ˆˆˆ°(€€€€€€€€€€€€€€€€¡Í½ÕÉ•}±½}¥°¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¥lÁt((€€€‘•˜É•Ù¥Í¥½¹}½Õ¹Ğ¡Í•±˜°Í½ÕÉ•}±½}¥èÍÑÈ¤€´ø¥¹Ğè(€€€€€€€İ¥Ñ Í•±˜¹}½¹¹•Ñ¥½¸ ¤…Ì½¹¹•Ñ¥½¸è(€€€€€€€€€€€µ¥É…Ñ”¡½¹¹•Ñ¥½¸¤(€€€€€€€€€€€É•ÑÕÉ¸½¹¹•Ñ¥½¸¹•á•ÕÑ” (€€€€€€€€€€€€€€€€‰M1P=U9P ¨¤I=4Í½ÕÉ•}±½}É•Ù¥Í¥½¹Ì]!IÍ½ÕÉ•}±½}¥€ô€üˆ°(€€€€€€€€€€€€€€€€¡Í½ÕÉ•}±½}¥°¤°(€€€€€€€€€€€€¤¹™•Ñ¡½¹” ¥lÁt