"""Versioned CzechRad Studio schema inside a standards-shaped GeoPackage."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


SCHEMA_VERSION = 3
GPKG_APPLICATION_ID = 0x47504B47
GPKG_USER_VERSION = 10300


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _create_geopackage_core(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS gpkg_spatial_ref_sys (
            srs_name TEXT NOT NULL,
            srs_id INTEGER NOT NULL PRIMARY KEY,
            organization TEXT NOT NULL,
            organization_coordsys_id INTEGER NOT NULL,
            definition TEXT NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS gpkg_contents (
            table_name TEXT NOT NULL PRIMARY KEY,
            data_type TEXT NOT NULL,
            identifier TEXT UNIQUE,
            description TEXT DEFAULT '',
            last_change DATETIME NOT NULL DEFAULT
                (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            min_x DOUBLE,
            min_y DOUBLE,
            max_x DOUBLE,
            max_y DOUBLE,
            srs_id INTEGER,
            CONSTRAINT fk_gc_r_srs_id FOREIGN KEY (srs_id)
                REFERENCES gpkg_spatial_ref_sys(srs_id)
        );
        """
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO gpkg_spatial_ref_sys
        (srs_name, srs_id, organization, organization_coordsys_id, definition, description)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ("Undefined Cartesian", -1, "NONE", -1, "undefined", "undefined Cartesian coordinate reference system"),
            ("Undefined geographic", 0, "NONE", 0, "undefined", "undefined geographic coordinate reference system"),
            ("WGS 84", 4326, "EPSG", 4326, "GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563]],PRIMEM[\"Greenwich\",0],UNIT[\"degree\",0.0174532925199433]]", "longitude/latitude coordinates in decimal degrees on the WGS 84 spheroid"),
        ),
    )


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE crs_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc TEXT NOT NULL
        );

        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL DEFAULT 'CzechRad',
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE missions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'review', 'archived')),
            started_at_utc TEXT,
            ended_at_utc TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE source_logs (
            id TEXT PRIMARY KEY,
            device_id INTEGER NOT NULL REFERENCES devices(id),
            logical_date TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            UNIQUE (device_id, logical_date)
        );

        CREATE TABLE source_log_revisions (
            id TEXT PRIMARY KEY,
            source_log_id TEXT NOT NULL REFERENCES source_logs(id) ON DELETE CASCADE,
            content_sha256 TEXT NOT NULL,
            nogps_sha256 TEXT,
            source_path TEXT NOT NULL,
            source_filename TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            modified_at_utc TEXT,
            parser_version TEXT NOT NULL,
            imported_at_utc TEXT NOT NULL,
            started_at_utc TEXT,
            ended_at_utc TEXT,
            measurement_count INTEGER NOT NULL,
            parse_failure_count INTEGER NOT NULL,
            is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
            UNIQUE (source_log_id, content_sha256, nogps_sha256)
        );

        CREATE UNIQUE INDEX one_current_revision_per_log
            ON source_log_revisions(source_log_id) WHERE is_current = 1;

        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id TEXT NOT NULL REFERENCES source_log_revisions(id) ON DELETE CASCADE,
            record_kind TEXT NOT NULL CHECK (record_kind IN ('track', 'nogps')),
            sequence_no INTEGER NOT NULL,
            source_line_number INTEGER,
            measured_at_utc TEXT NOT NULL,
            cpm INTEGER NOT NULL,
            interval_counts INTEGER NOT NULL,
            total_counts INTEGER NOT NULL,
            radiation_status TEXT NOT NULL,
            gps_status TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            altitude_m REAL,
            satellites INTEGER NOT NULL,
            hdop_raw INTEGER NOT NULL,
            checksum_valid INTEGER NOT NULL CHECK (checksum_valid IN (0, 1)),
            time_quality TEXT NOT NULL,
            location_quality TEXT NOT NULL,
            radiation_valid INTEGER NOT NULL CHECK (radiation_valid IN (0, 1)),
            validation_issues TEXT NOT NULL DEFAULT '',
            raw_line_sha256 TEXT NOT NULL,
            UNIQUE (revision_id, record_kind, sequence_no)
        );

        CREATE INDEX measurements_revision_time
            ON measurements(revision_id, measured_at_utc);
        CREATE INDEX measurements_position
            ON measurements(latitude, longitude);

        CREATE TABLE mission_source_logs (
            mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
            source_log_id TEXT NOT NULL REFERENCES source_logs(id) ON DELETE CASCADE,
            attached_at_utc TEXT NOT NULL,
            PRIMARY KEY (mission_id, source_log_id)
        );
        """
    )
    now = utc_now_text()
    connection.execute(
        "INSERT INTO crs_schema_migrations(version, applied_at_utc) VALUES (?, ?)",
        (1, now),
    )
    for table_name, identifier, description in (
        ("devices", "CzechRad devices", "Profiles of imported CzechRad detectors"),
        ("missions", "CzechRad missions", "User-managed measurement missions"),
        ("source_logs", "CzechRad source logs", "Stable daily-log identities"),
        ("source_log_revisions", "CzechRad log revisions", "Immutable revisions of daily logs"),
        ("measurements", "CzechRad measurements", "Raw validated measurements including records without GPS"),
        ("mission_source_logs", "CzechRad mission membership", "Daily logs assigned to missions"),
    ):
        connection.execute(
            """
            INSERT OR IGNORE INTO gpkg_contents
            (table_name, data_type, identifier, description, srs_id)
            VALUES (?, 'attributes', ?, ?, NULL)
            """,
            (table_name, identifier, description),
        )


def _migration_2(connection: sqlite3.Connection) -> None:
    """Record the exact LOG sentence family and its calibration."""

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(devices)")
    }
    additions = (
        ("device_type", "TEXT NOT NULL DEFAULT 'CZRA1'"),
        ("device_family", "TEXT NOT NULL DEFAULT 'CzechRad'"),
        ("calibration_cpm_per_usvh", "REAL NOT NULL DEFAULT 328.5"),
    )
    for name, declaration in additions:
        if name not in columns:
            connection.execute(
                f"ALTER TABLE devices ADD COLUMN {name} {declaration}"
            )
    connection.execute(
        "INSERT INTO crs_schema_migrations(version, applied_at_utc) VALUES (?, ?)",
        (2, utc_now_text()),
    )


def _migration_3(connection: sqlite3.Connection) -> None:
    """Add revision-scoped proposals and stable user-owned segments."""

    connection.executescript(
        """
        CREATE TABLE segment_proposals (
            id TEXT PRIMARY KEY,
            source_log_id TEXT NOT NULL REFERENCES source_logs(id) ON DELETE CASCADE,
            revision_id TEXT NOT NULL REFERENCES source_log_revisions(id) ON DELETE CASCADE,
            proposal_type TEXT NOT NULL
                CHECK (proposal_type IN ('stationary', 'gps_loss', 'recording_gap')),
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT NOT NULL,
            confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            reason TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            center_latitude REAL,
            center_longitude REAL,
            created_at_utc TEXT NOT NULL,
            UNIQUE (revision_id, proposal_type, started_at_utc, ended_at_utc)
        );

        CREATE INDEX segment_proposals_source_revision
            ON segment_proposals(source_log_id, revision_id, started_at_utc);

        CREATE TABLE measurement_segments (
            id TEXT PRIMARY KEY,
            source_log_id TEXT NOT NULL REFERENCES source_logs(id) ON DELETE CASCADE,
            mission_id TEXT REFERENCES missions(id) ON DELETE SET NULL,
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT NOT NULL,
            segment_type TEXT NOT NULL DEFAULT 'unclassified'
                CHECK (segment_type IN ('unclassified', 'walking', 'car',
                    'public_transport', 'stationary', 'indoor', 'excluded')),
            title TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'confirmed', 'excluded')),
            include_in_suro INTEGER NOT NULL DEFAULT 1
                CHECK (include_in_suro IN (0, 1)),
            detector_height_m REAL,
            detector_orientation TEXT NOT NULL DEFAULT '',
            route_description TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            CHECK (ended_at_utc >= started_at_utc)
        );

        CREATE INDEX measurement_segments_source_time
            ON measurement_segments(source_log_id, started_at_utc, ended_at_utc);
        """
    )
    for table_name, identifier, description in (
        (
            "segment_proposals",
            "Automatic segment proposals",
            "Revision-scoped suggestions requiring user confirmation",
        ),
        (
            "measurement_segments",
            "Measurement segments",
            "Stable user-owned time ranges and SÚRO metadata",
        ),
    ):
        connection.execute(
            """
            INSERT OR IGNORE INTO gpkg_contents
            (table_name, data_type, identifier, description, srs_id)
            VALUES (?, 'attributes', ?, ?, NULL)
            """,
            (table_name, identifier, description),
        )
    connection.execute(
        "INSERT INTO crs_schema_migrations(version, applied_at_utc) VALUES (?, ?)",
        (3, utc_now_text()),
    )


def migrate(connection: sqlite3.Connection) -> int:
    """Initialize or upgrade a CzechRad Studio GeoPackage transactionally."""

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA application_id = %d" % GPKG_APPLICATION_ID)
    connection.execute("PRAGMA user_version = %d" % GPKG_USER_VERSION)
    with connection:
        _create_geopackage_core(connection)
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='crs_schema_migrations'"
        ).fetchone()
        current = (
            connection.execute("SELECT COALESCE(MAX(version), 0) FROM crs_schema_migrations").fetchone()[0]
            if exists
            else 0
        )
        if current < 1:
            _migration_1(connection)
            current = 1
        if current < 2:
            _migration_2(connection)
            current = 2
        if current < 3:
            _migration_3(connection)
            current = 3
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                "Databáze byla vytvořena novější verzí CzechRad Studia "
                f"(schéma {current}, podporováno {SCHEMA_VERSION})."
            )
    return current
