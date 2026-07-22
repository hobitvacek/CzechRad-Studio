"""Exercise the compatibility layer against minimal Qt 5 and Qt 6 surfaces."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "czechrad_studio" / "qt_compat.py"
)


def load_compat(*, qt6):
    qgis = types.ModuleType("qgis")
    pyqt = types.ModuleType("qgis.PyQt")
    core = types.ModuleType("qgis.PyQt.QtCore")
    gui = types.ModuleType("qgis.PyQt.QtGui")
    widgets = types.ModuleType("qgis.PyQt.QtWidgets")

    if qt6:
        class QMetaType:
            class Type:
                QString = "qstring6"
                Int = "int6"
                Double = "double6"
                Bool = "bool6"

        class QDialog:
            class DialogCode:
                Accepted = 1

        class QDialogButtonBox:
            class StandardButton:
                Ok = 1
                Save = 2
                Cancel = 4

        class QAction:
            pass

        gui.QAction = QAction
    else:
        class QMetaType:
            pass

        class QDialog:
            Accepted = 1

        class QDialogButtonBox:
            Ok = 1
            Save = 2
            Cancel = 4

        class QAction:
            pass

        widgets.QAction = QAction

    class QVariant:
        String = "string5"
        Int = "int5"
        Double = "double5"
        Bool = "bool5"

    core.QMetaType = QMetaType
    core.QVariant = QVariant
    widgets.QDialog = QDialog
    widgets.QDialogButtonBox = QDialogButtonBox
    modules = {
        "qgis": qgis,
        "qgis.PyQt": pyqt,
        "qgis.PyQt.QtCore": core,
        "qgis.PyQt.QtGui": gui,
        "qgis.PyQt.QtWidgets": widgets,
    }
    name = "_czechrad_qt6_test" if qt6 else "_czechrad_qt5_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class QtCompatibilityTest(unittest.TestCase):
    def test_qt5_unscoped_enums_and_qvariant_types(self):
        compat = load_compat(qt6=False)

        self.assertEqual(1, compat.DIALOG_ACCEPTED)
        self.assertEqual(1, compat.BUTTON_OK)
        self.assertEqual("string5", compat.FIELD_STRING)
        self.assertEqual("int5", compat.FIELD_INT)

        class LegacyDialog:
            def exec_(self):
                return 1

        self.assertEqual(1, compat.exec_dialog(LegacyDialog()))

    def test_qt6_scoped_enums_and_qmetatype_types(self):
        compat = load_compat(qt6=True)

        self.assertEqual(1, compat.DIALOG_ACCEPTED)
        self.assertEqual(2, compat.BUTTON_SAVE)
        self.assertEqual("qstring6", compat.FIELD_STRING)
        self.assertEqual("double6", compat.FIELD_DOUBLE)

        class ModernDialog:
            def exec(self):
                return 1

        self.assertEqual(1, compat.exec_dialog(ModernDialog()))


if __name__ == "__main__":
    unittest.main()
