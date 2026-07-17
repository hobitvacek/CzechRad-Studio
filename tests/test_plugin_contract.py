"""Contract tests that run without an installed QGIS runtime."""

import ast
import configparser
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
