"""Small Qt 5/Qt 6 compatibility surface used by the QGIS UI.

All application code imports Qt through ``qgis.PyQt``.  This module contains
the few API spelling differences which the QGIS shim cannot hide, so the rest
of CzechRad Studio stays version-independent.
"""

from qgis.PyQt.QtCore import QMetaType, QVariant
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox

try:
    # QAction moved from QtWidgets in Qt 5 to QtGui in Qt 6.
    from qgis.PyQt.QtGui import QAction
except ImportError:  # pragma: no cover - exercised inside QGIS 3 / Qt 5
    from qgis.PyQt.QtWidgets import QAction


def _enum_member(owner, scoped_name, member_name):
    """Return a scoped Qt 6 enum member or its unscoped Qt 5 equivalent."""

    scoped = getattr(owner, scoped_name, None)
    return getattr(scoped if scoped is not None else owner, member_name)


def _field_type(qmeta_name, qvariant_name):
    """Return the field type expected by QgsField in the active QGIS major."""

    scoped = getattr(QMetaType, "Type", None)
    if scoped is not None and hasattr(scoped, qmeta_name):
        return getattr(scoped, qmeta_name)
    return getattr(QVariant, qvariant_name)


DIALOG_ACCEPTED = _enum_member(QDialog, "DialogCode", "Accepted")

BUTTON_OK = _enum_member(QDialogButtonBox, "StandardButton", "Ok")
BUTTON_SAVE = _enum_member(QDialogButtonBox, "StandardButton", "Save")
BUTTON_CANCEL = _enum_member(QDialogButtonBox, "StandardButton", "Cancel")

FIELD_STRING = _field_type("QString", "String")
FIELD_INT = _field_type("Int", "Int")
FIELD_DOUBLE = _field_type("Double", "Double")
FIELD_BOOL = _field_type("Bool", "Bool")


def exec_dialog(dialog):
    """Execute a modal dialog using the method exposed by the active Qt."""

    method = getattr(dialog, "exec", None)
    if method is None:
        method = dialog.exec_
    return method()


__all__ = [
    "QAction",
    "BUTTON_CANCEL",
    "BUTTON_OK",
    "BUTTON_SAVE",
    "DIALOG_ACCEPTED",
    "FIELD_BOOL",
    "FIELD_DOUBLE",
    "FIELD_INT",
    "FIELD_STRING",
    "exec_dialog",
]
