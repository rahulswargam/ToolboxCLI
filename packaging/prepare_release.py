from pathlib import Path
import zipfile
import shutil
import importlib.util

root = Path(__file__).resolve().parent.parent
release = root / "release"
release.mkdir(exist_ok=True)
bundle = (root / "dist" / "RahulsToolbox").resolve()
assert bundle.is_relative_to(root.resolve())
# Qt uses Windows' unsuffixed ICU API. A third-party ICU DLL found on PATH
# can export only version-suffixed symbols and prevent QtCore from loading.
# Windows 10 1809+ supplies the required ICU API itself.
for name in ("icuuc.dll", "icudt78.dll", "icuuc.dll.disabled"):
    (bundle / "_internal" / name).unlink(missing_ok=True)
(bundle / "Diagnostic.exe").unlink(missing_ok=True)
# Keep the C++ runtime consistent with Qt's newer, backward-compatible copy.
qt_dir = Path(importlib.util.find_spec("PySide6").origin).parent
for name in ("vcruntime140.dll", "vcruntime140_1.dll"):
    shutil.copy2(qt_dir / name, bundle / "_internal" / name)
shutil.copytree(root / "assets" / "licenses", bundle / "_internal" / "assets" / "licenses", dirs_exist_ok=True)
with zipfile.ZipFile(release / "RahulsToolbox-3.3.0-Source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for name in ("toolboxdesktop", "toolboxcli", "packaging", "tests", "assets", "docs"):
        for path in (root / name).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(root))
    for name in (".gitignore", ".gitattributes", "desktop.pyw", "toolbox.py", "requirements.txt", "requirements-desktop.txt", "requirements-desktop.lock.txt", "README.md", "THIRD_PARTY_NOTICES.md", "LICENSE"):
        archive.write(root / name, name)
shutil.copy2(release / "RahulsToolbox-3.3.0-Source.zip", root / "dist" / "RahulsToolbox")
