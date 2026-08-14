# Changelog

Vìznamn‚ zmØny budou dokumentov ny v tomto souboru. Projekt pou§¡v  [Semantic Versioning](https://semver.org/) a form t vych z¡ z [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

- Added manual creation of a measurement segment from a UTC time range in a
  selected current recording.
- Kept manual segments attached to the explicitly selected card recording even
  when multiple same-day recordings overlap in time.
- Added independent recording identities for multiple cards or recording
  sessions from the same device on the same UTC day.
- Distinguished a continuing LOG revision from a separate same-day recording
  by overlap of immutable raw measurement hashes instead of the filename.
- Kept each recording's NOGPS correlation, current revision, proposals and
  saved-segment map positions isolated while allowing the recordings to share
  one daily mission.
- Added collision-safe display labels such as `07960808.LOG (mØýen¡ 2)` without
  renaming or modifying the original source files.
- Added an active-mission overview of saved measurement segments with metadata
  editing and map focus based on the current LOG revision.
- Preserved the original GPS-loss entry anchor for locating indoor segments
  which contain no usable coordinates.
- Added a temporary high-contrast QGIS map layer for locating a selected
  segment proposal without modifying the source LOG or stored measurements.
- Fixed proposal highlighting not appearing while the segment editor blocked
  QGIS canvas repaint; the editor is now non-modal and explicitly refreshes
  the map after zooming.
- Added a QGIS 3/4 segment-review dialog for proposals in the active mission.
- Added confirmation of stop and GPS-loss proposals with movement type, title,
  detector height and orientation, route description, notes and SéRO inclusion.
- Added proposal review states so accepted or intentionally skipped suggestions
  do not repeatedly return after reopening the project.
- Suppressed recording-gap proposals when the same interval is already
  explained by a correlated GPS-loss episode from `NOGPS.LOG`.
- Kept recording gaps as reviewable boundary suggestions instead of allowing
  them to be incorrectly confirmed as measured time ranges.
- Added schema version 3 with revision-scoped automatic segment proposals and
  stable user-owned measurement segments.
- Added conservative proposals for prolonged stops, internal GPS-loss periods
  and recording gaps of at least five minutes.
- Preserved user-created segment boundaries and metadata across later revisions
  of the same daily LOG.
- Fixed QGIS 3.34 / Qt 5 field creation on Linux by selecting QVariant field
  types from the actual Qt major version instead of the presence of a scoped
  QMetaType enum.
- Corrected the default uSv/h map mode to use the device's latest five-second
  count, while retaining a separate smoothed one-minute CPM mode.
- Added explicit device detection for CzechRad `CZRA1`, legacy CzechRad
  `CZRDD`, and Safecast bGeigie Nano `BNRDD` records.
- Added CzechRad (328.5 CPM/uSv/h) and Safecast (334 CPM/uSv/h) calibration
  profiles to map layers, stop summaries, and GeoPackage device metadata.

### Added

- Versioned GeoPackage schema for devices, missions, daily source logs,
  immutable revisions and validated measurements.
- Transactional import with SHA-256 deduplication and preservation of the
  previous valid revision when a daily LOG changes.
- Mission creation and assignment of multiple daily logs through a new QGIS
  project dialog.
- Persistence of manual imports and monitored card imports into the active
  mission, including radiation records without usable GPS geometry.
- NOGPS revision identity based only on records matched to the imported day,
  preventing cumulative-file growth from revising unrelated older tracks.

- One shared plugin package for QGIS 3.22+ / Qt 5 and QGIS 4.x / Qt 6.
- A focused Qt compatibility layer for dialog enums, standard buttons,
  attribute field types, `QAction` and modal dialog execution.
- Python 3.8/3.9-compatible domain dataclasses for older Linux QGIS 3 builds.
- Linux CI checks on Python 3.8 and Python 3.12 for the portable core and the
  simulated Qt5/Qt6 compatibility surface.

- Read-only monitoring of a configured card or LOG folder every five seconds.
- Import only after two unchanged file observations.
- SHA-256 deduplication, verified archive copies and collision numbering (`-1`, `-2`, ).
- Automatic replacement of an in-session map layer after a changed daily LOG is safely archived.
- Persistent QGIS settings for source folder, archive folder and monitoring state.

- Comparison of prolonged stops with the nearby route radiation baseline.
- Highlighting only stops elevated by at least 30% and 0.03 uSv/h as possible stationary measurements.
- Preservation of all points in an elevated stop while ordinary GPS-drift clusters remain eligible for map-only aggregation.

- CzechRad conversion from CPM and five-second counts to uSv/h using the documented 328.5 CPM calibration.
- Neutral five-band map renderer switchable between uSv/h and CPM whose classes appear in the QGIS layer legend.
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

- Podpora `NOGPS*.LOG` jako mØýen¡ bez polohy, vŸetnØ vnitýn¡ch £sek… a ruŸn¡ho pýiýazen¡ m¡sta.
- Import jednoho denn¡ho LOG souboru.
- Monitoring slo§ky a aktualizace zmØnØn‚ho souboru bez duplicit.
- Volitelnì automatickì import po vlo§en¡ nastaven‚ karty, bezpeŸn  archivn¡ kopie a Ÿ¡slov n¡ koliz¡ n zv….

## [0.1.0] - 2026-07-17

### Added

- Z kladn¡ kostra QGIS pluginu.
- Modul rn¡ adres ýov  struktura.
- Dokumenty VISION, ARCHITECTURE, ROADMAP a SURO_EXPORT.
- Z kladn¡ testy kontraktu pluginu.
- Kontrola a sjednocen¡ licenŸn¡ch informac¡.
