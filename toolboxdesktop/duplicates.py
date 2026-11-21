from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
from .common import label, button, run_job, configure_dialog
from .operations import scan_duplicates, recycle_duplicates


class DuplicateDialog(QDialog):
    def __init__(self, parent, folder=None):
        super().__init__(parent)
        self.setWindowTitle("Remove Duplicate Files")
        configure_dialog(self, 1050, 680, (700, 400))
        self.duplicates = []
        self.scanned_folder = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(16)
        layout.addWidget(label("A cleaner folder. Nothing lost.", "title"))
        layout.addWidget(label("Find identical contents across all file types, even with different names. Keep one original and review each copy.", "subtitle", True))
        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setReadOnly(True)
        if folder:
            self.folder.setText(str(folder))
        self.folder.setPlaceholderText("Select a folder to scan")
        row.addWidget(self.folder, 1)
        row.addWidget(button("Choose folder…", self.choose_folder))
        self.scan_button = button("Scan folder", self.scan, True)
        row.addWidget(self.scan_button)
        layout.addLayout(row)
        self.recursive = QCheckBox("Include subfolders")
        layout.addWidget(self.recursive)
        self.summary = label("Choose a folder to begin. Matching filenames alone never trigger removal.", "muted", True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Remove", "Duplicate copy", "Original to keep", "Size"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("Select all copies", lambda: self.select_all(True)))
        actions.addWidget(button("Clear selection", lambda: self.select_all(False)))
        actions.addStretch()
        self.recycle_button = button("Move selected to Recycle Bin", self.recycle, True)
        self.recycle_button.setEnabled(False)
        actions.addWidget(self.recycle_button)
        layout.addLayout(actions)
        layout.addWidget(label("Files can be restored from the Windows Recycle Bin. Original copies are kept.", "muted", True))

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder")
        if folder:
            self.folder.setText(folder)
            self.duplicates = []
            self.scanned_folder = None
            self.table.setRowCount(0)
            self.recycle_button.setEnabled(False)

    def scan(self):
        if not self.folder.text():
            return
        folder = self.folder.text()
        recursive = self.recursive.isChecked()
        run_job(self, "Scan duplicate files", lambda progress, message: scan_duplicates(folder, recursive, progress),
                lambda result: self.show_results(folder, result))

    def show_results(self, folder, result):
        self.duplicates, warnings, total = result
        self.scanned_folder = folder
        self.table.setRowCount(len(self.duplicates))
        for row, item in enumerate(self.duplicates):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            for col, text in ((1, str(item.copy)), (2, str(item.original)), (3, f"{item.size / 1024:,.1f} KB")):
                cell = QTableWidgetItem(text)
                cell.setToolTip(text)
                self.table.setItem(row, col, cell)
        size = sum(d.size for d in self.duplicates) / (1024*1024)
        self.summary.setText(f"{total} files scanned  ·  {len(self.duplicates)} identical copies  ·  {size:,.2f} MB recoverable" + (f"  ·  {len(warnings)} skipped" if warnings else ""))
        self.recycle_button.setEnabled(bool(self.duplicates))
        if warnings:
            QMessageBox.information(self, "Files skipped", "\n".join(warnings[:30]))

    def select_all(self, checked):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def recycle(self):
        items = [d for row, d in enumerate(self.duplicates) if self.table.item(row, 0).checkState() == Qt.CheckState.Checked]
        if not items:
            return
        if QMessageBox.question(self, "Move duplicate copies?", f"Move {len(items)} selected duplicate copies to the Recycle Bin? Originals will remain in place.") != QMessageBox.StandardButton.Yes:
            return
        def finished(result):
            removed, errors = result
            QMessageBox.information(self, "Cleanup finished", f"Moved {len(removed)} copies to the Recycle Bin." + ("\n\n" + "\n".join(errors[:20]) if errors else ""))
            self.duplicates = []
            self.table.setRowCount(0)
            self.recycle_button.setEnabled(False)
            self.summary.setText("Cleanup complete. Scan again to refresh the folder.")
        run_job(self, "Remove duplicate files", lambda progress, message: recycle_duplicates(items, self.scanned_folder, progress), finished)
