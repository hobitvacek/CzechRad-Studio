# Changelog

Významné změny budou dokumentovány v tomto souboru. Projekt používá [Semantic Versioning](https://semver.org/) a formát vychází z [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- One shared plugin package for QGIS 3.22+ / Qt 5 and QGIS 4.x / Qt 6.
- A focused Qt compatibility layer for dialog enums, standard buttons,
  attribute field types, `QAction` and modal dialog execution.
- Python 3.8/3.9-compatible domain dataclasses for older Linux QGIS 3 builds.
- Linux CI checks on Python 3.8 and Python 3.12 for the portable core and the
  simulated Qt5/Qt6 compatibility surface.

- Read-only monitoring of a configured card or LOG folder every five seconds.
- Import only after two unchanged file observations.
- SHA-256 deduplication, verified archive copies and collision numbering (`-1`, `-2`, …).
- Automatic replacement of an in-session map layer after a changed daily LOG is safely archived.
- Persistent QGIS settings for source folder, archive folder and monitoring state.

- Comparison of prolonged stops with the nearby route radiation baseline.
- Highlighting only stops elevated by at least 30% and 0.03 µSv/h as possible stationary measurements.
- Preservation of all points in an elevated stop while ordinary GPS-drift clusters remain eligible for map-only aggregation.

- CzechRad conversion from CPM and five-second counts to µSv/h using the documented 328.5 CPM calibration.
- Neutral five-band map renderer switchable between µSv/h and CPM whose classes appear in the QGIS layer legend.
- Optional map-only aggregation of stable prolonged stops into one average point.
- Conservative preservation of all stop points when a sudden or sustained radiation increase is detected.

- QGIS-independent domain types for CzechRad measurements.
- Parser for CzechRad `$CZRA1` records with checksum verification and audit failures.
- Independent validation of timestamps, radiation values and GPS trust.
- Synthetic tests for valid GPS, NOGPS and device default dates.
- Correlation of a cumulative multi-day `NOGPS.LOG` with one daily track.
- Detection of internal GPS-loss candidates with trusted entry and exit anchors.
- Detection of prolonged spatial stop candidates without QGIS dependencies.
- QGIS import dialog for a daily LOG and optional cumulative `NOGPS.LOG`.
- Memory layers for mapped measurements and stop/GPS-loss candidates.
- CRS-aware zoom to imported WGS 84 tracks in OpenStreetMap projects.

### Fixed

- Preserve checksum-valid radiation measurements when CzechRad writes malformed
  coordinates during a GPS outage; the records remain auditable without map
  geometry instead of becoming parser failures.
- Interpret field 6 as radiation-count validity and field 12 as GPS validity,
  matching the published CzechRad LOG specification.

### Planned

- Podpora `NOGPS*.LOG` jako měření bez polohy, včetně vnitřních úseků a ručního přiřazení místa.
- Import jednoho denního LOG souboru.
- Monitoring složky a aktualizace změněného souboru bez duplicit.
- Volitelný automatický import po vložení nastavené karty, bezpečná archivní kopie a číslování kolizí názvů.

## [0.1.0] - 2026-07-17

### Added

- Základní kostra QGIS pluginu.
- Modulární adresářová struktura.
- Dokumenty VISION, ARCHITECTURE, ROADMAP a SURO_EXPORT.
- Základní testy kontraktu pluginu.
- Kontrola a sjednocení licenčních informací.
