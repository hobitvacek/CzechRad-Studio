"""Settings dialog for read-only card monitoring and local archiving."""

from pathlib import Path

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..qt_compat import BUTTON_CANCEL, BUTTON_SAVE


class MonitorDialog(QDialog):
    """Configure a source card/folder and a separate archive folder."""

    SOURCE_KEY = "CzechRadStudio/monitorSource"
    ARCHIVE_KEY = "CzechRadStudio/monitorArchive"
    ENABLED_KEY = "CzechRadStudio/monitorEnabled"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CzechRad Studio – automatický import")
        self.setModal(True)
        self.resize(720, 210)
        settings = QSettings()

        self.source_edit = QLineEdit(
            settings.value(self.SOURCE_KEY, "", type=str), self
        )
        self.source_edit.setPlaceholderText("Kořen karty nebo složka s LOGy")
        self.archive_edit = QLineEdit(
            settings.value(self.ARCHIVE_KEY, "", type=str), self
        )
        self.archive_edit.setPlaceholderText("Archiv mimo kartu, například D:\\Radiace")
        self.enabled_checkbox = QCheckBox("Automatické sledování je aktivní", self)
        self.enabled_checkbox.setChecked(
            settings.value(self.ENABLED_KEY, False, type=bool)
        )

        source_button = QPushButton("Vybrat…", self)
        source_button.clicked.connect(self._choose_source)
        archive_button = QPushButton("Vybrat…", self)
        archive_button.clicked.connect(self._choose_archive)

        form = QFormLayout()
        form.addRow("Karta / zdroj:", self._path_row(self.source_edit, source_button))
        form.addRow("Místní archiv:", self._path_row(self.archive_edit, archive_button))

        buttons = QDialogButtonBox(
            BUTTON_SAVE | BUTTON_CANCEL,
            parent=self,
        )
        buttons.button(BUTTON_SAVE).setText("Uložit")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.enabled_checkbox)
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
    def source_folder(self) -> str:
        return self.source_edit.text().strip()

    @property
    def archive_folder(self) -> str:
        return self.archive_edit.text().strip()

    @property
    def enabled(self) -> bool:
        return self.enabled_checkbox.isChecked()

    def _choose_source(self):
        path = QFileDialog.getExistingDirectory(
            self, "Vybrat kartu nebo zdrojovou složku", self.source_folder
        )
        if path:
            self.source_edit.setText(path)

    def _choose_archive(self):
        path = QFileDialog.getExistingDirectory(
            self, "Vybrat místní archiv", self.archive_folder
        )
        if path:
            self.archive_edit.setText(path)

    def accept(self):
        source = Path(self.source_folder)
        archive = Path(self.archive_folder)
        if self.enabled and not source.is_dir():
            QMessageBox.warning(self, "CzechRad Studio", "Vyber dostupnou kartu nebo zdrojovou složku.")
            return
        if self.enabled and not self.archive_folder:
            QMessageBox.warning(self, "CzechRad Studio", "Vyber místní archiv.")
            return
        if self.enabled:
            source_resolved = source.resolve()
            archive_resolved = archive.resolve()
            if (
                archive_resolved == source_resolved
                or source_resolved in archive_resolved.parents
                or archive_resolved in source_resolved.parents
            ):
                QMessageBox.warning(
                    self,
                    "CzechRad Studio",
                    "Archiv musí být v samostatné složce mimo kartu.",
                )
                return

        settings = QSettings()
        settings.setValue(self.SOURCE_KEY, self.source_folder)
        settings.setValue(self.ARCHIVE_KEY, self.archive_folder)
        settings.setValue(self.ENABLED_KEY, self.enabled)
        super().accept()
