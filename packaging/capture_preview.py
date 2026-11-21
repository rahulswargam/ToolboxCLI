"""Capture both themes and file-aware recommendations from the actual Qt UI."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from toolboxdesktop.app import MainWindow
import fitz

app = QApplication([])
app.setStyle("Fusion")
root = Path(__file__).resolve().parent.parent / "artifacts" / "redesign"
root.mkdir(parents=True, exist_ok=True)
window = MainWindow(settings_dir=root / "settings")
window.resize(1280, 850)
window.show()
def settle():
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    app.processEvents()

for mode in ("dark", "light"):
    window.theme_choice.setCurrentIndex(window.theme_choice.findData(mode))
    settle()
    window.grab().save(str(root / f"dashboard-{mode}.png"))
source = root / "Brand guidelines.pdf"
with fitz.open() as doc:
    doc.new_page()
    doc.save(source)
window.ingest_paths([source])
settle()
window.grab().save(str(root / "file-recommendations.png"))
window.navigate("Settings")
settle()
window.grab().save(str(root / "settings-light.png"))
window.close()
