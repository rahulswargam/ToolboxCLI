from __future__ import annotations

from pathlib import Path
import fitz
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QImage, QIcon, QPainter, QFont, QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QAbstractItemView, QFileDialog, QComboBox, QLineEdit, QSpinBox,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem, QFormLayout,
    QWidget, QMessageBox)
from .common import label, button, run_job, reveal, error, configure_dialog, ElidedLabel
from .operations import open_pdf, edit_pdf, merge_pdf, sign_pdf


def pixmap(page, width):
    data = page.get_pixmap(matrix=fitz.Matrix(width / page.rect.width, width / page.rect.width), alpha=False)
    return QPixmap.fromImage(QImage(data.samples, data.width, data.height, data.stride,
                                   QImage.Format.Format_RGB888).copy())


class PageList(QListWidget):
    """Reorder the model explicitly, so saved page order matches the preview."""
    def dropEvent(self, event):
        if self.viewMode() != QListWidget.ViewMode.IconMode:
            return super().dropEvent(event)
        source = self.currentRow()
        target = self.indexAt(event.position().toPoint()).row()
        if source >= 0 and target >= 0 and source != target:
            item = self.takeItem(source)
            self.insertItem(target, item)
            self.setCurrentItem(item)
        event.acceptProposedAction()


class PdfEditor(QDialog):
    def __init__(self, parent, tool, files=None):
        super().__init__(parent)
        self.tool = tool
        self.source = None
        self.doc = None
        self.setWindowTitle(tool.label)
        configure_dialog(self, 1080, 720, (700, 400))
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 24, 24, 24)
        self.layout.setSpacing(14)
        self.layout.addWidget(label(tool.label, "title"))
        self.layout.addWidget(label(tool.description, "subtitle", True))
        toolbar = QHBoxLayout()
        toolbar.addWidget(button("Add PDFs…" if tool.key == "merge_pdf" else "Open PDF…", self.open))
        self.filename = ElidedLabel("Choose a document to get started")
        self.filename.setObjectName("muted")
        toolbar.addWidget(self.filename, 1)
        self.layout.addLayout(toolbar)
        self.pages = PageList()
        self.pages.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.pages.setIconSize(QSize(110, 150))
        self.pages.setSpacing(8)
        if tool.key == "merge_pdf":
            self.pages.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            self.layout.addWidget(label("Drag documents to change their order. Select a document and click Remove to exclude it.", "muted", True))
            self.layout.addWidget(self.pages, 1)
            self.layout.addWidget(button("Remove selected documents", self.remove_items))
        elif tool.key == "sign_pdf":
            self.setup_sign()
        else:
            self.pages.setViewMode(QListWidget.ViewMode.IconMode)
            self.pages.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.pages.setGridSize(QSize(155, 200))
            if tool.key == "organize_pdf":
                self.pages.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
                self.pages.setMovement(QListWidget.Movement.Snap)
                self.pages.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
                self.layout.addWidget(label("Drag thumbnails to reorder pages. Every page is preserved in the displayed order.", "muted", True))
            else:
                self.layout.addWidget(label("Click pages to select them. Hold Ctrl to select multiple pages.", "muted"))
            self.layout.addWidget(self.pages, 1)
        actions = QHBoxLayout()
        if tool.key == "rotate_pdf":
            self.angle = QComboBox()
            self.angle.addItems(["90° clockwise", "180°", "270° clockwise"])
            actions.addWidget(self.angle)
            actions.addWidget(button("Select all", self.pages.selectAll))
        actions.addStretch()
        self.save_button = button("Save new PDF…", self.save, True)
        self.save_button.setEnabled(False)
        actions.addWidget(self.save_button)
        self.layout.addLayout(actions)
        if files:
            self.load_files(files)

    def setup_sign(self):
        split = QSplitter()
        self.pages.setMaximumWidth(165)
        self.pages.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pages.currentRowChanged.connect(self.show_page)
        split.addWidget(self.pages)
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setBackgroundBrush(self.palette().color(QPalette.ColorRole.Mid))
        split.addWidget(self.view)
        panel = QWidget()
        controls = QVBoxLayout(panel)
        panel.setMaximumWidth(250)
        controls.addWidget(label("YOUR SIGNATURE", "eyebrow"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Type your full name")
        controls.addWidget(self.name)
        self.font_choice = QComboBox()
        available = QFontDatabase.families()
        fonts = [f for f in ("Segoe Script", "Lucida Handwriting", "Brush Script MT", "Gabriola") if f in available]
        self.font_choice.addItems(fonts or ["Segoe UI"])
        controls.addWidget(self.font_choice)
        controls.addWidget(button("Create from name", self.create_signature))
        controls.addWidget(label("or", "muted"))
        controls.addWidget(button("Import signature PNG…", self.import_signature))
        controls.addWidget(label("Width (% of page)", "muted"))
        self.signature_width = QSpinBox()
        self.signature_width.setRange(5, 70)
        self.signature_width.setValue(30)
        self.signature_width.valueChanged.connect(self.scale_signature)
        controls.addWidget(self.signature_width)
        controls.addWidget(label("Drag the signature onto the page. Choose a page from the left to place it there.", "muted", True))
        controls.addStretch()
        controls.addWidget(label("Visual signature only. This does not create a certificate-based digital signature.", "muted", True))
        split.addWidget(panel)
        split.setStretchFactor(1, 1)
        self.layout.addWidget(split, 1)
        self.signature = None
        self.signature_pixmap = None

    def open(self):
        if self.tool.key == "merge_pdf":
            files, _ = QFileDialog.getOpenFileNames(self, "Add PDFs", "", "PDF (*.pdf)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF (*.pdf)")
            files = [path] if path else []
        if files:
            self.load_files(files)

    def load_files(self, files):
        if self.tool.key == "merge_pdf":
            for path in files:
                try:
                    with open_pdf(path) as doc:
                        item = QListWidgetItem(f"{Path(path).name}   ·   {len(doc)} pages")
                        item.setToolTip(path)
                        item.setData(Qt.ItemDataRole.UserRole, path)
                        self.pages.addItem(item)
                except Exception as exc:
                    error(self, exc)
            self.save_button.setEnabled(self.pages.count() >= 2)
            self.filename.setText(f"{self.pages.count()} documents")
            return
        path = files[0] if files else None
        if not path:
            return
        try:
            doc = open_pdf(path)
            if self.doc:
                self.doc.close()
            self.doc = doc
            self.source = path
            self.pages.clear()
            self.filename.setText(f"{Path(path).name}  ·  {len(doc)} pages")
            # Thumbnail rendering is incremental so opening large documents stays responsive.
            self.next_thumbnail = 0
            self.save_button.setEnabled(False)
            from PySide6.QtCore import QTimer
            if hasattr(self, "thumbnail_timer"):
                self.thumbnail_timer.stop()
            self.thumbnail_timer = QTimer(self)
            self.thumbnail_timer.timeout.connect(self.add_thumbnail)
            self.thumbnail_timer.start(1)
        except Exception as exc:
            error(self, exc)

    def add_thumbnail(self):
        try:
            i = self.next_thumbnail
            item = QListWidgetItem(QIcon(pixmap(self.doc[i], 110)), f"Page {i+1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.pages.addItem(item)
            self.next_thumbnail += 1
            if self.next_thumbnail == len(self.doc):
                self.thumbnail_timer.stop()
                self.save_button.setEnabled(True)
                self.pages.setCurrentRow(0)
        except Exception as exc:
            self.thumbnail_timer.stop()
            error(self, exc)

    def remove_items(self):
        for item in self.pages.selectedItems():
            self.pages.takeItem(self.pages.row(item))
        self.save_button.setEnabled(self.pages.count() >= 2)

    def show_page(self, row):
        if row < 0 or not self.doc:
            return
        self.scene.clear()
        self.signature = None
        self.page_pixmap = pixmap(self.doc[row], 850)
        self.scene.addPixmap(self.page_pixmap)
        self.scene.setSceneRect(0, 0, self.page_pixmap.width(), self.page_pixmap.height())
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.place_signature()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "scene"):
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def create_signature(self):
        name = self.name.text().strip()
        if not name:
            error(self, "Enter your name first.")
            return
        if len(name) > 100:
            error(self, "Use a name of 100 characters or fewer.")
            return
        font = QFont(self.font_choice.currentText(), 64)
        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(font)
        pix = QPixmap(metrics.horizontalAdvance(name) + 50, metrics.height() + 30)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(font)
        painter.setPen(QColor("#171717"))
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, name)
        painter.end()
        self.signature_pixmap = pix
        self.place_signature()

    def import_signature(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose signature", "", "PNG (*.png)")
        if path:
            pix = QPixmap(path)
            if pix.isNull():
                error(self, "This PNG could not be opened.")
                return
            self.signature_pixmap = pix
            self.place_signature()

    def place_signature(self):
        if self.signature_pixmap is None or not hasattr(self, "page_pixmap"):
            return
        if self.signature:
            self.scene.removeItem(self.signature)
        self.signature = QGraphicsPixmapItem(self.signature_pixmap)
        self.signature.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.signature.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.scene.addItem(self.signature)
        self.scale_signature()
        self.signature.setPos(self.page_pixmap.width() * .12, self.page_pixmap.height() * .7)

    def scale_signature(self):
        if self.signature:
            width = self.page_pixmap.width() * self.signature_width.value() / 100
            self.signature.setScale(width / self.signature_pixmap.width())

    def save(self):
        try:
            key = self.tool.key
            if key == "merge_pdf":
                files = [self.pages.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.pages.count())]
                if len(files) < 2:
                    raise ValueError("Add at least two PDFs.")
            elif not self.source:
                raise ValueError("Open a PDF first.")
            if key == "sign_pdf":
                if not self.signature:
                    raise ValueError("Create or import a signature first.")
                bounds = self.signature.sceneBoundingRect()
                area = self.scene.sceneRect()
                if not area.contains(bounds):
                    raise ValueError("Drag the entire signature inside the page.")
                box = (bounds.x()/area.width(), bounds.y()/area.height(), bounds.width()/area.width(), bounds.height()/area.height())
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                self.signature_pixmap.save(buffer, "PNG")
                png = bytes(buffer.data())
                page_index = self.pages.currentRow()
            elif key != "merge_pdf":
                selected = self.pages.selectedItems()
                pages = [self.pages.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.pages.count())] if key == "organize_pdf" else [i.data(Qt.ItemDataRole.UserRole) for i in selected]
                if not pages:
                    raise ValueError("Select at least one page.")
                if key == "remove_pages" and len(pages) == len(self.doc):
                    raise ValueError("Keep at least one page.")
            default = Path(self.parent().output_root) / f"{Path(self.source).stem if self.source else 'Merged'}_{key}.pdf"
            path, _ = QFileDialog.getSaveFileName(self, "Save new PDF", str(default), "PDF (*.pdf)")
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            if Path(path).exists():
                raise ValueError("Choose a new filename. Existing files are preserved.")
            if key == "merge_pdf":
                function = lambda progress, message: merge_pdf(files, path, progress)
            elif key == "sign_pdf":
                function = lambda progress, message: sign_pdf(self.source, path, page_index, png, box)
            else:
                action = {"rotate_pdf": "rotate", "organize_pdf": "organize", "remove_pages": "remove"}[key]
                angle = (90, 180, 270)[self.angle.currentIndex()] if key == "rotate_pdf" else 90
                function = lambda progress, message: edit_pdf(self.source, path, action, pages, angle)
            run_job(self, self.tool.label, function, lambda result: reveal(result.parent))
        except Exception as exc:
            error(self, exc)

    def done(self, result):
        if hasattr(self, "thumbnail_timer"):
            self.thumbnail_timer.stop()
        if self.doc:
            self.doc.close()
            self.doc = None
        super().done(result)
