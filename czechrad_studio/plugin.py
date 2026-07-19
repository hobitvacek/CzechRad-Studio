"""Minimal QGIS plugin shell.

Copyright (C) 2026 CzechRad Studio contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

from qgis.PyQt.QtWidgets import QAction, QDialog, QMessageBox

from .core.constants import PLUGIN_NAME
from .importer import analyze_log_files
from .ui import ImportDialog, add_analysis_layers


class CzechRadStudioPlugin:
    """Register and remove the initial CzechRad Studio UI action."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):  # noqa: N802 - QGIS requires this name
        self.action = QAction(PLUGIN_NAME, self.iface.mainWindow())
        self.action.setObjectName("czechradStudioOpenAction")
        self.action.setStatusTip("Otevřít CzechRad Studio")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is None:
            return

        self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self.action)
        self.iface.removeToolBarIcon(self.action)
        self.action.deleteLater()
        self.action = None

    def run(self):
        dialog = ImportDialog(self.iface.mainWindow())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            analysis = analyze_log_files(dialog.track_path, dialog.nogps_path)
            layers = add_analysis_layers(analysis, dialog.track_path)
            self.iface.setActiveLayer(layers.track)
            self.iface.mapCanvas().setExtent(layers.track.extent())
            self.iface.mapCanvas().refresh()
        except Exception as exc:  # QGIS must report file and provider failures to user
            QMessageBox.critical(
                self.iface.mainWindow(),
                PLUGIN_NAME,
                f"Měření se nepodařilo načíst:\n\n{exc}",
            )
            return

        correlation = analysis.nogps_correlation
        matched_nogps = len(correlation.matched) if correlation is not None else 0
        QMessageBox.information(
            self.iface.mainWindow(),
            PLUGIN_NAME,
            "Měření bylo načteno.\n\n"
            f"Datum (UTC): {analysis.expected_date.isoformat()}\n"
            f"Záznamů v denním LOGu: {len(analysis.track.measurements)}\n"
            f"Bodů v mapě: {len(analysis.geometry_measurements)}\n"
            f"Přiřazených NOGPS záznamů: {matched_nogps}\n"
            f"Kandidátů zastavení: {len(analysis.stop_candidates)}\n"
            f"Kandidátů ztráty GPS: {len(analysis.location_losses)}\n"
            f"Nezpracovaných řádků: {analysis.failure_count}",
        )

