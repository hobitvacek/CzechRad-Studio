"""Review and edit user-confirmed measurement segments."""

from __future__ import annotations

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from ..database import GeoPackageRepository
from ..qt_compat import DIALOG_ACCEPTED, exec_dialog
from ..segments import SegmentType
from .manual_segment_dialog import ManualSegmentDialog
from .segments_dialog import SEGMENT_TYPES, _enum


SEGMENT_LABELS = {value: label for label, value in SEGMENT_TYPES}


class SavedSegmentsDialog(QDialog):
    """Non-blocking list and metadata editor for one mission's segments."""

    segment_focus_requested = pyqtSignal(object)
    map_segment_requested = pyqtSignal()

    def __init__(self, database_path, mission_id: str, parent=None):
        super().__init__(parent)
        self.repository = GeoPackageRepository(database_path)
        self.mission_id = mission_id
        self.segments = ()

        self.setWindowTitle("CzechRad Studio – uložené úseky")
        self.setModal(False)
        self.resize(980, 650)

        self.summary_label = QLabel(self)
        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(
            ("Datum", "Od", "Do", "Typ", "Název", "SÚRO", "Soubor")
        )
        self.table.setSelectionMode(
            _enum(QAbstractItemView, "SelectionMode", "SingleSelection")
        )
        self.table.setSelectionBehavior(
            _enum(QAbstractItemView, "SelectionBehavior", "SelectRows")
        )
        self.table.setEditTriggers(
            _enum(QAbstractItemView, "EditTrigger", "NoEditTriggers")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            4, _enum(QHeaderView, "ResizeMode", "Stretch")
        )
        self.table.itemSelectionChanged.connect(self._selection_changed)

        self.type_combo = QComboBox(self)
        for label, value in SEGMENT_TYPES:
            self.type_combo.addItem(label, value.value)
        self.title_edit = QLineEdit(self)
        self.height_spin = QDoubleSpinBox(self)
        self.height_spin.setRange(-1.0, 10.0)
        self.height_spin.setDecimals(2)
        self.height_spin.setSingleStep(0.1)
        self.height_spin.setSuffix(" m")
        self.height_spin.setSpecialValueText("neuvedeno")
        self.orientation_combo = QComboBox(self)
        self.orientation_combo.addItems(
            ("", "dolů", "nahoru", "dopředu", "dozadu", "doleva", "doprava")
        )
        self.route_edit = QLineEdit(self)
        self.notes_edit = QTextEdit(self)
        self.notes_edit.setMaximumHeight(85)
        self.suro_check = QCheckBox("Zahrnout do přípravy pro SÚRO", self)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Typ úseku:", self.type_combo)
        form.addRow("Název:", self.title_edit)
        form.addRow("Výška detektoru:", self.height_spin)
        form.addRow("Orientace detektoru:", self.orientation_combo)
        form.addRow("Popis trasy:", self.route_edit)
        form.addRow("Poznámka:", self.notes_edit)
        form.addRow("", self.suro_check)

        self.new_button = QPushButton("Nový úsek podle času…", self)
        self.new_button.clicked.connect(self._new_segment)
        self.map_button = QPushButton("Nový úsek z mapy…", self)
        self.map_button.clicked.connect(self.map_segment_requested.emit)
        self.focus_button = QPushButton("Ukázat v mapě", self)
        self.focus_button.clicked.connect(self._focus)
        self.save_button = QPushButton("Uložit změny", self)
        self.save_button.clicked.connect(self._save)
        close_button = QPushButton("Zavřít", self)
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.map_button)
        buttons.addWidget(self.focus_button)
        buttons.addWidget(self.save_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Zde lze opravit metadata potvrzených úseků. Časové hranice "
                "a původní LOG se touto obrazovkou nemění.",
                self,
            )
        )
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)

        self._reload()

    def _reload(self, selected_id=None):
        self.segments = self.repository.list_mission_segments(self.mission_id)
        self.table.setRowCount(len(self.segments))
        selected_row = 0
        for row_index, segment in enumerate(self.segments):
            if segment.id == selected_id:
                selected_row = row_index
            values = (
                segment.logical_date or segment.start.date().isoformat(),
                segment.start.strftime("%H:%M:%S"),
                segment.end.strftime("%H:%M:%S"),
                SEGMENT_LABELS.get(segment.segment_type, segment.segment_type.value),
                segment.title,
                "Ano" if segment.include_in_suro else "Ne",
                segment.source_name or "",
            )
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))
        self.summary_label.setText(
            f"Uložené úseky: {len(self.segments)}."
            if self.segments
            else "Aktivní mise zatím nemá žádné potvrzené úseky."
        )
        enabled = bool(self.segments)
        has_recordings = bool(
            self.repository.list_mission_recordings(self.mission_id)
        )
        self.new_button.setEnabled(has_recordings)
        self.map_button.setEnabled(has_recordings)
        self.focus_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        if enabled:
            self.table.selectRow(selected_row)

    def _selected(self):
        row = self.table.currentRow()
        return self.segments[row] if 0 <= row < len(self.segments) else None

    def _new_segment(self):
        dialog = ManualSegmentDialog(
            self.repository.path, self.mission_id, self
        )
        if exec_dialog(dialog) != DIALOG_ACCEPTED:
            return
        segment = dialog.created_segment
        self._reload(segment.id if segment is not None else None)
        if segment is not None:
            self.segment_focus_requested.emit(segment)

    def add_created_segment(self, segment):
        """Refresh the list after a map-selected segment was created."""

        if segment is None:
            return
        self._reload(segment.id)
        self.segment_focus_requested.emit(segment)

    def _set_type(self, segment_type: SegmentType):
        for index in range(self.type_combo.count()):
            if self.type_combo.itemData(index) == segment_type.value:
                self.type_combo.setCurrentIndex(index)
                return

    def _set_orientation(self, value: str):
        index = self.orientation_combo.findText(value)
        self.orientation_combo.setCurrentIndex(max(0, index))

    def _selection_changed(self):
        segment = self._selected()
        if segment is None:
            return
        self._set_type(segment.segment_type)
        self.title_edit.setText(segment.title)
        self.height_spin.setValue(
            -1.0 if segment.detector_height_m is None
            else segment.detector_height_m
        )
        self._set_orientation(segment.detector_orientation)
        self.route_edit.setText(segment.route_description)
        self.notes_edit.setPlainText(segment.notes)
        self.suro_check.setChecked(segment.include_in_suro)
        self.status_label.setText("")

    def _focus(self):
        segment = self._selected()
        if segment is not None:
            self.segment_focus_requested.emit(segment)

    def _save(self):
        segment = self._selected()
        if segment is None:
            return
        height = self.height_spin.value()
        try:
            self.repository.update_segment(
                segment.id,
                segment_type=SegmentType(self.type_combo.currentData()),
                title=self.title_edit.text(),
                include_in_suro=self.suro_check.isChecked(),
                detector_height_m=None if height < 0 else height,
                detector_orientation=self.orientation_combo.currentText(),
                route_description=self.route_edit.text(),
                notes=self.notes_edit.toPlainText(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "CzechRad Studio", str(exc))
            return
        self._reload(segment.id)
        self.status_label.setText("Změny byly uloženy.")

