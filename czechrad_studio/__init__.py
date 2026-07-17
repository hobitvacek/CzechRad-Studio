"""QGIS entry point for CzechRad Studio.

Copyright (C) 2026 CzechRad Studio contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""


def classFactory(iface):  # noqa: N802 - QGIS requires this name
    """Create the QGIS plugin instance."""
    from .plugin import CzechRadStudioPlugin

    return CzechRadStudioPlugin(iface)
