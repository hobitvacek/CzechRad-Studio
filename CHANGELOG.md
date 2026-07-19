# Changelog

Významné změny budou dokumentovány v tomto souboru. Projekt používá [Semantic Versioning](https://semver.org/) a formát vychází z [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- QGIS-independent domain types for CzechRad measurements.
- Parser for CzechRad `$CZRA1` records with checksum verification and audit failures.
- Independent validation of timestamps, radiation values and GPS trust.
- Synthetic tests for valid GPS, NOGPS and device default dates.
- Correlation of a cumulative multi-day `NOGPS.LOG` with one daily track.
- Detection of internal GPS-loss candidates with trusted entry and exit anchors.
- Detection of prolonged spatial stop candidates without QGIS dependencies.
- QGIS import dialog for a daily LOG and optional cumulative `NOGPS.LOG`.
- Memory layers for mapped measurements and stop/GPS-loss candidates.

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

