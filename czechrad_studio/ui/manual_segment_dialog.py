"""Create a user-owned measurement segment from a selected UTC time range."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from qgis.PyQt.QtCore import QTime
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
)

from ..database import GeoPackageRepository
from ..segments import SegmentType
from .segments_dialog import SEGMENT_TYPES


class ManualSegmentDialog(QDialog):
    """Small QGIS 3/4 compatible editor for one manual time segment."""

    def __init__(self, database_path, mission_id: str, parent=None):
        super().__init__(parent)
        self.repository = GeoPackageRepository(database_path)
        self.mission_id = mission_id
        self.recordings = self.repository.list_mission_recordings(mission_id)
        self.created_segment = None

        self.setWindowTitle("CzechRad Studio – nový úsek podle času")
        self.resize(620, 510)

        self.recording_combo = QComboBox(self)
        for recording in self.recordings:
            self.recording_combo.addItem(
                (
                    f"{recording.logical_date} – {recording.source_name} – "
                    f"{recording.start:%H:%M:%S}–{recording.end:%H:%M:%S} "
                    f"({recording.measurement_count} záznamů)"
                )
            )
        self.recording_combo.currentIndexChanged.connect(
            self._recording_changed
        )

        self.start_time = QTimeEdit(self)
        self.start_time.setDisplayFormat("HH:mm:ss")
        self.end_time = QTimeEdit(self)
        self.end_time.setDisplayFormat("HH:mm:ss")

        self.type_combo = QComboBox(self)
        for label, value in SEGMENT_TYPES:
            self.type_combo.addItem(label, value.value)
        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("Například pěší trasa centrem")
        self.height_spin = QDoubleSpinBox(self)
        self.height_spin.setRange(-1.0, 10.0)
        self.height_spin.setDecimals(2)
        self.height_spin.setSingleStep(0.1)
        self.height_spin.setSuffix(" m")
        self.height_spin.setSpecialValueText("neuvedeno")
        self.height_spin.setValue(-1.0)
        self.orientation_combo = QComboBox(self)
        self.orientation_combo.addItems(
            ("", "dolů", "nahoru", "dopředu", "dozadu", "doleva", "doprava")
        )
        self.route_edit = QLineEdit(self)
        self.route_edit.setPlaceholderText("Místo nebo stručný popis trasy")
        self.notes_edit = QTextEdit(self)
        self.notes_edit.setMaximumHeight(85)
        self.suro_check = QCheckBox("Zahrnout do přípravy pro SÚRO", self)
        self.suro_check.setChecked(True)
        self.range_label = QLabel(self)
        self.range_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Měření:", self.recording_combo)
        form.addRow("Začátek (UTC):", self.start_time)
        form.addRow("Konec (UTC):", self.end_time)
        form.addRow("Dostupný rozsah:", self.range_label)
        form.addRow("Typ úseku:", self.type_combo)
        form.addRow("Název:", self.title_edit)
        form.addRow("Výška detektoru:", self.height_spin)
        form.addRow("Orientace detektoru:", self.orientation_combo)
        form.addRow("Popis trasy:", self.route_edit)
        form.addRow("Poznámka:", self.notes_edit)
        form.addRow("", self.suro_check)

        create_button = QPushButton("Vytvořit úsek", self)
        create_button.clicked.connect(self._create)
        cancel_button = QPushButton("Zrušit", self)
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(create_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Vyber konkrétní záznam a nastav hranice úseku podle času "
                "v LOGu. Původní soubor ani naměřené body se nemění.",
                self,
            )
        )
        layout.addLayout(form)
        layout.addLayout(buttons)

        create_button.setEnabled(bool(self.recordings))
        if self.recordings:
            self._recording_changed(0)
        else:
            self.range_label.setText(
                "Aktivní mise neobsahuje žádné načtené měření."
            )

    def _recording_changed(self, index: int):
        if not 0 <= index < len(self.recordings):
            return
        recording = self.recordings[index]
        self.start_time.setTime(
            QTime(recording.start.hour, recording.start.minute, recording.start.second)
        )
        self.end_time.setTime(
            QTime(recording.end.hour, recording.end.minute, recording.end.second)
        )
        self.range_label.setText(
            f"{recording.start.isoformat()} až {recording.end.isoformat()}"
        )

    @staticmethod
    def _selected_datetime(recording, time_edit, *, is_end=False):
        selected = time_edit.time()
        value = datetime(
            recording.start.year,
            recording.start.month,
            recording.start.day,
            selected.hour(),
            selected.minute(),
            selected.second(),
            tzinfo=timezone.utc,
        )
        if is_end and value < recording.start and recording.end.date() > recording.start.date():
            value += timedelta(days=1)
        return value

    def _create(self):
        index = self.recording_combo.currentIndex()
        if not 0 <= index < len(self.recordings):
            return
        recording = self.recordings[index]
        start = self._selected_datetime(recording, self.start_time)
        end = self._selected_datetime(recording, self.end_time, is_end=True)
        height = self.height_spin.value()
        try:
            self.created_segment = self.repository.create_segment(
                recording.source_log_id,
                start,
                end,
                mission_id=self.mission_id,
                recording_id=recording.recording_id,
                segment_type=SegmentType(self.type_combo.currentData()),
                title=self.title_edit.text(),
                status="confirmed",
                include_in_suro=self.suro_check.isChecked(),
                detector_height_m=None if height < 0 else height,
                detector_orientation=self.orientation_combo.currentText(),
                route_description=self.route_edit.text(),
                notes=self.notes_edit.toPlainText(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "CzechRad Studio", str(exc))
            return
        self.accept()
