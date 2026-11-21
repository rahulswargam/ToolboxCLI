from pathlib import Path
from copy import deepcopy
import io
import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from toolboxdesktop.catalog import TOOLS
from toolboxdesktop.pdf_workspace import PdfWorkspace
from toolboxdesktop.pdf_forms import native_fields, detect_fields, save_filled_pdf
from toolboxdesktop.common import configure_dialog
from test_desktop_ui import window


def settle():
    for _ in range(4):
        QApplication.instance().processEvents()


@pytest.fixture
def form_pdf(tmp_path):
    path = tmp_path / "application.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.insert_text((50, 45), "APPLICATION FORM", fontsize=20)
        page.insert_text((50, 115), "Full name:")
        text = fitz.Widget()
        text.field_name = "full_name"
        text.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        text.rect = fitz.Rect(150, 98, 470, 125)
        text.field_flags = fitz.PDF_FIELD_IS_REQUIRED
        text.field_value = ""
        page.add_widget(text)
        page.insert_text((50, 165), "Department:")
        choice = fitz.Widget()
        choice.field_name = "department"
        choice.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX
        choice.rect = fitz.Rect(150, 148, 470, 175)
        choice.choice_values = ["Engineering", "Design"]
        choice.field_value = "Engineering"
        page.add_widget(choice)
        check = fitz.Widget()
        check.field_name = "accepted"
        check.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
        check.rect = fitz.Rect(50, 200, 68, 218)
        page.add_widget(check)
        page.insert_text((82, 214), "I confirm these details")
        page.draw_rect(fitz.Rect(50, 300, 480, 340))
        page.insert_text((50, 290), "Address:")
        page.draw_rect(fitz.Rect(50, 400, 300, 445))
        page.insert_text((50, 465), "Applicant Signature")
        doc.new_page(width=600, height=800)
        doc.save(path)
    return path


def test_native_form_values_round_trip_and_flatten(form_pdf, tmp_path):
    before = form_pdf.read_bytes()
    with fitz.open(form_pdf) as doc:
        fields = native_fields(doc[0])
    ids = {f["name"]: f["id"] for f in fields}
    values = {ids["full_name"]: "Rahul Swargam", ids["department"]: "Design", ids["accepted"]: True}
    destination = tmp_path / "filled.pdf"
    save_filled_pdf(form_pdf, destination, values, [])
    with fitz.open(destination) as doc:
        result = {w.field_name: w.field_value for w in doc[0].widgets()}
        assert result["full_name"] == "Rahul Swargam"
        assert result["department"] == "Design"
        assert result["accepted"] != "Off"
        assert "Rahul Swargam" in doc[0].get_text()
    assert before == form_pdf.read_bytes()
    save_filled_pdf(form_pdf, tmp_path / "flattened.pdf", values, [], True)
    with fitz.open(tmp_path / "flattened.pdf") as doc:
        assert not list(doc[0].widgets() or [])
        assert "Rahul Swargam" in doc[0].get_text()


def test_flat_entries_and_signatures_export_on_multiple_pages(form_pdf, tmp_path):
    png = io.BytesIO()
    Image.new("RGB", (180, 50), (10, 10, 10)).save(png, "PNG")
    entries = [
        dict(kind="text", page=0, box=[.1, .65, .7, .08], text="123 Example Road", font=12),
        dict(kind="check", page=0, box=[.1, .8, .03, .03]),
        dict(kind="signature", page=0, box=[.1, .85, .3, .05], png=png.getvalue()),
        dict(kind="signature", page=1, box=[.2, .6, .3, .05], png=png.getvalue()),
    ]
    out = tmp_path / "flat-filled.pdf"
    save_filled_pdf(form_pdf, out, {}, entries)
    with fitz.open(out) as doc:
        assert "123 Example Road" in doc[0].get_text()
        assert doc[0].get_image_info() and doc[1].get_image_info()
    entries[0]["box"] = [.9, .9, .4, .1]
    with pytest.raises(ValueError):
        save_filled_pdf(form_pdf, tmp_path / "bad.pdf", {}, entries)
    with pytest.raises(FileExistsError):
        save_filled_pdf(form_pdf, form_pdf, {}, [])


def test_detects_native_fields_static_boxes_and_signature_label(form_pdf):
    fields, message = detect_fields(form_pdf, 0)
    assert {f["name"] for f in fields if f["native"]} == {"full_name", "department", "accepted"}
    assert any(f["kind"] == "signature" for f in fields)
    assert any(not f["native"] and f["kind"] == "text" for f in fields)
    assert "review" in message.lower()


def test_ocr_finds_signature_on_scanned_form(tmp_path):
    image = Image.new("RGB", (1000, 1200), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30)
    draw.text((70, 80), "APPLICATION FORM", font=font, fill="black")
    draw.rectangle((70, 800, 650, 910), outline="black", width=3)
    draw.text((70, 940), "Applicant Signature", font=font, fill="black")
    data = io.BytesIO()
    image.save(data, "PNG")
    path = tmp_path / "scan.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=500, height=600)
        page.insert_image(page.rect, stream=data.getvalue())
        doc.save(path)
    fields, message = detect_fields(path, 0, use_ocr=True)
    assert any(f["kind"] == "signature" for f in fields)
    assert "OCR" in message


def test_favorite_click_does_not_navigate_scroll_or_open_tool(window, monkeypatch):
    opened = []
    monkeypatch.setattr(window, "open_tool", lambda tool: opened.append(tool.key))
    window.populate()
    window.show()
    settle()
    scroll = window.tools_scroll.verticalScrollBar()
    scroll.setValue(scroll.maximum())
    settle()
    card = window.card_widgets[-1]
    key = card.tool.key
    previous = key in window.favorites
    position = scroll.value()
    QTest.mouseClick(card.favorite_button, Qt.MouseButton.LeftButton)
    settle()
    assert (key in window.favorites) != previous
    assert scroll.value() == position and not opened
    assert window.card_widgets[-1] is card
    QTest.mouseClick(card.favorite_button, Qt.MouseButton.LeftButton)
    assert (key in window.favorites) == previous


def test_clicking_card_text_opens_once_and_keyboard_opens(window, monkeypatch):
    opened = []
    monkeypatch.setattr(window, "open_tool", lambda tool: opened.append(tool.key))
    window.populate()
    window.show()
    settle()
    card = window.card_widgets[0]
    QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.description.geometry().center())
    assert opened == [card.tool.key]
    card.setFocus()
    QTest.keyClick(card, Qt.Key.Key_Return)
    assert opened == [card.tool.key, card.tool.key]


def test_workspace_preview_resize_undo_and_page_state(window, form_pdf):
    tool = next(t for t in TOOLS if t.key == "fill_pdf")
    editor = PdfWorkspace(window, tool, files=[str(form_pdf)])
    editor.show()
    settle()
    assert editor.doc and editor.view.page_rect.width() == 600
    assert len(editor.field_proxies) >= 3
    assert editor.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
    editor.name.setText("Rahul Swargam")
    editor.create_signature()
    editor.page_clicked(QPointF(100, 500))
    item = next(iter(editor.entry_items.values()))
    before = editor.snapshot()
    original_width = item.rect.width()
    item.anchor = item.pos()
    item.resize_from_corner(item.pos()+QPointF(original_width*1.5, 100))
    item.sync()
    editor.commit_drag(before)
    assert item.rect.width() > original_width
    enlarged_box = list(item.entry["box"])
    editor.undo()
    assert editor.annotations[0]["box"] != enlarged_box
    editor.redo()
    assert editor.annotations[0]["box"] == enlarged_box
    editor.pages.setCurrentRow(1)
    settle()
    editor.add_entry("text", QPointF(50, 100), 180, 35, "Second page")
    editor.pages.setCurrentRow(0)
    settle()
    assert len(editor.annotations) == 2
    assert next(iter(editor.entry_items.values())).entry["box"] == enlarged_box
    editor.focus_button.setChecked(True)
    editor.toggle_focus()
    settle()
    assert not editor.panel.isVisible() and not editor.pages.isVisible()
    editor.dirty = False
    editor.reject()


def test_every_tool_dialog_is_resizable_and_fits_available_screen(window):
    for tool in TOOLS:
        dialog = window.create_tool_dialog(tool)
        dialog.show()
        settle()
        assert dialog.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint, tool.key
        available = dialog.screen().availableGeometry()
        assert dialog.width() <= available.width(), tool.key
        assert dialog.height() <= available.height()-20, (tool.key, dialog.height(), available.height())
        dialog.reject()


def test_native_signature_field_is_detected_without_changing_its_certificate_value(form_pdf, tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, TextStringObject, ArrayObject, NumberObject
    writer = PdfWriter(clone_from=str(form_pdf))
    sig = DictionaryObject({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
                            NameObject("/FT"): NameObject("/Sig"), NameObject("/T"): TextStringObject("applicant_signature"),
                            NameObject("/Rect"): ArrayObject([NumberObject(v) for v in (50, 355, 300, 400)])})
    ref = writer._add_object(sig)
    writer.pages[0]["/Annots"].append(ref)
    writer.root_object["/AcroForm"]["/Fields"].append(ref)
    path = tmp_path / "native-signature.pdf"
    writer.write(path)
    fields, _ = detect_fields(path, 0)
    signature = next(f for f in fields if f.get("name") == "applicant_signature")
    assert signature["kind"] == "signature" and signature["native"] and not signature["signed"]
    save_filled_pdf(path, tmp_path / "sig-copy.pdf", {signature["id"]: "must not become a certificate"}, [])
    with fitz.open(tmp_path / "sig-copy.pdf") as doc:
        assert not next(w for w in doc[0].widgets() if w.field_name == "applicant_signature").is_signed


def test_native_radio_group_keeps_one_selection(form_pdf, tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, TextStringObject, ArrayObject, NumberObject, DecodedStreamObject
    writer = PdfWriter(clone_from=str(form_pdf))
    parent = DictionaryObject({NameObject("/FT"): NameObject("/Btn"), NameObject("/Ff"): NumberObject(32768),
                               NameObject("/T"): TextStringObject("contact_method"), NameObject("/V"): NameObject("/Email"), NameObject("/Kids"): ArrayObject()})
    parent_ref = writer._add_object(parent)
    for index, name in enumerate(("Email", "Phone")):
        stream = DecodedStreamObject()
        stream.set_data(b"q Q")
        stream.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                       NameObject("/BBox"): ArrayObject([NumberObject(v) for v in (0, 0, 16, 16)])})
        appearance = writer._add_object(stream)
        widget = DictionaryObject({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
                                   NameObject("/Parent"): parent_ref,
                                   NameObject("/Rect"): ArrayObject([NumberObject(v) for v in (50+index*40, 500, 66+index*40, 516)]),
                                   NameObject("/AS"): NameObject("/Email" if index == 0 else "/Off"),
                                   NameObject("/AP"): DictionaryObject({NameObject("/N"): DictionaryObject({NameObject("/Off"): appearance, NameObject("/"+name): appearance})})})
        ref = writer._add_object(widget)
        parent["/Kids"].append(ref)
        writer.pages[0]["/Annots"].append(ref)
    writer.root_object["/AcroForm"]["/Fields"].append(parent_ref)
    source = tmp_path / "radios.pdf"
    writer.write(source)
    with fitz.open(source) as doc:
        fields = [f for f in native_fields(doc[0]) if f["kind"] == "radio"]
    assert len(fields) == 2 and sum(bool(f["value"]) for f in fields) == 1
    for choice in ("Phone", "Email"):
        path = tmp_path / f"radio-{choice}.pdf"
        save_filled_pdf(source, path, {f["id"]: f["on"] == choice for f in fields}, [])
        with fitz.open(path) as doc:
            after = [f for f in native_fields(doc[0]) if f["kind"] == "radio"]
            assert sum(bool(f["value"]) for f in after) == 1
            assert next(f for f in after if f["value"])["on"] == choice


def test_real_mouse_drag_resizes_signature_handle(window, form_pdf):
    editor = PdfWorkspace(window, next(t for t in TOOLS if t.key == "sign_pdf"), files=[str(form_pdf)])
    editor.showMaximized()
    settle()
    editor.name.setText("Sample Applicant")
    editor.create_signature()
    editor.page_clicked(QPointF(100, 550))
    item = next(iter(editor.entry_items.values()))
    settle()
    old_width = item.rect.width()
    start = editor.view.mapFromScene(item.mapToScene(item.rect.bottomRight()))
    finish = editor.view.mapFromScene(item.mapToScene(item.rect.bottomRight()+QPointF(70, 25)))
    QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(editor.view.viewport(), finish, 80)
    QTest.mouseRelease(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=finish)
    settle()
    assert item.rect.width() > old_width
    editor.dirty = False
    editor.reject()


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_form_preview_and_saved_signature_match_display_coordinates(window, form_pdf, tmp_path, rotation):
    source = tmp_path / f"rotated-{rotation}.pdf"
    with fitz.open(form_pdf) as doc:
        doc[0].set_rotation(rotation)
        doc.save(source)
    editor = PdfWorkspace(window, next(t for t in TOOLS if t.key == "fill_pdf"), files=[str(source)])
    editor.show()
    settle()
    assert all(proxy.rotation() == rotation for proxy in editor.field_proxies.values())
    png = io.BytesIO()
    Image.new("RGB", (150, 40), (0, 0, 220)).save(png, "PNG")
    output = tmp_path / f"saved-{rotation}.pdf"
    save_filled_pdf(source, output, {}, [dict(page=0, kind="signature", png=png.getvalue(), box=[.1, .7, .4, .1])])
    with fitz.open(output) as doc:
        pix = doc[0].get_pixmap()
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        r, g, b = image.getpixel((round(pix.width*.3), round(pix.height*.75)))
        assert b > 180 and r < 30 and g < 30
    editor.reject()


@pytest.mark.parametrize("key", ["fill_pdf", "rotate_pdf"])
def test_long_filename_cannot_push_header_controls_outside_dialog(window, key):
    editor = window.create_tool_dialog(next(t for t in TOOLS if t.key == key))
    editor.filename.setText("A very long application document name " * 20 + ".pdf")
    editor.resize(800, 500)
    editor.show()
    settle()
    assert editor.filename.minimumSizeHint().width() < 100
    if key == "fill_pdf":
        assert editor.rect().contains(editor.maximize_button.geometry())
        assert editor.rect().contains(editor.focus_button.geometry())
    assert len(editor.filename.text()) < len(editor.filename.full_text)
    editor.reject()
