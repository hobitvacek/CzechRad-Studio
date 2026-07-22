"""File selection dialog for the first CzechRad Studio import workflow."""

from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..qt_compat import BUTTON_CANCEL, BUTTON_OK


class ImportDialog(QDialog):
    """Choose a required daily LOG and an optional cumulative NOGPS file."""

    SETTINGS_KEY = "CzechRadStudio/lastImportFolder"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CzechRad Studio – načíst měření")
        self.setModal(True)
        self.resize(720, 230)

        self.track_edit = QLineEdit(self)
        self.track_edit.setPlaceholderText("Denní soubor, například 07960719.LOG")
        self.nogps_edit = QLineEdit(self)
        self.nogps_edit.setPlaceholderText("Volitelné: kumulativní NOGPS.LOG")
        self.collapse_stops_checkbox = QCheckBox(
            "Sloučit stabilní dlouhá zastavení do jednoho průměrného bodu", self
        )
        self.collapse_stops_checkbox.setChecked(True)
        self.collapse_stops_checkbox.setToolTip(
            "Původní LOG se nemění. Při nárůstu nebo skoku radiace zůstanou "
            "všechny body zobrazené."
        )
        self.display_unit_combo = QComboBox(self)
        self.display_unit_combo.addItem(
            "µSv/h – hodnota displeje (posledních 5 s)", "device_usvh"
        )
        self.display_unit_combo.addItem(
            "µSv/h – vyhlazená hodnota (minutové CPM)", "minute_usvh"
        )
        self.display_unit_combo.addItem("CPM – původní minutová hodnota", "cpm")

        track_button = QPushButton("Vybrat…", self)
        track_button.clicked.connect(self._choose_track)
        nogps_button = QPushButton("Vybrat…", self)
        nogps_button.clicked.connect(self._choose_nogps)

        form = QFormLayout()
        form.addRow("Denní LOG:", self._path_row(self.track_edit, track_button))
        form.addRow("NOGPS.LOG:", self._path_row(self.nogps_edit, nogps_button))
        form.addRow("Barevná legenda:", self.display_unit_combo)

        note = QLabel(
            "Denní LOG vytvoří vrstvu bodů. Pokud vybereš také NOGPS.LOG, "
            "doplní se analýza měření bez použitelné polohy.",
            self,
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(
            BUTTON_OK | BUTTON_CANCEL,
            parent=self,
        )
        buttons.button(BUTTON_OK).setText("Načíst do mapy")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(self.collapse_stops_checkbox)
        layout.addStretch(1)
        layout.addWidget(buttons)

    @staticmethod
    def _path_row(line_edit, button):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return widget

    @property
    def track_path(self) -> str:
        return self.track_edit.text().strip()

    @property
    def nogps_path(self) -> str | None:
        value = self.nogps_edit.text().strip()
        return value or None

    @property
    def collapse_stops(self) -> bool:
        return self.collapse_stops_checkbox.isChecked()

    @property
    def display_unit(self) -> str:
        return self.display_unit_combo.currentData()

    def _initial_folder(self) -> str:
        stored = QSettings().value(self.SETTINGS_KEY, "", type=str)
        return stored if stored and Path(stored).is_dir() else ""

    def _choose_file(self, title: str) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            self._initial_folder(),
            "CzechRad LOG (*.LOG *.log);;Všechny soubory (*)",
        )
        if path:
            QSettings().setValue(self.SETTINGS_KEY, str(Path(path).parent))
        return path

    def _choose_track(self):
        path = self._choose_file("Vybrat denní CzechRad LOG")
        if not path:
            return
        self.track_edit.setText(path)

        if not self.nogps_edit.text().strip():
            for candidate in Path(path).parent.iterdir():
                if candidate.is_file() and candidate.name.upper() == "NOGPS.LOG":
                    self.nogps_edit.setText(str(candidate))
                    break

    def _choose_nogps(self):
        path = self._choose_file("Vybrat kumulativní NOGPS.LOG")
        if path:
            self.nogps_edit.setText(path)

    def accept(self):
        if not self.track_path or not Path(self.track_path).is_file():
            QMessageBox.warning(self, "CzechRad Studio", "Vyber platný denní LOG.")
            return
        if self.nogps_path and not Path(self.nogps_path).is_file():
            QMessageBox.warning(self, "CzechRad Studio", "Vyber platný NOGPS.LOG.")
            return
        super().accept()
