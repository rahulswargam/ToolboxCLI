"""Generate a synthetic application form and capture the production workspace."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fitz
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QEvent, QCoreApplication
from toolboxdesktop.app import MainWindow
from toolboxdesktop.catalog import TOOLS
from toolboxdesktop.pdf_workspace import PdfWorkspace
from toolboxdesktop.pdf_forms import save_filled_pdf
from toolboxcli.core.platform import unique_path

root = Path(__file__).resolve().parent.parent / "artifacts" / "fill-sign"
root.mkdir(parents=True, exist_ok=True)
source = root / "Sample application.pdf"
with fitz.open() as doc:
    page = doc.new_page(width=600, height=780)
    page.insert_text((44, 56), "Application form", fontsize=28)
    page.insert_text((44, 80), "SAMPLE DOCUMENT  /  Fill & Sign workspace demonstration", fontsize=10)
    page.draw_line((44, 102), (556, 102), color=(.3, .3, .3))
    page.insert_text((44, 135), "01  PERSONAL DETAILS", fontsize=12)
    for field_name, title, box in (
        ("full_name", "Full name", (44, 169, 556, 201)),
        ("email", "Email address", (44, 239, 556, 271)),
        ("phone", "Phone number", (44, 309, 290, 341)),
        ("birth_date", "Date of birth", (310, 309, 556, 341)),
        ("address", "Postal address", (44, 381, 556, 433)),
    ):
        page.insert_text((box[0], box[1]-9), title, fontsize=11)
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = field_name
        widget.rect = fitz.Rect(box)
        widget.field_value = ""
        widget.border_color = (.55, .55, .55)
        widget.border_width = .6
        if field_name == "address":
            widget.field_flags = fitz.PDF_TX_FIELD_IS_MULTILINE
        page.add_widget(widget)
    page.insert_text((44, 490), "02  DECLARATION", fontsize=12)
    check = fitz.Widget()
    check.field_name = "declaration"
    check.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    check.rect = fitz.Rect(44, 515, 60, 531)
    check.border_color = (.3, .3, .3)
    check.border_width = .8
    page.add_widget(check)
    page.insert_text((72, 527), "I confirm that the information provided is correct.", fontsize=11)
    page.draw_rect(fitz.Rect(44, 585, 340, 666), color=(.5, .5, .5), width=.6)
    page.insert_text((44, 687), "Applicant signature", fontsize=11)
    page.insert_text((400, 687), "Date: 21 / 11 / 2026", fontsize=11)
    page.insert_text((44, 742), "Sample data only. No personal documents are used in this preview.", fontsize=9)
    doc.save(source)

app = QApplication([])
app.setStyle("Fusion")
window = MainWindow(settings_dir=root / "settings")
window.output_root = str(root)
window.show()
tool = next(t for t in TOOLS if t.key == "fill_pdf")
editor = PdfWorkspace(window, tool, files=[str(source)])
editor.showMaximized()

def settle():
    for _ in range(6):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

settle()
for field in editor.fields_by_page[0]:
    if field.get("name") in {"full_name", "email", "phone", "birth_date", "address", "declaration"}:
        values = {"full_name": "Alex Morgan", "email": "alex@example.com", "phone": "+1 555 0100", "birth_date": "15 / 06 / 1995", "address": "12 Example Avenue\nSample City, 10001", "declaration": True}
        editor.set_field(field, values[field["name"]])
editor.show_page(0)
editor.name.setText("Alex Morgan")
editor.create_signature()
signature = next(f for f in editor.fields_by_page[0] if f["kind"] == "signature")
editor.activate_field(signature)
editor.panel.setCurrentIndex(1)
for mode in ("light", "dark"):
    window.theme_choice.setCurrentIndex(window.theme_choice.findData(mode))
    editor.view.fit_page()
    settle()
    editor.grab().save(str(root / f"workspace-{mode}.png"))
editor.focus_button.setChecked(True)
editor.toggle_focus()
settle()
editor.grab().save(str(root / "focused-page.png"))
editor.flush_fields()
save_filled_pdf(source, unique_path(root / "Filled sample.pdf"), editor.values, editor.annotations)
editor.dirty = False
editor.reject()
window.close()
print(root)
