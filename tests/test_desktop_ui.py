import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from toolboxdesktop.app import MainWindow
from toolboxdesktop.catalog import TOOLS
from toolboxdesktop.pdf_editor import PdfEditor


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    w = MainWindow(settings_dir=tmp_path / "settings")
    w.output_root = str(tmp_path)
    yield w
    w.close()
    app.processEvents()


def test_search_category_and_favorites(window):
    window.navigate("PDF Tools")
    window.search.setText("sign")
    assert {t.key for t in window.visible_tools()} == {"sign_pdf", "fill_pdf"}
    window.search.clear()
    window.navigate("Image Tools")
    assert window.grid.count() == 3
    window.navigate("Recent activity")
    assert window.stack.currentWidget() is window.activity_page


def test_all_tools_have_openable_dialogs(window):
    from toolboxdesktop.forms import ToolForm
    from toolboxdesktop.duplicates import DuplicateDialog
    for tool in TOOLS:
        dialog = window.create_tool_dialog(tool)
        assert dialog.windowTitle()
        dialog.reject()


@pytest.mark.parametrize("fails", [False, True])
def test_background_job_delivers_result_or_error_without_freezing(window, monkeypatch, fails):
    from toolboxdesktop.common import JobDialog
    recorded, results = [], []
    monkeypatch.setattr(window, "record_job", lambda title, status: recorded.append(status))

    def work(progress, message):
        progress(1, 2)
        message("Processing a test document")
        if fails:
            raise ValueError("Test document cannot be opened")
        return "saved.pdf"

    dialog = JobDialog(window, "Test operation", work, results.append)
    dialog.worker.finished.connect(dialog.accept)
    dialog.exec()
    assert not dialog.worker.isRunning()
    assert recorded == ["Failed" if fails else "Completed"]
    if fails:
        assert "Test document cannot be opened" in dialog.log.toPlainText()
    else:
        assert results == ["saved.pdf"]
