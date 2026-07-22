"""Choose a GeoPackage project and its active measurement mission."""

from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from ..database import GeoPackageRepository
from ..qt_compat import BUTTON_CANCEL, BUTTON_OK


class ProjectDialog(QDialog):
    """Create or open a CzechRad GeoPackage and select one mission."""

    DATABASE_KEY = "CzechRadStudio/projectDatabase"
    MISSION_KEY = "CzechRadStudio/activeMission"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CzechRad Studio – projekt a mise")
        self.setModal(True)
        self.resize(720, 260)

        self.database_edit = QLineEdit(self)
        self.database_edit.setPlaceholderText("Například D:\\Radiace\\Ostrava_2026.gpkg")
        self.database_edit.editingFinished.connect(self._reload_missions)
        self.mission_combo = QComboBox(self)
        self.mission_name_edit = QLineEdit(self)
        self.mission_name_edit.setPlaceholderText("Například Víkend v Ostravě")
        self.description_edit = QLineEdit(self)
        self.description_edit.setPlaceholderText("Volitelný popis mise")
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)

        open_button = QPushButton("Otevřít…", self)
        open_button.clicked.connect(self._choose_existing)
        new_button = QPushButton("Nový…", self)
        new_button.clicked.connect(self._choose_new)
        create_mission_button = QPushButton("Vytvořit misi", self)
        create_mission_button.clicked.connect(self._create_mission)

        form = QFormLayout()
        form.addRow(
            "Projektový GeoPackage:",
            self._row(self.database_edit, open_button, new_button),
        )
        form.addRow("Aktivní mise:", self.mission_combo)
        form.addRow("Nová mise:", self._row(self.mission_name_edit, create_mission_button))
        form.addRow("Popis:", self.description_edit)

        note = QLabel(
            "Nové i změněné denní LOGy se budou ukládat do vybrané mise. "
            "Stejná data se znovu nevloží a změněný LOG vytvoří novou revizi.",
            self,
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(BUTTON_OK | BUTTON_CANCEL, parent=self)
        buttons.button(BUTTON_OK).setText("Použít projekt")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(buttons)

        settings = QSettings()
        self.database_edit.setText(settings.value(self.DATABASE_KEY, "", type=str))
        self._reload_missions(settings.value(self.MISSION_KEY, "", type=str))

    @staticmethod
    def _row(*widgets):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        for index, widget in enumerate(widgets):
            layout.addWidget(widget, 1 if index == 0 else 0)
        return container

    @property
    def database_path(self) -> str:
        return self.database_edit.text().strip()

    @property
    def mission_id(self) -> str | None:
        return self.mission_combo.currentData()

    @classmethod
    def active_configuration(cls) -> tuple[str | None, str | None]:
        settings = QSettings()
        database = settings.value(cls.DATABASE_KEY, "", type=str).strip()
        mission = settings.value(cls.MISSION_KEY, "", type=str).strip()
        return (database or None, mission or None)

    def _choose_existing(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Otevřít projekt CzechRad Studio",
            str(Path(self.database_path).parent) if self.database_path else "",
            "GeoPackage (*.gpkg)",
        )
        if path:
            self.database_edit.setText(path)
            self._reload_missions()

    def _choose_new(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Vytvořit projekt CzechRad Studio",
            self.database_path,
            "GeoPackage (*.gpkg)",
        )
        if path:
            if not path.lower().endswith(".gpkg"):
                path += ".gpkg"
            self.database_edit.setText(path)
            try:
                GeoPackageRepository(path).initialize()
            except Exception as exc:
                QMessageBox.critical(self, "CzechRad Studio", f"Projekt nelze vytvořit:\n\n{exc}")
                return
            self._reload_missions()

    def _reload_missions(self, selected_id: str | None = None):
        self.mission_combo.clear()
        if not self.database_path or not Path(self.database_path).is_file():
            self.status_label.setText("Vyber existující projekt nebo vytvoř nový.")
            return
        try:
            repository = GeoPackageRepository(self.database_path)
            missions = repository.list_missions()
        except Exception as exc:
            self.status_label.setText(f"Projekt nelze otevřít: {exc}")
            return
        for mission in missions:
            self.mission_combo.addItem(mission.name, mission.id)
            if selected_id and mission.id == selected_id:
                self.mission_combo.setCurrentIndex(self.mission_combo.count() - 1)
        self.status_label.setText(
            f"Nalezeno misí: {len(missions)}."
            if missions
            else "Projekt zatím nemá žádnou misi. Vytvoř první misi."
        )

    def _create_mission(self):
        if not self.database_path:
            QMessageBox.warning(self, "CzechRad Studio", "Nejdříve vyber nebo vytvoř projekt.")
            return
        try:
            repository = GeoPackageRepository(self.database_path)
            repository.initialize()
            mission = repository.create_mission(
                self.mission_name_edit.text(), self.description_edit.text()
            )
        except Exception as exc:
            QMessageBox.warning(self, "CzechRad Studio", f"Misi nelze vytvořit:\n\n{exc}")
            return
        self.mission_name_edit.clear()
        self.description_edit.clear()
        self._reload_missions(mission.id)

    def accept(self):
        if not self.database_path or not Path(self.database_path).is_file():
            QMessageBox.warning(self, "CzechRad Studio", "Vyber platný projektový GeoPackage.")
            return
        if not self.mission_id:
            QMessageBox.warning(self, "CzechRad Studio", "Vyber nebo vytvoř aktivní misi.")
            return
        try:
            GeoPackageRepository(self.database_path).get_mission(self.mission_id)
        except Exception as exc:
            QMessageBox.warning(self, "CzechRad Studio", f"Projekt nelze použít:\n\n{exc}")
            return
        settings = QSettings()
        settings.setValue(self.DATABASE_KEY, self.database_path)
        settings.setValue(self.MISSION_KEY, self.mission_id)
        super().accept()

