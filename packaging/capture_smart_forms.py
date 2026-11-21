"""Capture direct typing against the public regression form (not redistributed)."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from toolboxdesktop.app import MainWindow
from toolboxdesktop.catalog import TOOLS
from toolboxdesktop.pdf_workspace import PdfWorkspace
from toolboxdesktop.pdf_forms import save_filled_pdf
from toolboxcli.core.platform import unique_path

root=Path(__file__).resolve().parent.parent/'artifacts/smart-forms'
root.mkdir(parents=True,exist_ok=True)
source=root.parent/'form-research/hdfc-minor-to-major.pdf'
app=QApplication([]);app.setStyle('Fusion')
window=MainWindow(settings_dir=root/'settings');window.show()
editor=PdfWorkspace(window,next(t for t in TOOLS if t.key=='fill_pdf'),files=[str(source)])
editor.showMaximized()
def settle():
    for _ in range(6):app.processEvents()
settle()
fields=editor.fields_by_page[0]
for label,value in [('Customer ID','123456789'),('Bank A/c','00123456789012'),('Date:*','21112026'),('PAN Number','ABCDE1234F'),('Mobile','9000000000')]:
    field=next(f for f in fields if f['kind']=='comb' and label in f['label'])
    editor.activate_field(field)
    QTest.keyClicks(editor.field_proxies[field['id']].widget(),value)
    settle()
assert not editor.annotations
editor.flush_fields()
save_filled_pdf(source,unique_path(root/'Filled demonstration.pdf'),editor.values,[],detected_fields=fields)
for mode in ('light','dark'):
    window.theme_choice.setCurrentIndex(window.theme_choice.findData(mode))
    editor.view.fit_width();settle()
    editor.view.verticalScrollBar().setValue(0);settle()
    editor.grab().save(str(root/f'direct-fill-{mode}.png'))
editor.dirty=False;editor.reject();window.close()
print(root)
