from __future__ import annotations

import traceback
from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl, QSize
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QProgressBar, QTextEdit, QMessageBox, QApplication, QSizePolicy)


class ElidedLabel(QLabel):
    """Long filenames must yield width to actions instead of pushing them offscreen."""
    def __init__(self, text=""):
        self.full_text = str(text)
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text):
        self.full_text = str(text)
        super().setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideMiddle, max(20, self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QLabel.setText(self, self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideMiddle, max(20, self.width())))

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


def configure_dialog(dialog, width=1000, height=680, minimum=(640, 400)):
    """Use logical screen bounds, including Windows taskbar and title-bar space."""
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
    dialog.setSizeGripEnabled(True)
    screen = dialog.parent().screen() if dialog.parent() else QApplication.primaryScreen()
    available = screen.availableGeometry()
    dialog.setMinimumSize(min(minimum[0], available.width()-48), min(minimum[1], available.height()-80))
    dialog.resize(min(width, available.width()-64), min(height, available.height()-96))


def label(text, name="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    return widget


class Worker(QThread):
    progress = Signal(int, int)
    message = Signal(str)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.result.emit(self.function(self.progress.emit, self.message.emit))
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)


class JobDialog(QDialog):
    """Keeps work off the GUI thread; never destroys an active worker."""
    def __init__(self, parent, title, function, on_result=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(580, 330)
        configure_dialog(self, 660, 450, (480, 300))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)
        layout.addWidget(label(title, "section"))
        self.status = label("Working…", "subtitle", True)
        layout.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        self.close_button = button("Close", self.accept)
        self.close_button.setEnabled(False)
        layout.addWidget(self.close_button)
        self.worker = Worker(function, self)
        self.worker.progress.connect(self.update_progress)
        self.worker.message.connect(self.log.append)
        self.worker.result.connect(lambda result: self.complete(result, on_result))
        self.worker.failed.connect(self.fail)
        self.worker.finished.connect(lambda: self.close_button.setEnabled(True))
        self.worker.start()

    def update_progress(self, current, total):
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(current)

    def complete(self, result, callback):
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.status.setText("Completed")
        if callback:
            callback(result)
        self.record("Completed")

    def fail(self, message):
        self.status.setText("Could not complete this task")
        self.log.append(message)
        self.bar.setRange(0, 1)
        self.record("Failed")

    def record(self, status):
        owner = self.parent()
        while owner is not None and not hasattr(owner, "record_job"):
            owner = owner.parent()
        if owner is not None:
            owner.record_job(self.windowTitle(), status)

    def reject(self):
        if not self.worker.isRunning():
            super().reject()

    def closeEvent(self, event):
        if self.worker.isRunning():
            event.ignore()
        else:
            event.accept()


def run_job(parent, title, function, on_result=None):
    dialog = JobDialog(parent, title, function, on_result)
    dialog.exec()


def reveal(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def error(parent, exc):
    QMessageBox.warning(parent, "Please check your selection", str(exc))
