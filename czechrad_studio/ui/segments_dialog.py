"""Review automatic segment proposals and add field metadata."""

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
    QWidget,
)

from ..database import GeoPackageRepository
from ..segments import ProposalType, SegmentType


PROPOSAL_LABELS = {
    ProposalType.STATIONARY: "Zastavení",
    ProposalType.GPS_LOSS: "Ztráta GPS / možná budova",
    ProposalType.RECORDING_GAP: "Mezera v záznamu",
}

SEGMENT_TYPES = (
    ("Neurčeno", SegmentType.UNCLASSIFIED),
    ("Pěšky", SegmentType.WALKING),
    ("Auto", SegmentType.CAR),
    ("MHD", SegmentType.PUBLIC_TRANSPORT),
    ("Stacionární měření", SegmentType.STATIONARY),
    ("Budova / bez GPS", SegmentType.INDOOR),
    ("Vyřadit", SegmentType.EXCLUDED),
)


def _enum(owner, scoped_name, member_name):
    scoped = getattr(owner, scoped_name, None)
    return getattr(scoped if scoped is not None else owner, member_name)


class SegmentsDialog(QDialog):
    """Modal, map-independent first editor for one mission's proposals."""

    proposal_focus_requested = pyqtSignal(object)

    def __init__(self, database_path, mission_id: str, parent=None):
        super().__init__(parent)
        self.repository = GeoPackageRepository(database_path)
        self.mission_id = mission_id
        self.proposals = ()

        self.setWindowTitle("CzechRad Studio – měřicí úseky")
        self.setModal(True)
        self.resize(1050, 680)

        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(
            ("Datum", "Od", "Do", "Návrh", "Délka", "Soubor", "Důvod")
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
            6, _enum(QHeaderView, "ResizeMode", "Stretch")
        )
        self.table.itemSelectionChanged.connect(self._selection_changed)

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
        self.notes_edit.setPlaceholderText("Volitelná poznámka")
        self.notes_edit.setMaximumHeight(85)
        self.suro_check = QCheckBox("Zahrnout do přípravy pro SÚRO", self)
        self.suro_check.setChecked(True)
        self.hint_label = QLabel(self)
        self.hint_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Typ úseku:", self.type_combo)
        form.addRow("Název:", self.title_edit)
        form.addRow("Výška detektoru:", self.height_spin)
        form.addRow("Orientace detektoru:", self.orientation_combo)
        form.addRow("Popis trasy:", self.route_edit)
        form.addRow("Poznámka:", self.notes_edit)
        form.addRow("", self.suro_check)

        self.confirm_button = QPushButton("Potvrdit jako úsek", self)
        self.confirm_button.clicked.connect(self._confirm)
        self.dismiss_button = QPushButton("Přeskočit návrh", self)
        self.dismiss_button.clicked.connect(self._dismiss)
        self.focus_button = QPushButton("Ukázat v mapě", self)
        self.focus_button.clicked.connect(self._focus)
        close_button = QPushButton("Zavřít", self)
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.focus_button)
        buttons.addWidget(self.confirm_button)
        buttons.addWidget(self.dismiss_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Automatické návrhy jsou pouze pomůcka. Potvrzením vznikne "
                "trvalý úsek; původní LOG se nikdy nemění.",
                self,
            )
        )
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.hint_label)
        layout.addLayout(form)
        layout.addLayout(buttons)

        self._reload()

    @staticmethod
    def _duration_text(proposal) -> str:
        seconds = max(0, int((proposal.end - proposal.start).total_seconds()))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (
            f"{hours:d}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes:d}:{seconds:02d}"
        )

    def _reload(self):
        self.proposals = self.repository.list_mission_segment_proposals(
            self.mission_id
        )
        self.table.setRowCount(len(self.proposals))
        for row_index, proposal in enumerate(self.proposals):
            values = (
                proposal.logical_date or proposal.start.date().isoformat(),
                proposal.start.strftime("%H:%M:%S"),
                proposal.end.strftime("%H:%M:%S"),
                PROPOSAL_LABELS[proposal.proposal_type],
                self._duration_text(proposal),
                proposal.source_name or "",
                proposal.reason,
            )
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))
        self.summary_label.setText(
            f"Čeká na kontrolu: {len(self.proposals)} návrhů."
            if self.proposals
            else "V aktivní misi nejsou žádné nevyřízené návrhy."
        )
        if self.proposals:
            self.table.selectRow(0)
        else:
            self.confirm_button.setEnabled(False)
            self.dismiss_button.setEnabled(False)
            self.focus_button.setEnabled(False)
            self.hint_label.setText("")

    def _selected(self):
        row = self.table.currentRow()
        return self.proposals[row] if 0 <= row < len(self.proposals) else None

    def _set_segment_type(self, segment_type: SegmentType):
        for index in range(self.type_combo.count()):
            if self.type_combo.itemData(index) == segment_type.value:
                self.type_combo.setCurrentIndex(index)
                return

    def _selection_changed(self):
        proposal = self._selected()
        if proposal is None:
            return
        defaults = {
            ProposalType.STATIONARY: SegmentType.STATIONARY,
            ProposalType.GPS_LOSS: SegmentType.INDOOR,
            ProposalType.RECORDING_GAP: SegmentType.UNCLASSIFIED,
        }
        self._set_segment_type(defaults[proposal.proposal_type])
        is_gap = proposal.proposal_type is ProposalType.RECORDING_GAP
        self.confirm_button.setEnabled(not is_gap)
        self.dismiss_button.setEnabled(True)
        self.focus_button.setEnabled(True)
        if is_gap:
            self.hint_label.setText(
                "Toto je návrh hranice mezi úseky, nikoli samotný měřicí "
                "úsek. Zatím jej můžeš přeskočit; použití hranic doplní "
                "následující mapový editor."
            )
        else:
            self.hint_label.setText(
                "Zkontroluj typ a doplň pouze údaje, které znáš. Vše lze "
                "později upravit."
            )

    def _focus(self):
        proposal = self._selected()
        if proposal is not None:
            self.proposal_focus_requested.emit(proposal)

    def _confirm(self):
        proposal = self._selected()
        if proposal is None:
            return
        height = self.height_spin.value()
        try:
            self.repository.confirm_segment_proposal(
                proposal.id,
                self.mission_id,
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
        self._clear_form()
        self._reload()

    def _dismiss(self):
        proposal = self._selected()
        if proposal is None:
            return
        try:
            self.repository.dismiss_segment_proposal(proposal.id)
        except Exception as exc:
            QMessageBox.critical(self, "CzechRad Studio", str(exc))
            return
        self._clear_form()
        self._reload()

    def _clear_form(self):
        self.title_edit.clear()
        self.height_spin.setValue(-1.0)
        self.orientation_combo.setCurrentIndex(0)
        self.route_edit.clear()
        self.notes_edit.clear()
        self.suro_check.setChecked(True)
