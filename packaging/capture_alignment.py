"""Visual QA of both themes, last-row clipping, compact layout, and DPI."""
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from toolboxdesktop.app import MainWindow

app = QApplication([])
app.setStyle("Fusion")
scale = f"{round(app.primaryScreen().devicePixelRatio() * 100)}percent"
root = Path(__file__).resolve().parent.parent / "artifacts" / "alignment" / scale
root.mkdir(parents=True, exist_ok=True)
window = MainWindow(settings_dir=root / "settings")
window.resize(1280, 680)
window.show()

def settle():
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

for mode in ("dark", "light"):
    window.theme_choice.setCurrentIndex(window.theme_choice.findData(mode))
    window.tools_scroll.verticalScrollBar().setValue(0)
    settle()
    window.grab().save(str(root / f"dashboard-{mode}.png"))
    window.tools_scroll.verticalScrollBar().setValue(window.tools_scroll.verticalScrollBar().maximum())
    settle()
    window.grab().save(str(root / f"last-row-{mode}.png"))
window.resize(960, 640)
window.tools_scroll.verticalScrollBar().setValue(0)
settle()
assert window.card_columns == 2
window.grab().save(str(root / "compact-light.png"))
window.close()
print(f"Verified screenshots: {root}")
