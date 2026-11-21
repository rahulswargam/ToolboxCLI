"""Render the application mark and package dependency license texts."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import importlib.metadata as metadata
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from PySide6.QtWidgets import QApplication
from toolboxdesktop.icons import brand_icon
app = QApplication.instance() or QApplication([])
brand_icon(1024).pixmap(1024, 1024).save(str(root / "assets" / "toolbox.png"))
image = Image.open(root / "assets" / "toolbox.png")
image.save(root / "assets" / "toolbox.ico", sizes=[(16,16),(32,32),(48,48),(128,128),(256,256)])
wizard = Image.new("RGB", (328, 628), "#111111")
mark = image.resize((140, 140))
wizard.paste(mark, (32, 68), mark)
art = ImageDraw.Draw(wizard)
font_root = Path("C:/Windows/Fonts")
heading = ImageFont.truetype(str(font_root / "segoeuib.ttf"), 31)
body = ImageFont.truetype(str(font_root / "segoeui.ttf"), 21)
art.text((32, 240), "RAHUL'S\nTOOLBOX", font=heading, fill="#ffffff", spacing=6)
art.text((32, 365), "Your files.\nYour next move.", font=body, fill="#aaaaaa", spacing=9)
art.line((32, 500, 275, 500), fill="#444444", width=2)
art.text((32, 525), "DESKTOP EDITION\nv3.3.0", font=body, fill="#ffffff", spacing=8)
wizard.save(root / "assets" / "wizard.bmp")
# BMP cannot retain the rounded mark's alpha channel. Composite onto the
# installer's white header and leave an inset so the logo never touches it.
header = Image.new("RGB", (110, 110), "white")
header_mark = image.convert("RGBA").resize((76, 76), Image.Resampling.LANCZOS)
header.paste(header_mark, (17, 17), header_mark)
header.save(root / "assets" / "wizard-small.bmp")
license_dir = root / "assets" / "licenses"
license_dir.mkdir(exist_ok=True)
for distribution in metadata.distributions():
    name = distribution.metadata["Name"]
    for file in distribution.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "notice")):
            source = Path(distribution.locate_file(file))
            if source.is_file() and source.suffix.lower() not in (".py", ".pyc", ".pyd"):
                try:
                    (license_dir / f"{name}-{file.name}").write_bytes(source.read_bytes())
                except OSError:
                    pass
