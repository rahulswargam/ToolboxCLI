"""Opt-in packaged-build verification, used by release engineering."""
from pathlib import Path
import json
import traceback
import io


def self_test(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    report = {"passed": [], "error": None}
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from PIL import Image
        import fitz
        from .app import MainWindow
        from .catalog import TOOLS
        from .style import STYLE
        from .forms import ToolForm
        from .pdf_editor import PdfEditor
        from .duplicates import DuplicateDialog
        from .operations import merge_pdf, edit_pdf, sign_pdf, compress_pdf, scan_duplicates, recycle_duplicates
        from toolboxcli.core.platform import OUTPUT_ROOT
        from toolboxcli.core.runners import RUNNERS, Done

        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(folder / "settings"))
        app = QApplication.instance() or QApplication([])
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        window = MainWindow(settings_dir=folder / "settings")
        window.output_root = str(folder)
        window.show()
        app.processEvents()
        window.grab().save(str(folder / "dashboard.png"))
        for mode in ("dark", "light"):
            window.theme_choice.setCurrentIndex(window.theme_choice.findData(mode))
            app.processEvents()
            app.processEvents()
            assert window.active_theme == mode
            window.grab().save(str(folder / f"dashboard-{mode}.png"))
        window.theme_choice.setCurrentIndex(window.theme_choice.findData("auto"))
        assert window.settings.path.is_file() and window.settings.value("theme") == "auto"
        report["passed"].append("Dark, Light and Auto themes with JSON settings folder")
        app.processEvents()
        app.processEvents()
        assert window.brand_mark.size().width() == 48 and window.brand_mark.size().height() == 48
        assert len({card.description.y() for card in window.card_widgets}) == 1
        assert len({card.launch.y() for card in window.card_widgets}) == 1
        window.resize(960, 640)
        app.processEvents()
        app.processEvents()
        assert window.card_columns == 2
        window.resize(1280, 680)
        app.processEvents()
        app.processEvents()
        assert window.card_columns == 3
        report["passed"].append("Aligned card baselines, unclipped logo and responsive two/three-column grid")
        for tool in TOOLS:
            dialog = window.create_tool_dialog(tool)
            dialog.reject()
        report["passed"].append(f"All {len(TOOLS)} tool dialogs and dashboard")

        source = folder / "source.pdf"
        with fitz.open() as doc:
            for i in range(3):
                page = doc.new_page()
                page.insert_text((40, 50), f"Verification page {i+1}")
            doc.save(source)
        window.ingest_paths([source])
        assert "sign_pdf" in {t.key for t in window.visible_tools()}
        form = window.create_tool_dialog(next(t for t in TOOLS if t.key == "resize_pdf"))
        assert Path(form.paths["file"]) == source.resolve()
        form.reject()
        editor = window.create_tool_dialog(next(t for t in TOOLS if t.key == "sign_pdf"))
        assert Path(editor.source) == source.resolve()
        editor.reject()
        window.clear_selection()
        assert len(window.visible_tools()) == len(TOOLS)
        report["passed"].append("File-aware recommendations and preloaded PDF forms and editors")
        from .pdf_forms import native_fields, save_filled_pdf, detect_fields
        from .pdf_workspace import PdfWorkspace
        from PySide6.QtCore import QPointF
        form_source = folder / "application-form.pdf"
        with fitz.open() as doc:
            page = doc.new_page(width=600, height=800)
            page.insert_text((40, 45), "APPLICATION FORM")
            field = fitz.Widget()
            field.field_name = "full_name"
            field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
            field.rect = fitz.Rect(50, 100, 400, 130)
            page.add_widget(field)
            page.insert_text((50, 190), "Account number:")
            for index in range(12):
                page.draw_rect(fitz.Rect(50+index*18,200,66+index*18,219),width=.5)
            page.draw_rect(fitz.Rect(50, 500, 300, 550))
            page.insert_text((50, 570), "Applicant Signature")
            doc.save(form_source)
        workspace = PdfWorkspace(window, next(t for t in TOOLS if t.key == "fill_pdf"), files=[str(form_source)])
        workspace.show()
        app.processEvents()
        fields = native_fields(workspace.doc[0])
        workspace.set_field(fields[0], "Packaged Applicant")
        from .field_editors import CombLineEdit
        from PySide6.QtTest import QTest
        comb = next(field for field in workspace.fields_by_page[0] if field['kind'] == 'comb')
        workspace.activate_field(comb)
        inline = workspace.field_proxies[comb['id']].widget()
        assert isinstance(inline, CombLineEdit)
        QTest.keyClicks(inline, '001234567890')
        assert workspace.values[comb['id']] == '001234567890' and not workspace.annotations
        workspace.name.setText("Packaged Applicant")
        workspace.create_signature()
        workspace.page_clicked(QPointF(60, 510))
        workspace.resize_signature(1.1)
        workspace.view.fit_width()
        app.processEvents()
        workspace.grab().save(str(folder / "fill-sign-workspace.png"))
        save_filled_pdf(form_source, folder / "filled-application.pdf", workspace.values, workspace.annotations, detected_fields=workspace.fields_by_page[0])
        with fitz.open(folder / "filled-application.pdf") as doc:
            assert "Packaged Applicant" in doc[0].get_text()
            assert doc[0].get_image_info()
            assert any(field['kind'] == 'comb' and field['value'] == '001234567890' for field in native_fields(doc[0]))
        workspace.dirty = False
        workspace.reject()
        report["passed"].append("Interactive form filling, signature handles and saved PDF round trip")
        report["passed"].append("Detected character boxes: inline typing, leading zeros and editable comb export")
        from PIL import ImageDraw, ImageFont
        scan = Image.new("RGB", (1000, 1200), "white")
        draw = ImageDraw.Draw(scan)
        draw.rectangle((70, 800, 650, 910), outline="black", width=3)
        draw.text((70, 940), "Applicant Signature", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30))
        scan_data = io.BytesIO()
        scan.save(scan_data, "PNG")
        scan_source = folder / "scanned-application.pdf"
        with fitz.open() as doc:
            page = doc.new_page(width=500, height=600)
            page.insert_image(page.rect, stream=scan_data.getvalue())
            doc.save(scan_source)
        detected, _ = detect_fields(scan_source, 0, True)
        assert any(field["kind"] == "signature" for field in detected)
        report["passed"].append("Bundled local OCR and scanned signature-area detection")
        merge_pdf([source, source], folder / "merged.pdf")
        edit_pdf(source, folder / "rotated.pdf", "rotate", [1], 90)
        edit_pdf(source, folder / "organized.pdf", "organize", [2, 0, 1])
        edit_pdf(source, folder / "removed.pdf", "remove", [1])
        png = io.BytesIO()
        Image.new("RGBA", (200, 60), (10, 20, 130, 255)).save(png, "PNG")
        sign_pdf(source, folder / "signed.pdf", 1, png.getvalue(), (.1, .7, .4, .1))
        compress_pdf(source, folder / "compressed.pdf", 100)
        with fitz.open(folder / "merged.pdf") as doc:
            assert len(doc) == 6
        with fitz.open(folder / "organized.pdf") as doc:
            assert "page 3" in doc[0].get_text()
        with fitz.open(folder / "removed.pdf") as doc:
            assert len(doc) == 2
        report["passed"].append("Merge, rotate, organize, remove, sign and compress PDFs")

        image = folder / "image.png"
        Image.new("RGB", (200, 100), (50, 130, 200)).save(image)
        token = OUTPUT_ROOT.set(folder)
        try:
            for key, values in (
                ("compress_images", {"files": [image], "target_kb": "100"}),
                ("images_to_pdf", {"files": [image]}),
                ("pdf_to_jpg", {"file": source, "dpi": "72"}),
                ("pdf_to_word", {"file": source}),
                ("lock_pdf", {"file": source, "password": "verification"}),
            ):
                assert any(isinstance(event, Done) for event in RUNNERS[key](**values))
                report["passed"].append(key)
            locked = folder / "Locked PDF" / "source.pdf"
            assert any(isinstance(event, Done) for event in RUNNERS["unlock_pdf"](file=locked, password="verification"))
            report["passed"].append("unlock_pdf")
        finally:
            OUTPUT_ROOT.reset(token)
        copies = folder / "duplicates"
        copies.mkdir()
        (copies / "a.txt").write_text("same")
        (copies / "b.dat").write_text("same")
        duplicates, warnings, total = scan_duplicates(copies)
        assert len(duplicates) == 1 and total == 2 and not warnings
        report["passed"].append("Content-based duplicate detection")
        removed, errors = recycle_duplicates(duplicates, copies)
        assert len(removed) == 1 and not errors
        assert duplicates[0].original.exists() and not duplicates[0].copy.exists()
        report["passed"].append("Windows Recycle Bin cleanup preserves original")
        window.close()
    except Exception:
        report["error"] = traceback.format_exc()
    (folder / "self-test.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if report["error"] else 0
