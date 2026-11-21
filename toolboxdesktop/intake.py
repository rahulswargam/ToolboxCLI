"""Classify local selections and suggest tools compatible with the selection."""
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
IMAGE_COMPRESS_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PDF_IMAGE_TYPES = {".jpg", ".jpeg", ".png"}
PDF_TOOLS = {"fill_pdf", "pdf_to_jpg", "pdf_to_word", "unlock_pdf", "lock_pdf", "resize_pdf", "merge_pdf", "sign_pdf", "rotate_pdf", "organize_pdf", "remove_pages"}


def selection_kind(paths):
    if not paths:
        return "none"
    if len(paths) == 1 and Path(paths[0]).is_dir():
        return "folder"
    if all(Path(p).is_file() and Path(p).suffix.lower() == ".pdf" for p in paths):
        return "pdf"
    if all(Path(p).is_file() and Path(p).suffix.lower() in IMAGE_TYPES for p in paths):
        return "images"
    return "unsupported"


def recommended_keys(paths):
    kind = selection_kind(paths)
    if kind == "pdf":
        return {"merge_pdf"} if len(paths) > 1 else PDF_TOOLS
    if kind == "images":
        keys = set()
        if all(Path(p).suffix.lower() in IMAGE_COMPRESS_TYPES for p in paths):
            keys.add("compress_images")
        if all(Path(p).suffix.lower() in PDF_IMAGE_TYPES for p in paths):
            keys.add("images_to_pdf")
        return keys
    if kind == "folder":
        return {"remove_duplicates", "find_duplicates", "rename_by_date"}
    return set()


class DropZone(QFrame):
    filesDropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self.setProperty("dragging", False)

    def set_dragging(self, active):
        self.setProperty("dragging", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if urls and all(url.isLocalFile() for url in urls):
            event.acceptProposedAction()
            self.set_dragging(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.set_dragging(False)
        event.accept()

    def dropEvent(self, event):
        self.set_dragging(False)
        urls = event.mimeData().urls()
        if urls and all(url.isLocalFile() for url in urls):
            self.filesDropped.emit([url.toLocalFile() for url in urls])
            event.acceptProposedAction()
        else:
            event.ignore()
