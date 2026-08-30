"""Cross-platform helpers: native pickers, Desktop detection, dependency checks.

Everything here works identically on Windows and macOS. The tkinter dialogs
are launched with the Textual app suspended (see screens/task.py) so the
native window takes focus properly instead of appearing behind the terminal.
"""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
from pathlib import Path


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_mac() -> bool:
    return platform.system() == "Darwin"


def get_desktop_path() -> Path:
    """The user's real Desktop, handling OneDrive redirection on Windows."""
    if is_windows():
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            raw = winreg.QueryValueEx(key, "Desktop")[0]
            winreg.CloseKey(key)
            desktop = Path(os.path.expandvars(raw))
            if desktop.exists():
                return desktop
        except Exception:
            pass
        for candidate in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop"):
            if candidate.exists():
                return candidate
    return Path.home() / "Desktop"


def output_folder(name: str) -> Path:
    folder = get_desktop_path() / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def open_in_file_manager(path: Path) -> None:
    try:
        if is_windows():
            os.startfile(str(path))  # noqa: Windows-only
        elif is_mac():
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass


def has_module(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def require_module(module_name: str, pip_name: str | None = None):
    pip_name = pip_name or module_name
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"This tool needs the '{pip_name}' package.\n"
            f"Install it with:  pip install {pip_name}"
        ) from exc


def require_binary(binary: str) -> None:
    if shutil.which(binary):
        return
    hint = ("winget install Gyan.FFmpeg" if is_windows() else "brew install ffmpeg")
    raise RuntimeError(
        f"This tool needs the '{binary}' command on your PATH.\nInstall it with:  {hint}"
    )


# ── Native pickers ────────────────────────────────────────────────────────

def _tk_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def pick_files(title: str, filetypes=(), multiple: bool = True) -> list[Path]:
    try:
        from tkinter import filedialog
    except ImportError:
        raise RuntimeError(
            "tkinter is not available.\n"
            "On macOS with Homebrew Python, run:  brew install python-tk"
        )
    root = _tk_root()
    kwargs = {"title": title}
    if filetypes:
        kwargs["filetypes"] = list(filetypes) + [("All files", "*.*")]
    try:
        if multiple:
            paths = filedialog.askopenfilenames(**kwargs)
        else:
            single = filedialog.askopenfilename(**kwargs)
            paths = [single] if single else []
    finally:
        root.destroy()
    return [Path(p) for p in paths if p]


def pick_folder(title: str) -> Path | None:
    try:
        from tkinter import filedialog
    except ImportError:
        raise RuntimeError(
            "tkinter is not available.\n"
            "On macOS with Homebrew Python, run:  brew install python-tk"
        )
    root = _tk_root()
    try:
        folder = filedialog.askdirectory(title=title)
    finally:
        root.destroy()
    return Path(folder) if folder else None
