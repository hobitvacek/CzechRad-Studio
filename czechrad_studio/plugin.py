"""Minimal QGIS plugin shell.

Copyright (C) 2026 CzechRad Studio contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .core.constants import PLUGIN_NAME


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
        QMessageBox.information(
            self.iface.mainWindow(),
            PLUGIN_NAME,
            "Technický základ pluginu je načten. Import měření bude doplněn v další verzi.",
        )
