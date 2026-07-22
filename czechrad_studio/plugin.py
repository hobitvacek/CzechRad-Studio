"""Minimal QGIS plugin shell.

Copyright (C) 2026 CzechRad Studio contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from qgis.PyQt.QtCore import QSettings, QTimer
from qgis.PyQt.QtWidgets import QAction, QDialog, QMessageBox
from qgis.core import QgsProject

from .core.constants import PLUGIN_NAME
from .importer import analyze_log_files
from .missions import assess_stop_radiation
from .monitoring import StableFileTracker, archive_ready_logs
from .ui import ImportDialog, MonitorDialog, add_analysis_layers


class CzechRadStudioPlugin:
    """Register and remove the initial CzechRad Studio UI action."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.monitor_action = None
        self.monitor_timer = QTimer(self.iface.mainWindow())
        self.monitor_timer.setInterval(5000)
        self.monitor_timer.timeout.connect(self._poll_monitor)
        self.monitor_tracker = StableFileTracker()
        self._monitored_archives = {}
        self._monitored_layers = {}
        self._loaded_digests = set()
        self._latest_nogps = None

    def initGui(self):  # noqa: N802 - QGIS requires this name
        self.action = QAction(PLUGIN_NAME, self.iface.mainWindow())
        self.action.setObjectName("czechradStudioOpenAction")
        self.action.setStatusTip("Otevřít CzechRad Studio")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.action)
        self.iface.addToolBarIcon(self.action)

        self.monitor_action = QAction(
            "Nastavit automatický import…", self.iface.mainWindow()
        )
        self.monitor_action.triggered.connect(self.configure_monitoring)
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.monitor_action)
        self._apply_monitor_settings()

    def unload(self):
        if self.action is None:
            return

        self.monitor_timer.stop()
        if self.monitor_action is not None:
            self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self.monitor_action)
            self.monitor_action.deleteLater()
            self.monitor_action = None

        self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self.action)
        self.iface.removeToolBarIcon(self.action)
        self.action.deleteLater()
        self.action = None

    def configure_monitoring(self):
        dialog = MonitorDialog(self.iface.mainWindow())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.monitor_tracker = StableFileTracker()
            self._apply_monitor_settings()

    def _apply_monitor_settings(self):
        enabled = QSettings().value(MonitorDialog.ENABLED_KEY, False, type=bool)
        if enabled:
            self.monitor_timer.start()
        else:
            self.monitor_timer.stop()

    @staticmethod
    def _is_nogps(path: Path) -> bool:
        return path.stem.upper().startswith("NOGPS")

    def _replace_monitored_layer(self, source_key: str, track_path: Path):
        analysis = analyze_log_files(track_path, self._latest_nogps)
        new_layers = add_analysis_layers(
            analysis,
            str(track_path),
            collapse_stops=True,
            display_unit="usvh",
        )
        previous = self._monitored_layers.get(source_key)
        self._monitored_layers[source_key] = new_layers
        self._monitored_archives[source_key] = track_path
        if previous is not None:
            project = QgsProject.instance()
            project.removeMapLayer(previous.track.id())
            if previous.candidates is not None:
                project.removeMapLayer(previous.candidates.id())

    def _poll_monitor(self):
        settings = QSettings()
        source = settings.value(MonitorDialog.SOURCE_KEY, "", type=str)
        archive = settings.value(MonitorDialog.ARCHIVE_KEY, "", type=str)
        if not source or not archive or not Path(source).is_dir():
            return
        try:
            results = archive_ready_logs(self.monitor_tracker, source, archive)
            nogps_results = [
                result for result in results if self._is_nogps(result.destination)
            ]
            if nogps_results:
                self._latest_nogps = nogps_results[-1].destination

            daily_results = [
                result
                for result in results
                if not self._is_nogps(result.destination)
                and result.digest not in self._loaded_digests
            ]
            for result in daily_results:
                self._replace_monitored_layer(
                    str(result.source).casefold(), result.destination
                )
                self._loaded_digests.add(result.digest)

            if nogps_results:
                for source_key, track_path in tuple(self._monitored_archives.items()):
                    self._replace_monitored_layer(source_key, track_path)

            copied_count = sum(result.copied for result in results)
            if copied_count:
                self.iface.messageBar().pushSuccess(
                    PLUGIN_NAME,
                    f"Archivováno {copied_count} nových nebo změněných LOGů.",
                )
        except Exception as exc:
            self.iface.messageBar().pushWarning(
                PLUGIN_NAME, f"Automatický import se nezdařil: {exc}"
            )

    def run(self):
        dialog = ImportDialog(self.iface.mainWindow())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            analysis = analyze_log_files(dialog.track_path, dialog.nogps_path)
            layers = add_analysis_layers(
                analysis,
                dialog.track_path,
                collapse_stops=dialog.collapse_stops,
                display_unit=dialog.display_unit,
            )
            self.iface.setActiveLayer(layers.track)
            # QGIS transforms the layer's WGS 84 extent to the canvas CRS
            # (commonly Web Mercator for the OpenStreetMap template).
            self.iface.zoomToActiveLayer()
        except Exception as exc:  # QGIS must report file and provider failures to user
            QMessageBox.critical(
                self.iface.mainWindow(),
                PLUGIN_NAME,
                f"Měření se nepodařilo načíst:\n\n{exc}",
            )
            return

        correlation = analysis.nogps_correlation
        matched_nogps = len(correlation.matched) if correlation is not None else 0
        elevated_stops = sum(
            assessment is not None and assessment.elevated
            for assessment in (
                assess_stop_radiation(candidate, analysis.geometry_measurements)
                for candidate in analysis.stop_candidates
            )
        )
        QMessageBox.information(
            self.iface.mainWindow(),
            PLUGIN_NAME,
            "Měření bylo načteno.\n\n"
            f"Datum (UTC): {analysis.expected_date.isoformat()}\n"
            f"Záznamů v denním LOGu: {len(analysis.track.measurements)}\n"
            f"Bodů v mapě: {len(analysis.geometry_measurements)}\n"
            f"Přiřazených NOGPS záznamů: {matched_nogps}\n"
            f"Kandidátů zastavení: {len(analysis.stop_candidates)}\n"
            f"Možných stacionárních měření: {elevated_stops}\n"
            f"Kandidátů ztráty GPS: {len(analysis.location_losses)}\n"
            f"Nezpracovaných řádků: {analysis.failure_count}",
        )

