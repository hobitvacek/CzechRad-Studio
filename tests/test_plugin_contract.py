"""Contract tests that run without an installed QGIS runtime."""

import ast
import configparser
import unittest
from pathlib import Path

from czechrad_studio.core.constants import PLUGIN_VERSION


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "czechrad_studio"


class PluginContractTest(unittest.TestCase):
    def test_required_plugin_files_exist(self):
        for relative_path in ("__init__.py", "metadata.txt", "plugin.py"):
            self.assertTrue((PLUGIN / relative_path).is_file(), relative_path)

    def test_entry_point_defines_class_factory(self):
        tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertIn("classFactory", functions)

    def test_metadata_contains_required_fields(self):
        parser = configparser.ConfigParser()
        parser.read(PLUGIN / "metadata.txt", encoding="utf-8")
        general = parser["general"]

        for field in (
            "name",
            "qgisminimumversion",
            "description",
            "about",
            "version",
            "author",
            "email",
            "repository",
        ):
            self.assertTrue(general.get(field), field)

    def test_qt_imports_are_qgis_version_independent(self):
        for path in PLUGIN.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("from PyQt5", source, path)
            self.assertNotIn("from PyQt6", source, path)

    def test_metadata_and_core_version_match(self):
        parser = configparser.ConfigParser()
        parser.read(PLUGIN / "metadata.txt", encoding="utf-8")

        self.assertEqual(PLUGIN_VERSION, parser["general"]["version"])

    def test_metadata_covers_qgis_3_and_qgis_4(self):
        parser = configparser.ConfigParser()
        parser.read(PLUGIN / "metadata.txt", encoding="utf-8")
        general = parser["general"]

        self.assertEqual("3.22", general["qgisminimumversion"])
        self.assertEqual("4.99", general["qgismaximumversion"])
        self.assertNotIn("supportsqt6", general)

    def test_first_import_ui_files_exist(self):
        for relative_path in (
            "ui/import_dialog.py",
            "ui/layers.py",
            "ui/monitor_dialog.py",
            "monitoring/files.py",
            "qt_compat.py",
        ):
            self.assertTrue((PLUGIN / relative_path).is_file(), relative_path)

    def test_sources_parse_with_python_3_8_grammar(self):
        for path in PLUGIN.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path), feature_version=(3, 8))
            self.assertNotIn("slots=True", source, path)

    def test_qt_version_specific_api_is_isolated(self):
        compatibility = PLUGIN / "qt_compat.py"
        for path in PLUGIN.rglob("*.py"):
            if path == compatibility:
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("DialogCode", source, path)
            self.assertNotIn("StandardButton", source, path)
            self.assertNotIn("QMetaType.Type", source, path)

    def test_monitoring_uses_qt_timer_and_read_only_archive_service(self):
        source = (PLUGIN / "plugin.py").read_text(encoding="utf-8")

        self.assertIn("QTimer", source)
        self.assertIn("archive_ready_logs", source)

    def test_zoom_uses_qgis_crs_aware_action(self):
        source = (PLUGIN / "plugin.py").read_text(encoding="utf-8")

        self.assertIn("zoomToActiveLayer()", source)
        self.assertNotIn("setExtent(layers.track.extent())", source)


if __name__ == "__main__":
    unittest.main()
