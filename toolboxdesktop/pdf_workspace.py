"""A full-page Fill & Sign workspace, shared by signing and form filling."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from pathlib import Path
from uuid import uuid4
import fitz

from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QTimer, QBuffer, QIODevice, QEvent
from PySide6.QtGui import QPixmap, QImage, QPainter, QFont, QFontMetrics, QColor, QFontDatabase, QShortcut, QKeySequence
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QScrollArea, QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem, QTabWidget,
    QListWidget, QListWidgetItem, QFileDialog, QLineEdit, QTextEdit, QComboBox,
    QSizePolicy, QCheckBox, QRadioButton, QSpinBox, QInputDialog, QMessageBox, QProgressBar, QToolBar)
from .common import label, button, configure_dialog, error, Worker, run_job, ElidedLabel
from .operations import open_pdf
from .pdf_forms import native_fields, detect_fields, display_rect, save_filled_pdf
from .pdf_canvas import PageView, EntryItem, FieldHint
from .field_editors import CombLineEdit


class PdfWorkspace(QDialog):
    def __init__(self, parent, tool, files=None):
        super().__init__(parent)
        self.tool = tool
        self.doc = None
        self.source = None
        self.annotations = []
        self.values = {}
        self.fields_by_page = {}
        self.undo_states, self.redo_states = [], []
        self.dirty = False
        self.signature_png = None
        self.mode = "select"
        self.current_page = 0
        self.detection_worker = None
        self.entry_items = {}
        self.field_proxies = {}
        self.setWindowTitle(tool.label)
        configure_dialog(self, 1200, 760, (760, 420))
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(label("Fill & Sign" if tool.key == "fill_pdf" else "Sign PDF", "section"))
        header.addWidget(button("Open PDF…", self.open))
        self.filename = ElidedLabel("Open a PDF to get started")
        self.filename.setObjectName("muted")
        self.filename.setMinimumWidth(0)
        header.addWidget(self.filename, 1)
        self.focus_button = button("Focus page", self.toggle_focus)
        self.focus_button.setCheckable(True)
        header.addWidget(self.focus_button)
        self.maximize_button = button("Maximize", self.toggle_maximize)
        header.addWidget(self.maximize_button)
        root.addLayout(header)
        toolbar = QToolBar(self)
        self.toolbar = toolbar
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.addAction("‹", lambda: self.change_page(-1))
        self.page_indicator = label("No document", "muted")
        toolbar.addWidget(self.page_indicator)
        toolbar.addAction("›", lambda: self.change_page(1))
        toolbar.addSeparator()
        toolbar.addAction("Fit page", lambda: self.view.fit_page())
        toolbar.addAction("Fit width", lambda: self.view.fit_width())
        toolbar.addAction("−", lambda: self.view.zoom_by(1/1.2))
        self.zoom_indicator = label("100%", "muted")
        self.zoom_indicator.setFixedWidth(43)
        self.zoom_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.zoom_indicator)
        toolbar.addAction("+", lambda: self.view.zoom_by(1.2))
        toolbar.addSeparator()
        self.undo_button = toolbar.addAction("Undo", self.undo)
        self.redo_button = toolbar.addAction("Redo", self.redo)
        toolbar.addAction("Delete selected", self.delete_selected)
        root.addWidget(toolbar)

        self.splitter = QSplitter()
        self.pages = QListWidget()
        self.pages.setMinimumWidth(80)
        self.pages.setMaximumWidth(124)
        self.pages.setIconSize(QSize(72, 94))
        self.pages.setViewMode(QListWidget.ViewMode.IconMode)
        self.pages.setFlow(QListWidget.Flow.TopToBottom)
        self.pages.setWrapping(False)
        self.pages.setGridSize(QSize(100, 128))
        self.pages.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.pages.setMovement(QListWidget.Movement.Static)
        self.pages.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pages.currentRowChanged.connect(self.show_page)
        self.splitter.addWidget(self.pages)
        self.scene = QGraphicsScene(self)
        self.view = PageView(self.scene)
        self.view.setBackgroundBrush(QColor("#d0d0d0" if parent.active_theme == "light" else "#303030"))
        self.view.pageClicked.connect(self.page_clicked)
        self.view.deleteRequested.connect(self.delete_selected)
        self.view.zoomChanged.connect(lambda value: self.zoom_indicator.setText(f"{value}%"))
        self.splitter.addWidget(self.view)
        self.panel = QTabWidget()
        self.panel.setMinimumWidth(220)
        self.panel.setMaximumWidth(290)
        self.build_fill_panel()
        self.build_signature_panel()
        if tool.key == "sign_pdf":
            self.panel.setCurrentIndex(1)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([112, 800, 250])
        root.addWidget(self.splitter, 1)
        bottom = QHBoxLayout()
        self.status = label("Open a PDF. Then choose a field or place an entry on the page.", "muted", True)
        bottom.addWidget(self.status, 1)
        self.save_button = button("Save filled PDF…" if tool.key == "fill_pdf" else "Save signed PDF…", self.save, True)
        self.save_button.setEnabled(False)
        bottom.addWidget(self.save_button)
        root.addLayout(bottom)
        self.update_history_buttons()
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.duplicate_selected)
        QShortcut(QKeySequence("Escape"), self.view, activated=lambda: self.set_mode("select"))
        if files:
            self.load_file(files[0])

    def scroll_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)
        inner.setMinimumWidth(0)
        inner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scroll.setWidget(inner)
        return scroll, layout

    def build_fill_panel(self):
        panel, controls = self.scroll_panel()
        controls.addWidget(label("FILL THE BLANKS", "eyebrow"))
        controls.addWidget(label("Click a detected blank and type. Character rows put one character in each printed box. Tab moves to the next field.", "muted", True))
        self.mode_buttons = {}
        fill_button = button("Fill detected blanks",lambda:self.set_mode("fill"),True)
        fill_button.setCheckable(True)
        self.mode_buttons["fill"] = fill_button
        controls.addWidget(fill_button)
        manual_toggle = button("Manual tools ▸",lambda:None)
        manual_toggle.setCheckable(True)
        controls.addWidget(manual_toggle)
        manual = QWidget()
        manual_controls = QVBoxLayout(manual)
        manual_controls.setContentsMargins(0,0,0,0)
        for name, mode in (("Select / move entries", "select"), ("Add text anywhere", "text"), ("Today's date", "date"), ("Checkmark anywhere", "check"), ("Cross anywhere", "cross")):
            b = button(name, lambda checked=False, value=mode: self.set_mode(value))
            b.setCheckable(True)
            self.mode_buttons[mode] = b
            manual_controls.addWidget(b)
        manual_controls.addWidget(label("Manual text size", "muted"))
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 72)
        self.font_size.setValue(12)
        self.font_size.valueChanged.connect(self.change_font)
        manual_controls.addWidget(self.font_size)
        controls.addWidget(manual)
        manual.hide()
        manual_toggle.toggled.connect(manual.setVisible)
        manual_toggle.toggled.connect(lambda active:manual_toggle.setText("Manual tools ▾" if active else "Manual tools ▸"))
        self.highlight_fields = QCheckBox("Show field guides")
        self.highlight_fields.setChecked(True)
        self.highlight_fields.toggled.connect(lambda: self.show_page(self.current_page, keep_zoom=True))
        controls.addWidget(self.highlight_fields)
        self.ocr = QCheckBox("Use local OCR for scans")
        self.ocr.setChecked(True)
        controls.addWidget(self.ocr)
        self.detect_button = button("Detect fields on this page", self.detect)
        controls.addWidget(self.detect_button)
        self.detection_progress = QProgressBar()
        self.detection_progress.setRange(0, 0)
        self.detection_progress.hide()
        controls.addWidget(self.detection_progress)
        controls.addWidget(label("FIELDS ON THIS PAGE", "eyebrow"))
        self.field_list = QListWidget()
        self.field_list.setMinimumHeight(120)
        self.field_list.setMaximumHeight(200)
        self.field_list.itemClicked.connect(lambda item: self.activate_field(item.data(Qt.ItemDataRole.UserRole)))
        controls.addWidget(self.field_list)
        self.flatten = QCheckBox("Flatten fields on save")
        controls.addWidget(self.flatten)
        controls.addWidget(label("Printed blanks become editable PDF fields when saved. Review detection before saving; manual placement is available separately if a blank is missed.", "muted", True))
        controls.addStretch()
        self.panel.addTab(panel, "Fill form")

    def build_signature_panel(self):
        panel, controls = self.scroll_panel()
        controls.addWidget(label("YOUR SIGNATURE", "eyebrow"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Your full name")
        controls.addWidget(self.name)
        self.font_choice = QComboBox()
        fonts = QFontDatabase.families()
        self.font_choice.addItems([f for f in ("Segoe Script", "Lucida Handwriting", "Brush Script MT", "Gabriola") if f in fonts] or ["Segoe UI"])
        controls.addWidget(self.font_choice)
        controls.addWidget(button("Create from name", self.create_signature))
        controls.addWidget(button("Import signature PNG…", self.import_signature))
        self.signature_preview = label("")
        self.signature_preview.setFixedHeight(58)
        self.signature_preview.setStyleSheet("background: white; border:1px solid #aaaaaa; border-radius:5px;")
        self.signature_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(self.signature_preview)
        controls.addWidget(button("Place signature on page", lambda: self.set_mode("signature")))
        controls.addWidget(label("Click the page to place it. Drag the signature to move it; drag any corner handle to make it larger or smaller.", "muted", True))
        controls.addWidget(button("Duplicate selected signature", self.duplicate_selected))
        sizes = QHBoxLayout()
        sizes.addWidget(button("Smaller", lambda: self.resize_signature(.85)))
        sizes.addWidget(button("Larger", lambda: self.resize_signature(1.15)))
        controls.addLayout(sizes)
        controls.addWidget(label("PAGE CONTROLS", "eyebrow"))
        controls.addWidget(label("Fit page shows the entire page. Fit width and + zoom in for precise placement. Ctrl + mouse wheel also zooms. Focus page hides both side panels; F11 uses full screen.", "muted", True))
        controls.addStretch()
        controls.addWidget(label("Visual signatures only. Certificate signature fields are detected but this app does not create or validate certificate-based signatures.", "muted", True))
        self.panel.addTab(panel, "Signature")

    def toggle_focus(self):
        active = self.focus_button.isChecked()
        self.pages.setVisible(not active)
        self.panel.setVisible(not active)
        self.focus_button.setText("Show panels" if active else "Focus page")
        QTimer.singleShot(0, self.view.fit_page)

    def toggle_maximize(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
        self.maximize_button.setText("Restore" if self.isMaximized() else "Maximize")
        QTimer.singleShot(0, self.view.fit_page)

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()
        QTimer.singleShot(0, self.view.fit_page)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.view.fit_page)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "maximize_button"):
            self.maximize_button.setText("Restore" if self.isMaximized() else "Maximize")

    def confirm_discard(self):
        return not self.dirty or QMessageBox.question(self, "Unsaved changes", "Discard the unsaved changes in this document?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def open(self):
        if self.detection_worker and self.detection_worker.isRunning():
            return
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF (*.pdf)")
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            new_doc = open_pdf(path)
            if self.doc:
                self.doc.close()
            self.doc = new_doc
            self.source = str(path)
            self.annotations, self.values = [], {}
            self.fields_by_page = {}
            self.undo_states, self.redo_states = [], []
            self.dirty = False
            self.pages.blockSignals(True)
            self.pages.clear()
            for i in range(len(self.doc)):
                item = QListWidgetItem(f"Page {i+1}")
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.pages.addItem(item)
            self.pages.setCurrentRow(0)
            self.pages.blockSignals(False)
            self.filename.setText(Path(path).name)
            self.filename.setToolTip(str(path))
            self.current_page = 0
            self.show_page(0)
            self.save_button.setEnabled(True)
            self.next_thumbnail = 0
            if hasattr(self, "thumbnail_timer"):
                self.thumbnail_timer.stop()
            self.thumbnail_timer = QTimer(self)
            self.thumbnail_timer.timeout.connect(self.add_thumbnail)
            self.thumbnail_timer.start(12)
            self.update_history_buttons()
            self.set_mode("fill" if self.tool.key == "fill_pdf" else "select")
            if len(self.doc[0].get_text().strip()) < 20 and self.doc[0].get_images():
                QTimer.singleShot(0, self.detect)
        except Exception as exc:
            error(self, exc)

    def add_thumbnail(self):
        if not self.doc or self.next_thumbnail >= len(self.doc):
            self.thumbnail_timer.stop()
            return
        from PySide6.QtGui import QIcon
        index = self.next_thumbnail
        page = self.doc[index]
        pix = page.get_pixmap(matrix=fitz.Matrix(72/page.rect.width, 72/page.rect.width), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        self.pages.item(index).setIcon(QIcon(QPixmap.fromImage(image)))
        self.next_thumbnail += 1

    def show_page(self, row, keep_zoom=False):
        if not self.doc or row < 0 or row >= len(self.doc):
            return
        if row != self.current_page:
            self.flush_fields()
        self.current_page = row
        self.scene.clear()
        self.entry_items, self.field_proxies = {}, {}
        page = self.doc[row]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        background = self.scene.addPixmap(QPixmap.fromImage(image))
        background.setScale(page.rect.width/pix.width)
        background.setZValue(-10)
        self.page_area = QRectF(0, 0, page.rect.width, page.rect.height)
        self.scene.setSceneRect(self.page_area)
        self.view.page_rect = QRectF(self.page_area)
        self.page_indicator.setText(f"{row+1} / {len(self.doc)}")
        if row not in self.fields_by_page:
            self.fields_by_page[row] = detect_fields(self.source, row, False)[0]
        self.field_list.clear()
        for field in self.fields_by_page[row]:
            item = QListWidgetItem(("Sign · " if field["kind"] == "signature" else "") + field["label"] + (f" · {field['max_length']} cells" if field["kind"] == "comb" else "") + (" *" if field["required"] else ""))
            item.setData(Qt.ItemDataRole.UserRole, field)
            self.field_list.addItem(item)
            if field["kind"] in ("text","comb","checkbox","radio","choice"):
                self.add_native_field(field)
            elif self.highlight_fields.isChecked():
                r = display_rect(field["box"], page)
                self.scene.addItem(FieldHint(field, QRectF(r.x0, r.y0, r.width, r.height), self.activate_field))
        for entry in self.annotations:
            if entry["page"] == row:
                self.add_entry_item(entry)
        if not keep_zoom:
            QTimer.singleShot(0, self.view.fit_page)
        count = len(self.fields_by_page[row])
        self.status.setText(f"Page {row+1} · {count} blanks. Click a blank and type; Tab moves to the next field.")

    def add_native_field(self, field):
        r = display_rect(field["box"], self.doc[self.current_page])
        original = fitz.Rect(field["rect"])
        value = self.values.get(field["id"], field["value"])
        if field["kind"] == "comb":
            widget = CombLineEdit(field)
            widget.setText(str(value or ""))
            widget.textEdited.connect(lambda text,f=field:self.set_field(f,text))
            widget.inputRejected.connect(lambda f=field:self.status.setText(f"{f['label']}: {f['max_length']} cells maximum" + (", digits only." if f.get('input_type')=='digits' else ".")))
        elif field["kind"] in ("checkbox", "radio"):
            widget = QRadioButton() if field["kind"] == "radio" else QCheckBox()
            widget.setChecked(bool(value) and value != "Off")
            widget.toggled.connect(lambda checked, f=field: self.set_field(f, checked))
        elif field["kind"] == "choice":
            widget = QComboBox()
            widget.addItems([str(choice) for choice in field["choices"]])
            widget.setCurrentText(str(value or ""))
            widget.currentTextChanged.connect(lambda text, f=field: self.set_field(f, text))
        else:
            if field.get("multiline"):
                widget = QTextEdit()
                widget.setPlainText(str(value or ""))
                widget.textChanged.connect(lambda f=field, w=widget: self.set_field(f, w.toPlainText()))
            else:
                widget = QLineEdit(str(value or ""))
                if field.get("max_length", 0):
                    widget.setMaxLength(field["max_length"])
                widget.editingFinished.connect(lambda f=field, w=widget: self.set_field(f, w.text()))
        widget.setMinimumSize(1, 1)
        widget.setToolTip(field["label"] + (" · Required" if field["required"] else ""))
        widget.setEnabled(not field["readonly"])
        size = max(7, min(12, original.height*.65))
        if not isinstance(widget,CombLineEdit):
            widget.setStyleSheet(f"QWidget {{font-family:Arial; font-size:{size}px; color:#111111; background:white; padding:0; margin:0; border:1px solid {'#999999' if self.highlight_fields.isChecked() else 'transparent'}; border-radius:0;}} QCheckBox::indicator {{width:{max(7, min(14, r.height-2))}px; height:{max(7, min(14, r.height-2))}px;}}")
        widget.setProperty("pdf_field_id",field["id"])
        widget.installEventFilter(self)
        proxy = self.scene.addWidget(widget)
        origin = original.top_left * self.doc[self.current_page].rotation_matrix
        proxy.setPos(origin.x, origin.y)
        proxy.setRotation(self.doc[self.current_page].rotation)
        proxy.resize(original.width, original.height)
        proxy.setZValue(10)
        self.field_proxies[field["id"]] = proxy

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.KeyPress and watched.property("pdf_field_id") and event.key() in (Qt.Key.Key_Tab,Qt.Key.Key_Backtab):
            direction=-1 if event.key()==Qt.Key.Key_Backtab or event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            self.focus_next_field(watched.property("pdf_field_id"),direction)
            return True
        return super().eventFilter(watched,event)

    def focus_next_field(self,key,direction):
        fields=[f for f in self.fields_by_page.get(self.current_page,[]) if f["id"] in self.field_proxies and not f["readonly"]]
        ids=[f["id"] for f in fields]
        if key not in ids:return
        index=ids.index(key)+direction
        if 0<=index<len(ids):
            widget=self.field_proxies[ids[index]].widget()
            widget.setFocus(Qt.FocusReason.TabFocusReason)
            if isinstance(widget,QLineEdit):widget.selectAll()
            self.view.ensureVisible(self.field_proxies[ids[index]],25,25)
        elif self.doc and 0<=self.current_page+direction<len(self.doc):
            self.pages.setCurrentRow(self.current_page+direction)
            QTimer.singleShot(0,lambda:self.focus_edge_field(direction))

    def focus_edge_field(self,direction):
        fields=[f for f in self.fields_by_page.get(self.current_page,[]) if f["id"] in self.field_proxies and not f["readonly"]]
        if fields:
            proxy=self.field_proxies[fields[0 if direction>0 else -1]["id"]]
            proxy.widget().setFocus(Qt.FocusReason.TabFocusReason)
            self.view.ensureVisible(proxy,25,25)

    def set_field(self, field, value):
        old = self.values.get(field["id"], field["value"])
        if field["kind"] in ("checkbox", "radio"):
            old = bool(old) and old != "Off"
        if old == value:
            return
        self.checkpoint()
        if field["kind"] == "radio" and value:
            # Track the other buttons so a radio group retains one selection.
            for page in self.doc:
                for other in native_fields(page):
                    if other["kind"] == "radio" and other["name"] == field["name"]:
                        self.values[other["id"]] = other["id"] == field["id"]
            for f in self.fields_by_page.get(self.current_page, []):
                if f["kind"] == "radio" and f["name"] == field["name"] and f["id"] in self.field_proxies:
                    widget = self.field_proxies[f["id"]].widget()
                    widget.blockSignals(True)
                    widget.setChecked(f["id"] == field["id"])
                    widget.blockSignals(False)
        self.values[field["id"]] = value

    def flush_fields(self):
        for field in self.fields_by_page.get(self.current_page, []):
            proxy = self.field_proxies.get(field["id"])
            if proxy and isinstance(proxy.widget(), QLineEdit) and not field["readonly"]:
                self.set_field(field, proxy.widget().text())

    def change_page(self, direction):
        if self.doc:
            self.pages.setCurrentRow(max(0, min(len(self.doc)-1, self.current_page+direction)))

    def snapshot(self):
        return deepcopy((self.annotations, self.values))

    def checkpoint(self):
        self.undo_states.append(self.snapshot())
        self.undo_states = self.undo_states[-100:]
        self.redo_states.clear()
        self.dirty = True
        self.update_history_buttons()

    def commit_drag(self, before):
        if before != self.snapshot():
            self.undo_states.append(before)
            self.redo_states.clear()
            self.dirty = True
            self.update_history_buttons()

    def undo(self):
        if self.undo_states:
            self.redo_states.append(self.snapshot())
            self.annotations, self.values = self.undo_states.pop()
            self.dirty = True
            self.show_page(self.current_page, keep_zoom=True)
            self.update_history_buttons()

    def redo(self):
        if self.redo_states:
            self.undo_states.append(self.snapshot())
            self.annotations, self.values = self.redo_states.pop()
            self.dirty = True
            self.show_page(self.current_page, keep_zoom=True)
            self.update_history_buttons()

    def update_history_buttons(self):
        self.undo_button.setEnabled(bool(self.undo_states))
        self.redo_button.setEnabled(bool(self.redo_states))

    def set_mode(self, mode):
        self.mode = mode
        self.view.mode = mode
        self.view.setDragMode(PageView.DragMode.NoDrag if mode=="fill" else PageView.DragMode.ScrollHandDrag)
        for name, widget in self.mode_buttons.items():
            widget.setChecked(name == mode)
        self.view.setCursor(Qt.CursorShape.ArrowCursor if mode in ("select","fill") else Qt.CursorShape.CrossCursor)
        self.status.setText("Click a detected blank and type. Tab moves to the next field." if mode=="fill" else "Drag an entry to move it. Select it to show resize handles." if mode == "select" else f"Click the page to place {'a signature' if mode == 'signature' else mode}.")

    def page_clicked(self, point):
        if not self.doc:
            return
        mode = self.mode
        if mode == "signature" and not self.signature_png:
            self.panel.setCurrentIndex(1)
            self.status.setText("Create a name signature or import a PNG, then click the page.")
            return
        if mode == "signature":
            for field in self.fields_by_page.get(self.current_page, []):
                if field["kind"] == "signature":
                    rect = display_rect(field["box"], self.doc[self.current_page])
                    if QRectF(rect.x0, rect.y0, rect.width, rect.height).contains(point):
                        self.activate_field(field)
                        return
        text = ""
        if mode == "text":
            text, ok = QInputDialog.getMultiLineText(self, "Add text", "Text to place on the form:")
            if not ok or not text.strip():
                return
        elif mode == "date":
            text = date.today().strftime("%d/%m/%Y")
        w, h = (160, 35) if mode == "signature" else (18, 18) if mode in ("check", "cross") else (180, max(26, (text.count("\n")+1)*(self.font_size.value()+3)))
        if mode == "signature":
            pix = QPixmap()
            pix.loadFromData(self.signature_png)
            h = w*pix.height()/max(1, pix.width())
        self.add_entry(mode, point, w, h, text=text)
        self.set_mode("select")

    def add_entry(self, kind, point, width, height, text="", box=None, field_id=None):
        if not self.doc:
            return None
        if box is None:
            width, height = min(width, self.page_area.width()), min(height, self.page_area.height())
            x = max(0, min(point.x(), self.page_area.width()-width))
            y = max(0, min(point.y(), self.page_area.height()-height))
            box = [x/self.page_area.width(), y/self.page_area.height(), width/self.page_area.width(), height/self.page_area.height()]
        self.checkpoint()
        entry = dict(id=uuid4().hex, kind=kind, page=self.current_page, box=list(box), text=text, font=self.font_size.value(), field_id=field_id)
        if kind == "signature":
            entry["png"] = self.signature_png
            # Keep aspect ratio inside a detected signature rectangle.
            pix = QPixmap()
            pix.loadFromData(self.signature_png)
            w, h = box[2]*self.page_area.width(), box[3]*self.page_area.height()
            ratio = pix.width()/max(1, pix.height())
            w = min(w, h*ratio)
            h = w/ratio
            entry["box"][2:4] = [w/self.page_area.width(), h/self.page_area.height()]
        self.annotations.append(entry)
        item = self.add_entry_item(entry)
        self.scene.clearSelection()
        item.setSelected(True)
        return item

    def add_entry_item(self, entry):
        item = EntryItem(entry, self.page_area, self.snapshot, self.commit_drag, self.edit_entry)
        self.scene.addItem(item)
        self.entry_items[entry["id"]] = item
        return item

    def edit_entry(self, item):
        if item.entry["kind"] not in ("text", "date"):
            return
        text, ok = QInputDialog.getMultiLineText(self, "Edit text", "Text:", item.entry.get("text", ""))
        if ok:
            self.checkpoint()
            item.entry["text"] = text
            item.update()

    def change_font(self, value):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, EntryItem) and item.entry["kind"] in ("text", "date")]
        if selected:
            self.checkpoint()
            for item in selected:
                item.entry["font"] = value
                item.update()

    def delete_selected(self):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, EntryItem)]
        if selected:
            self.checkpoint()
            ids = {item.entry["id"] for item in selected}
            self.annotations = [e for e in self.annotations if e["id"] not in ids]
            for item in selected:
                self.scene.removeItem(item)
                self.entry_items.pop(item.entry["id"], None)

    def duplicate_selected(self):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, EntryItem)]
        if not selected:
            return
        self.checkpoint()
        self.scene.clearSelection()
        for item in selected:
            entry = deepcopy(item.entry)
            entry["id"] = uuid4().hex
            entry["box"][0] = min(entry["box"][0]+.025, 1-entry["box"][2])
            entry["box"][1] = min(entry["box"][1]+.025, 1-entry["box"][3])
            entry["field_id"] = None
            self.annotations.append(entry)
            self.add_entry_item(entry).setSelected(True)

    def resize_signature(self, factor):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, EntryItem) and item.entry["kind"] == "signature"]
        if not selected:
            self.status.setText("Select a signature first, or drag its corner handles directly.")
            return
        before = self.snapshot()
        for item in selected:
            item.anchor = item.pos()
            item.resize_from_corner(item.pos()+QPointF(item.rect.width()*factor, item.rect.height()*factor))
            item.sync()
        self.commit_drag(before)

    def activate_field(self, field):
        r = display_rect(field["box"], self.doc[self.current_page])
        self.view.centerOn(r.x0+r.width/2, r.y0+r.height/2)
        if field.get("signed"):
            self.status.setText("This is an existing certificate signature. It is read-only here.")
            return
        if field["readonly"]:
            self.status.setText("This PDF field is read-only.")
            return
        if field["id"] in self.field_proxies:
            self.field_proxies[field["id"]].widget().setFocus()
            return
        existing = next((entry for entry in self.annotations if entry.get("field_id") == field["id"]), None)
        if existing:
            item = self.entry_items[existing["id"]]
            self.scene.clearSelection()
            item.setSelected(True)
            self.edit_entry(item)
            return
        kind = field["kind"]
        if kind == "signature":
            if not self.signature_png:
                self.panel.setCurrentIndex(1)
                self.status.setText("Signature area found. Create or import a signature, then click the box again.")
                return
            self.add_entry("signature", QPointF(), r.width, r.height, box=field["box"], field_id=field["id"])
        elif kind == "checkbox":
            self.add_entry("check", QPointF(), r.width, r.height, box=field["box"], field_id=field["id"])
        else:
            text, ok = QInputDialog.getMultiLineText(self, "Fill field", field["label"])
            if ok and text.strip():
                self.add_entry("text", QPointF(), r.width, r.height, text=text, box=field["box"], field_id=field["id"])
        self.set_mode("select")

    def set_signature(self, pix):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pix.save(buffer, "PNG")
        self.signature_png = bytes(buffer.data())
        preview = pix.scaled(200, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.signature_preview.setPixmap(preview)
        self.set_mode("signature")

    def create_signature(self):
        name = self.name.text().strip()
        if not name or len(name) > 100:
            error(self, "Enter a name of 1 to 100 characters.")
            return
        font = QFont(self.font_choice.currentText(), 64)
        metrics = QFontMetrics(font)
        pix = QPixmap(metrics.horizontalAdvance(name)+50, metrics.height()+30)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(font)
        painter.setPen(QColor("#111111"))
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, name)
        painter.end()
        self.set_signature(pix)

    def import_signature(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import signature", "", "PNG (*.png)")
        if path:
            pix = QPixmap(path)
            if pix.isNull():
                error(self, "This signature PNG could not be opened.")
            else:
                self.set_signature(pix)

    def detect(self):
        if not self.doc or (self.detection_worker and self.detection_worker.isRunning()):
            return
        page_index = self.current_page
        source = self.source
        use_ocr = self.ocr.isChecked()
        self.detect_button.setEnabled(False)
        self.detection_progress.show()
        self.status.setText("Inspecting this page locally…")
        self.detection_worker = Worker(lambda progress, message: detect_fields(source, page_index, use_ocr), self)
        def finished(result):
            fields, message = result
            focused=next(((key,proxy.widget().cursorPosition()) for key,proxy in self.field_proxies.items() if isinstance(proxy.widget(),QLineEdit) and proxy.widget().hasFocus()),None)
            self.flush_fields()
            self.fields_by_page[page_index] = fields
            if self.current_page == page_index:
                self.show_page(page_index, keep_zoom=True)
                if focused and focused[0] in self.field_proxies:
                    widget=self.field_proxies[focused[0]].widget()
                    widget.setFocus()
                    widget.setCursorPosition(focused[1])
            self.status.setText(message)
        self.detection_worker.result.connect(finished)
        self.detection_worker.failed.connect(lambda message: self.status.setText(f"Detection could not finish: {message}. You can still fill the page manually."))
        self.detection_worker.finished.connect(lambda: self.detect_button.setEnabled(True))
        self.detection_worker.finished.connect(self.detection_progress.hide)
        self.detection_worker.start()

    def save(self):
        if not self.doc:
            return
        self.flush_fields()
        # Commit a native text field that still owns keyboard focus.
        focused = self.focusWidget()
        if focused:
            focused.clearFocus()
        for item in self.entry_items.values():
            item.sync()
        default = Path(self.parent().output_root) / f"{Path(self.source).stem}_filled.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save a new PDF", str(default), "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        if Path(path).exists():
            error(self, "Choose a new filename. The original and existing outputs are preserved.")
            return
        values, annotations = deepcopy(self.values), deepcopy(self.annotations)
        flatten = self.flatten.isChecked()
        def saved(result):
            self.dirty = False
            self.status.setText(f"Saved: {result}")
        detected=deepcopy([f for fields in self.fields_by_page.values() for f in fields])
        run_job(self, "Save filled PDF", lambda progress, message: save_filled_pdf(self.source, path, values, annotations, flatten,detected), saved)

    def done(self, result):
        if self.detection_worker and self.detection_worker.isRunning():
            self.status.setText("Wait for field detection to finish before closing.")
            return
        if not self.confirm_discard():
            return
        if hasattr(self, "thumbnail_timer"):
            self.thumbnail_timer.stop()
        if self.doc:
            self.doc.close()
            self.doc = None
        super().done(result)

    def closeEvent(self, event):
        if (self.detection_worker and self.detection_worker.isRunning()) or not self.confirm_discard():
            event.ignore()
        else:
            self.dirty = False
            self.done(QDialog.DialogCode.Rejected)
            event.accept()
