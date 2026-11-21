import json
from pathlib import Path

from PySide6.QtCore import Qt, QMimeData, QUrl, QPointF
from PySide6.QtGui import QDropEvent
from PIL import Image
import fitz
import pytest

from toolboxdesktop.preferences import Preferences
from toolboxdesktop.intake import selection_kind, recommended_keys, PDF_TOOLS
from toolboxdesktop.catalog import TOOLS
from test_desktop_ui import window


def tool(key):
    return next(t for t in TOOLS if t.key == key)


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "document.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path)
    return path


def test_settings_folder_created_and_preferences_survive_restart(tmp_path):
    folder = tmp_path / "settings"
    prefs = Preferences(folder)
    assert prefs.path.is_file() and prefs.value("theme") == "auto"
    prefs.setValue("theme", "dark")
    prefs.setValue("favorites", ["sign_pdf"])
    assert Preferences(folder).value("theme") == "dark"
    assert json.loads(prefs.path.read_text())["favorites"] == ["sign_pdf"]
    assert not prefs.path.with_suffix(".tmp").exists()


def test_invalid_settings_recover_and_keep_original(tmp_path):
    (tmp_path / "preferences.json").write_text("broken json")
    prefs = Preferences(tmp_path)
    assert prefs.value("theme") == "auto"
    assert (tmp_path / "preferences.invalid.json").read_text() == "broken json"
    prefs.setValue("theme", "unknown")
    assert Preferences(tmp_path).value("theme") == "auto"


def test_theme_immediate_and_auto_only_tracks_system(window, monkeypatch):
    import toolboxdesktop.app as module
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication
    monkeypatch.setattr(module, "system_theme", lambda app: "light")
    window.theme_choice.setCurrentIndex(window.theme_choice.findData("dark"))
    assert window.active_theme == "dark"
    window.system_theme_changed()
    assert window.active_theme == "dark"
    window.theme_choice.setCurrentIndex(window.theme_choice.findData("auto"))
    assert window.active_theme == "light"
    monkeypatch.setattr(module, "system_theme", lambda app: "dark")
    window.system_theme_changed()
    assert window.active_theme == "dark"
    assert window.settings.value("theme") == "auto"
    assert QApplication.palette().color(QPalette.ColorRole.Window).name() == "#111111"
    from toolboxdesktop.app import MainWindow
    reopened = MainWindow(settings_dir=window.settings.folder)
    assert reopened.theme_mode == "auto" and reopened.active_theme == "dark"
    reopened.close()


def test_upload_pdf_recommends_and_prefills_forms_and_editor(window, pdf):
    window.ingest_paths([pdf])
    assert {t.key for t in window.visible_tools()} == PDF_TOOLS
    form = window.create_tool_dialog(tool("resize_pdf"))
    assert Path(form.paths["file"]) == pdf
    form.reject()
    editor = window.create_tool_dialog(tool("sign_pdf"))
    assert Path(editor.source) == pdf and len(editor.doc) == 1
    editor.reject()
    window.clear_selection()
    assert len(window.visible_tools()) == len(TOOLS)


def test_multiple_pdfs_only_offer_merge_and_preserve_order(window, pdf, tmp_path):
    second = tmp_path / "second.pdf"
    second.write_bytes(pdf.read_bytes())
    window.ingest_paths([second, pdf, second])
    assert [t.key for t in window.visible_tools()] == ["merge_pdf"]
    editor = window.create_tool_dialog(tool("merge_pdf"))
    assert editor.pages.count() == 2
    assert editor.pages.item(0).data(Qt.ItemDataRole.UserRole) == str(second)
    editor.reject()


def test_image_upload_and_folder_suggestions_prefill(window, tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (20, 20), "white").save(path)
    window.ingest_paths([path])
    assert {t.key for t in window.visible_tools()} == {"compress_images", "images_to_pdf"}
    form = window.create_tool_dialog(tool("images_to_pdf"))
    assert form.paths["files"] == [str(path)]
    form.reject()
    window.ingest_paths([tmp_path])
    assert {t.key for t in window.visible_tools()} == {"remove_duplicates", "find_duplicates", "rename_by_date"}
    dialog = window.create_tool_dialog(tool("remove_duplicates"))
    assert dialog.folder.text() == str(tmp_path)
    dialog.reject()


def test_webp_does_not_offer_incompatible_images_to_pdf(window, tmp_path):
    path = tmp_path / "image.webp"
    Image.new("RGB", (10, 10)).save(path)
    window.ingest_paths([path])
    assert [t.key for t in window.visible_tools()] == ["compress_images"]


def test_mixed_and_unsupported_selections_offer_guidance(window, pdf, tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Text")
    window.ingest_paths([path, pdf])
    assert not window.visible_tools()
    assert "Choose PDFs together" in window.upload_detail.text()


def test_drag_drop_routes_local_files(window, pdf):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(pdf))])
    event = QDropEvent(QPointF(20, 20), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dropzone.dropEvent(event)
    assert window.selected_paths == [str(pdf)] and event.isAccepted()
    mime.setUrls([QUrl("https://example.com/test.pdf")])
    remote = QDropEvent(QPointF(20, 20), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dropzone.dropEvent(remote)
    assert not remote.isAccepted()
