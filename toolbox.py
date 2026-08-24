#!/usr/bin/env python3
"""
Rahul's Toolbox
===============
A single-file, cross-platform (Windows + macOS) CLI that bundles every
personal utility script into one menu-driven tool. Every tool that needs
an input/output location pops up a native file or folder picker instead
of relying on hardcoded paths.

Run it with:
    python toolbox.py

First-time setup:
    pip install -r requirements.txt

Some tools also need the `ffmpeg` command-line binary on your PATH
(Video Trimmer, YouTube-to-MP3). Install it with:
    Windows : winget install Gyan.FFmpeg   (or choco install ffmpeg)
    macOS   : brew install ffmpeg
"""

from __future__ import annotations

import hashlib
import importlib
import io
import os
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────
# Core UI dependencies (hard requirements — the app can't run without these)
# ──────────────────────────────────────────────────────────────────────────
try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    from rich import box
except ImportError:
    print("Missing dependency: rich\nInstall with: pip install -r requirements.txt")
    sys.exit(1)

try:
    import questionary
    from questionary import Style as QStyle
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, ScrollOffsets
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style as PTStyle
    from prompt_toolkit.data_structures import Point
except ImportError:
    print("Missing dependency: questionary\nInstall with: pip install -r requirements.txt")
    sys.exit(1)

# Force UTF-8 output so box-drawing characters and dashes render correctly
# on legacy Windows console codepages instead of turning into "?" / mojibake.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console()

THEME = QStyle([
    ("qmark", "fg:#00d7ff bold"),
    ("question", "bold"),
    ("answer", "fg:#00d787 bold"),
    ("pointer", "fg:#00d7ff bold"),
    ("highlighted", "fg:#00d7ff bold"),
    ("selected", "fg:#00d787 bold"),
    ("separator", "fg:#ffaf5f bold"),
    ("instruction", "fg:#6c6c6c italic"),
])


# ══════════════════════════════════════════════════════════════════════════
#  PLATFORM HELPERS  (shared by every tool below)
# ══════════════════════════════════════════════════════════════════════════

def is_windows() -> bool:
    return platform.system() == "Windows"


def is_mac() -> bool:
    return platform.system() == "Darwin"


def get_desktop_path() -> Path:
    """Return the user's real Desktop folder on Windows or macOS."""
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
    # macOS (and generic *nix fallback)
    return Path.home() / "Desktop"


def open_in_file_manager(path: Path) -> None:
    """Reveal a folder in Explorer (Windows) or Finder (macOS)."""
    try:
        if is_windows():
            os.startfile(str(path))  # noqa: only reached on Windows
        elif is_mac():
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass


def ensure_import(module_name: str, pip_name: str | None = None):
    """Import a soft/optional dependency, or explain how to install it."""
    pip_name = pip_name or module_name
    try:
        return importlib.import_module(module_name)
    except ImportError:
        console.print(f"[red]Missing dependency:[/red] this tool needs [bold]{pip_name}[/bold]")
        console.print(f"Install it with:  [bold cyan]pip install {pip_name}[/bold cyan]")
        return None


def ensure_binary(binary_name: str, install_hint: str) -> bool:
    """Check an external command-line tool (e.g. ffmpeg) is on PATH."""
    if shutil.which(binary_name):
        return True
    console.print(f"[red]Missing dependency:[/red] the [bold]{binary_name}[/bold] command was not found on your PATH.")
    console.print(f"Install it with:  [bold cyan]{install_hint}[/bold cyan]")
    return False


# ── Native file / folder pickers (tkinter ships with Python on both OSes) ──

def _tk_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def pick_files(title: str, filetypes=None, multiple: bool = True):
    """Popup a native 'open file' dialog. Returns a list[Path] (possibly empty)."""
    try:
        from tkinter import filedialog
    except ImportError:
        console.print("[red]tkinter is not installed.[/red] "
                       "On macOS via Homebrew, run: [bold cyan]brew install python-tk[/bold cyan]")
        return []

    root = _tk_root()
    kwargs = {"title": title}
    if filetypes:
        kwargs["filetypes"] = filetypes + [("All files", "*.*")]
    try:
        if multiple:
            paths = filedialog.askopenfilenames(**kwargs)
        else:
            single = filedialog.askopenfilename(**kwargs)
            paths = [single] if single else []
    finally:
        root.destroy()
    return [Path(p) for p in paths if p]


def pick_folder(title: str):
    """Popup a native 'select folder' dialog. Returns a Path or None."""
    try:
        from tkinter import filedialog
    except ImportError:
        console.print("[red]tkinter is not installed.[/red] "
                       "On macOS via Homebrew, run: [bold cyan]brew install python-tk[/bold cyan]")
        return None

    root = _tk_root()
    try:
        folder = filedialog.askdirectory(title=title)
    finally:
        root.destroy()
    return Path(folder) if folder else None


def ask_password(title: str, prompt: str):
    try:
        from tkinter import simpledialog
    except ImportError:
        return None
    root = _tk_root()
    try:
        return simpledialog.askstring(title, prompt, show="*")
    finally:
        root.destroy()


def confirm_popup(title: str, message: str) -> bool:
    try:
        from tkinter import messagebox
    except ImportError:
        return questionary.confirm(message, style=THEME).ask()
    root = _tk_root()
    try:
        return messagebox.askyesno(title, message)
    finally:
        root.destroy()


def info_popup(title: str, message: str) -> None:
    try:
        from tkinter import messagebox
    except ImportError:
        return
    root = _tk_root()
    try:
        messagebox.showinfo(title, message)
    finally:
        root.destroy()


def unique_path(path: Path) -> Path:
    """Avoid overwriting an existing file by adding ' (1)', ' (2)', ..."""
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def section(title: str) -> None:
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]", style="cyan")


def press_enter_to_continue() -> None:
    console.print()
    questionary.press_any_key_to_continue("Press any key to return to the menu...", style=THEME).ask()


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 1 — COMPRESS IMAGES  (merges compress_images.py / compressimages.py
#            / compressimagesjpg.py into one flow)
# ══════════════════════════════════════════════════════════════════════════

def _compress_one(img, target_kb: int):
    """Shrink a Pillow image under target_kb. Returns (jpeg_bytes, final_kb)."""
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = __import__("PIL.Image", fromlist=["Image"]).new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background.convert("RGB")
    else:
        img = img.convert("RGB")

    quality = 95
    while quality >= 20:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size_kb = buf.tell() / 1024
        if size_kb <= target_kb:
            return buf.getvalue(), size_kb
        quality -= 5

    width, height = img.size
    from PIL import Image as PILImage
    while True:
        width, height = int(width * 0.9), int(height * 0.9)
        img = img.resize((width, height), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        size_kb = buf.tell() / 1024
        if size_kb <= target_kb or width < 100 or height < 100:
            return buf.getvalue(), size_kb


def tool_compress_images() -> None:
    section("Compress Images")
    PIL = ensure_import("PIL", "pillow")
    if not PIL:
        return
    from PIL import Image

    files = pick_files(
        "Select images to compress (JPG / PNG)",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")],
    )
    if not files:
        console.print("[yellow]No files selected.[/yellow]")
        return

    target_kb = questionary.text(
        "Target size in KB per image?", default="100", style=THEME
    ).ask()
    try:
        target_kb = int(target_kb)
    except (TypeError, ValueError):
        console.print("[red]Invalid number, defaulting to 100 KB.[/red]")
        target_kb = 100

    out_folder = get_desktop_path() / "Compressed"
    out_folder.mkdir(parents=True, exist_ok=True)

    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("File")
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Status", justify="center")

    ok_count = 0
    with Progress(TextColumn("[progress.description]{task.description}"), BarColumn(), console=console) as progress:
        task = progress.add_task("Compressing...", total=len(files))
        for f in files:
            try:
                before_kb = f.stat().st_size / 1024
                img = Image.open(f)
                data, after_kb = _compress_one(img, target_kb)
                out_path = unique_path(out_folder / (f.stem + ".jpg"))
                out_path.write_bytes(data)
                success = after_kb <= target_kb
                ok_count += success
                table.add_row(
                    f.name, f"{before_kb:.1f} KB", f"{after_kb:.1f} KB",
                    "[green]OK[/green]" if success else "[yellow]too big[/yellow]",
                )
            except Exception as e:
                table.add_row(f.name, "-", "-", f"[red]error: {e}[/red]")
            progress.advance(task)

    console.print(table)
    console.print(f"\n[bold]{ok_count}/{len(files)}[/bold] compressed under {target_kb} KB.")
    console.print(f"Saved to: [cyan]{out_folder}[/cyan]")
    open_in_file_manager(out_folder)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 2 — FIND DUPLICATES  (merges duplicatefiles.py + duplicate_photos.py)
# ══════════════════════════════════════════════════════════════════════════

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tiff", ".tif", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".avi", ".m4v", ".mkv"}


def _file_hash(path: Path) -> str | None:
    hasher = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def _find_duplicates_by_name(folder: Path):
    seen, dupes = {}, []
    all_files = list(folder.rglob("*"))
    files_only = [f for f in all_files if f.is_file()]
    for f in files_only:
        try:
            key = (f.name.lower(), f.stat().st_size, f.suffix.lower())
        except OSError:
            continue
        if key in seen:
            dupes.append((f, seen[key]))
        else:
            seen[key] = f
    return dupes, len(files_only)


def _find_duplicates_by_content(folder: Path):
    """Content-hash duplicates for images, plus Live Photo (IMG+MOV) pairing."""
    files_by_stem = defaultdict(set)
    all_media = []
    for f in folder.rglob("*"):
        if not f.is_file() or f.name.startswith("."):
            continue
        suffix = f.suffix.lower()
        if suffix in IMAGE_EXTENSIONS or suffix in VIDEO_EXTENSIONS:
            files_by_stem[(str(f.parent), f.stem)].add(suffix)
            all_media.append(f)

    live_photos = sum(
        1 for exts in files_by_stem.values()
        if (exts & IMAGE_EXTENSIONS) and (exts & VIDEO_EXTENSIONS)
    )

    seen_hashes, dupes = {}, []
    for f in all_media:
        if f.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        h = _file_hash(f)
        if not h:
            continue
        if h in seen_hashes:
            dupes.append((f, seen_hashes[h]))
        else:
            seen_hashes[h] = f
    return dupes, len(all_media), live_photos


def tool_find_duplicates() -> None:
    section("Find Duplicates (Files or Photos)")
    send2trash = ensure_import("send2trash")
    if not send2trash:
        return

    mode = questionary.select(
        "How should duplicates be detected?",
        choices=[
            questionary.Choice("Quick — same name, size & extension", value="name"),
            questionary.Choice("Thorough — same content (hash) + Live Photo pairing", value="hash"),
        ],
        style=THEME,
    ).ask()
    if not mode:
        return

    folder = pick_folder("Select the folder to scan")
    if not folder:
        console.print("[yellow]No folder selected.[/yellow]")
        return

    console.print(f"\n[cyan]Scanning[/cyan] {folder} ...")

    if mode == "name":
        dupes, total = _find_duplicates_by_name(folder)
        console.print(f"Scanned {total} files.")
    else:
        dupes, total, live = _find_duplicates_by_content(folder)
        console.print(f"Scanned {total} media files. Detected {live} Live Photo pair(s).")

    if not dupes:
        console.print("[green]No duplicates found.[/green]")
        return

    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Duplicate")
    table.add_column("Original")
    for dup, original in dupes:
        table.add_row(str(dup), str(original))
    console.print(table)

    if questionary.confirm(f"Move all {len(dupes)} duplicate(s) to the Recycle Bin / Trash?", default=False, style=THEME).ask():
        for dup, _ in dupes:
            try:
                send2trash.send2trash(str(dup))
            except Exception as e:
                console.print(f"[red]Could not delete {dup}: {e}[/red]")
        console.print(f"[green]{len(dupes)} duplicate(s) moved to Trash.[/green]")
    else:
        console.print("[yellow]No files were deleted.[/yellow]")


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 3 — UNLOCK PDF
# ══════════════════════════════════════════════════════════════════════════

def tool_unlock_pdf() -> None:
    section("Unlock PDF")
    pypdf = ensure_import("pypdf")
    if not pypdf:
        return
    from pypdf import PdfReader, PdfWriter

    files = pick_files("Select the PDF you want to unlock", filetypes=[("PDF files", "*.pdf")], multiple=False)
    if not files:
        console.print("[yellow]No file selected.[/yellow]")
        return
    input_path = files[0]

    try:
        reader = PdfReader(str(input_path))
    except Exception as e:
        console.print(f"[red]Could not open PDF: {e}[/red]")
        return

    if reader.is_encrypted:
        decrypted = False
        try:
            decrypted = bool(reader.decrypt(""))
        except Exception:
            decrypted = False

        attempts = 0
        while not decrypted and attempts < 3:
            attempts += 1
            password = ask_password(
                "Password required",
                f'Enter password for "{input_path.name}" (attempt {attempts}/3):',
            )
            if password is None:
                console.print("[yellow]Cancelled — no password entered.[/yellow]")
                return
            try:
                decrypted = bool(reader.decrypt(password))
            except Exception:
                decrypted = False
            if not decrypted:
                console.print("[red]Incorrect password.[/red]")

        if not decrypted:
            console.print("[red]Failed to unlock after 3 attempts.[/red]")
            return
    else:
        console.print("[yellow]This PDF is not password-protected. Saving a plain copy anyway.[/yellow]")

    out_folder = get_desktop_path() / "Unlocked PDF"
    out_folder.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(out_folder / input_path.name)

    try:
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        console.print(f"[red]Could not save unlocked PDF: {e}[/red]")
        return

    console.print(f"[green]Unlocked successfully![/green] Saved to: [cyan]{output_path}[/cyan]")
    open_in_file_manager(out_folder)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 4 — PDF TO JPG
# ══════════════════════════════════════════════════════════════════════════

def tool_pdf_to_jpg() -> None:
    section("PDF to JPG")
    fitz = ensure_import("fitz", "pymupdf")
    if not fitz:
        return

    files = pick_files("Select a PDF file to convert", filetypes=[("PDF files", "*.pdf")], multiple=False)
    if not files:
        console.print("[yellow]No file selected.[/yellow]")
        return
    pdf_path = files[0]

    dpi = questionary.text("Render quality (DPI)?", default="300", style=THEME).ask()
    try:
        dpi = int(dpi)
    except (TypeError, ValueError):
        dpi = 300

    out_folder = get_desktop_path() / "JPG Converted"
    out_folder.mkdir(parents=True, exist_ok=True)

    saved = 0
    try:
        with fitz.open(str(pdf_path)) as doc:
            total = doc.page_count
            with Progress(TextColumn("[progress.description]{task.description}"), BarColumn(), console=console) as progress:
                task = progress.add_task("Converting pages...", total=total)
                for i, page in enumerate(doc, start=1):
                    pix = page.get_pixmap(dpi=dpi, alpha=False)
                    jpg_path = unique_path(out_folder / f"{pdf_path.stem}_page_{i}.jpg")
                    jpg_path.write_bytes(pix.tobytes("jpeg"))
                    saved += 1
                    progress.advance(task)
    except Exception as e:
        console.print(f"[red]Conversion failed: {e}[/red]")
        return

    console.print(f"[green]Converted {saved} page(s).[/green] Saved to: [cyan]{out_folder}[/cyan]")
    open_in_file_manager(out_folder)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 5 — RENAME IMAGES BY DATE TAKEN
# ══════════════════════════════════════════════════════════════════════════

def _get_date_taken(path: Path) -> datetime:
    if is_mac():
        try:
            result = subprocess.run(
                ["mdls", "-name", "kMDItemContentCreationDate", "-raw", str(path)],
                capture_output=True, text=True,
            )
            output = result.stdout.strip()
            if output and output != "(null)":
                return datetime.strptime(output, "%Y-%m-%d %H:%M:%S %z")
        except Exception:
            pass
    else:
        try:
            from PIL import Image, ExifTags
            img = Image.open(path)
            exif = img.getexif()
            date_tag = next((k for k, v in ExifTags.TAGS.items() if v == "DateTimeOriginal"), None)
            if date_tag and date_tag in exif:
                return datetime.strptime(exif[date_tag], "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def tool_rename_images() -> None:
    section("Rename Image File Names by Date")
    folder = pick_folder("Select the folder containing images")
    if not folder:
        console.print("[yellow]No folder selected.[/yellow]")
        return

    images = [f for f in folder.rglob("*") if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in IMAGE_EXTENSIONS]
    if not images:
        console.print("[yellow]No supported images found in that folder.[/yellow]")
        return

    console.print(f"Found {len(images)} image(s). Sorting by date taken...")
    images.sort(key=_get_date_taken)

    if not questionary.confirm(
        f"Rename {len(images)} images to IMG_001, IMG_002, ... ?", default=False, style=THEME
    ).ask():
        console.print("[yellow]Cancelled.[/yellow]")
        return

    # Rename in two passes through a temp name to avoid collisions.
    temp_files = []
    for i, f in enumerate(images, start=1):
        temp_path = f.with_name(f"__TEMP_RENAME_{i:05d}{f.suffix}")
        try:
            f.rename(temp_path)
            temp_files.append((temp_path, f.suffix))
        except Exception as e:
            console.print(f"[red]Error preparing {f.name}: {e}[/red]")

    renamed = 0
    for i, (temp_path, suffix) in enumerate(temp_files, start=1):
        new_path = temp_path.with_name(f"IMG_{i:03d}{suffix}")
        try:
            temp_path.rename(new_path)
            renamed += 1
        except Exception as e:
            console.print(f"[red]Error renaming {temp_path.name}: {e}[/red]")

    console.print(f"[green]Renamed {renamed} image(s) in {folder}[/green]")


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 6 — YOUTUBE VIDEO DOWNLOADER  (rewritten: original ytdownload.py lost)
# ══════════════════════════════════════════════════════════════════════════

def tool_youtube_video() -> None:
    section("YouTube Video Downloader")
    yt_dlp = ensure_import("yt_dlp")
    if not yt_dlp:
        return

    url = questionary.text("Paste the YouTube video (or playlist) URL:", style=THEME).ask()
    if not url:
        return

    folder = pick_folder("Choose where to save the video") or (get_desktop_path() / "YouTube Downloads")
    folder.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": str(folder / "%(title)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noprogress": False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        console.print(f"[green]Download complete.[/green] Saved to: [cyan]{folder}[/cyan]")
        open_in_file_manager(folder)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 7 — YOUTUBE TO MP3  (merges mp3download.py + youtubesongs.py — lost)
# ══════════════════════════════════════════════════════════════════════════

def tool_youtube_mp3() -> None:
    section("YouTube to MP3")
    yt_dlp = ensure_import("yt_dlp")
    if not yt_dlp:
        return
    if not ensure_binary("ffmpeg", "winget install Gyan.FFmpeg   (macOS: brew install ffmpeg)"):
        return

    url = questionary.text("Paste the YouTube video (or playlist) URL:", style=THEME).ask()
    if not url:
        return

    folder = pick_folder("Choose where to save the MP3(s)") or (get_desktop_path() / "YouTube MP3s")
    folder.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": str(folder / "%(title)s.%(ext)s"),
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        console.print(f"[green]Download complete.[/green] Saved to: [cyan]{folder}[/cyan]")
        open_in_file_manager(folder)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 8 — INSTAGRAM DOWNLOADER  (rewritten: original instadownload.py lost)
# ══════════════════════════════════════════════════════════════════════════

def tool_instagram_download() -> None:
    section("Instagram Post or Reel Downloader")
    instaloader = ensure_import("instaloader")
    if not instaloader:
        return

    target = questionary.text(
        "Public Instagram username, or a post/reel URL:", style=THEME
    ).ask()
    if not target:
        return

    folder = pick_folder("Choose where to save the download") or (get_desktop_path() / "Instagram Downloads")
    folder.mkdir(parents=True, exist_ok=True)

    loader = instaloader.Instaloader(
        dirname_pattern=str(folder),
        save_metadata=False,
        download_video_thumbnails=False,
        post_metadata_txt_pattern="",
    )

    try:
        match = re.search(r"instagram\.com/(?:p|reel)/([^/?]+)", target)
        if match:
            shortcode = match.group(1)
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            loader.download_post(post, target=folder.name)
        else:
            username = target.strip().lstrip("@")
            profile = instaloader.Profile.from_username(loader.context, username)
            loader.download_profile(profile, profile_pic=False)
        console.print(f"[green]Download complete.[/green] Saved to: [cyan]{folder}[/cyan]")
        open_in_file_manager(folder)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red] "
                      f"(private accounts or rate limits may require a logged-in session)")


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 9 — PINTEREST DOWNLOADER  (rewritten: original pinterestdownloader.py lost)
# ══════════════════════════════════════════════════════════════════════════

def tool_pinterest_download() -> None:
    section("Pinterest Post Downloader")
    gallery_dl = ensure_import("gallery_dl")
    if not gallery_dl:
        return

    url = questionary.text("Paste a Pinterest pin or board URL:", style=THEME).ask()
    if not url:
        return

    folder = pick_folder("Choose where to save the download") or (get_desktop_path() / "Pinterest Downloads")
    folder.mkdir(parents=True, exist_ok=True)

    try:
        from gallery_dl import config as gdl_config, job as gdl_job
        gdl_config.set((), "base-directory", str(folder))
        gdl_job.DownloadJob(url).run()
        console.print(f"[green]Download complete.[/green] Saved to: [cyan]{folder}[/cyan]")
        open_in_file_manager(folder)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 10 — VIDEO TRIMMER  (rewritten: original videocutter.py lost)
# ══════════════════════════════════════════════════════════════════════════

def tool_video_trimmer() -> None:
    section("Video Trimmer")
    if not ensure_binary("ffmpeg", "winget install Gyan.FFmpeg   (macOS: brew install ffmpeg)"):
        return

    files = pick_files(
        "Select the video to trim",
        filetypes=[("Videos", "*.mp4 *.mov *.mkv *.avi *.m4v")],
        multiple=False,
    )
    if not files:
        console.print("[yellow]No file selected.[/yellow]")
        return
    video_path = files[0]

    start = questionary.text("Start time (HH:MM:SS, e.g. 00:00:10):", default="00:00:00", style=THEME).ask()
    end = questionary.text("End time (HH:MM:SS, e.g. 00:01:30):", style=THEME).ask()
    if not end:
        console.print("[yellow]No end time given — cancelled.[/yellow]")
        return

    out_folder = get_desktop_path() / "Trimmed Videos"
    out_folder.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(out_folder / f"{video_path.stem}_trimmed{video_path.suffix}")

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-ss", start, "-to", end,
        "-c", "copy", str(output_path),
    ]
    console.print("[cyan]Trimming with ffmpeg...[/cyan]")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]ffmpeg error:[/red]\n{result.stderr[-800:]}")
            return
    except Exception as e:
        console.print(f"[red]Failed to run ffmpeg: {e}[/red]")
        return

    console.print(f"[green]Trimmed video saved to:[/green] [cyan]{output_path}[/cyan]")
    open_in_file_manager(out_folder)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 11 — IMAGES TO PDF  (JPG or PNG to PDF)
# ══════════════════════════════════════════════════════════════════════════

def _load_rgb_image(path: Path):
    from PIL import Image
    img = Image.open(path)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background.convert("RGB")
    else:
        img = img.convert("RGB")
    return img


def tool_images_to_pdf() -> None:
    section("Images to PDF")
    PIL = ensure_import("PIL", "pillow")
    if not PIL:
        return

    files = pick_files(
        "Select JPG/PNG images to convert to PDF",
        filetypes=[("Images", "*.jpg *.jpeg *.png")],
    )
    if not files:
        console.print("[yellow]No files selected.[/yellow]")
        return

    mode = questionary.select(
        "How do you want to combine them?",
        choices=[
            questionary.Choice("Combine into one PDF", value="combine"),
            questionary.Choice("One PDF per image", value="separate"),
        ],
        style=THEME,
    ).ask()
    if not mode:
        return

    out_folder = get_desktop_path() / "Images to PDF"
    out_folder.mkdir(parents=True, exist_ok=True)

    try:
        if mode == "combine":
            images = [_load_rgb_image(f) for f in files]
            output_path = unique_path(out_folder / "Combined.pdf")
            images[0].save(output_path, save_all=True, append_images=images[1:])
            console.print(f"[green]Created 1 PDF with {len(images)} page(s).[/green]")
        else:
            count = 0
            for f in files:
                output_path = unique_path(out_folder / f"{f.stem}.pdf")
                _load_rgb_image(f).save(output_path)
                count += 1
            console.print(f"[green]Created {count} PDF file(s).[/green]")
    except Exception as e:
        console.print(f"[red]Conversion failed: {e}[/red]")
        return

    console.print(f"Saved to: [cyan]{out_folder}[/cyan]")
    open_in_file_manager(out_folder)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 12 — PDF TO WORD
# ══════════════════════════════════════════════════════════════════════════

def tool_pdf_to_word() -> None:
    section("PDF to Word")
    pdf2docx = ensure_import("pdf2docx")
    if not pdf2docx:
        return
    from pdf2docx import Converter

    files = pick_files("Select the PDF to convert", filetypes=[("PDF files", "*.pdf")], multiple=False)
    if not files:
        console.print("[yellow]No file selected.[/yellow]")
        return
    pdf_path = files[0]

    out_folder = get_desktop_path() / "Word Converted"
    out_folder.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(out_folder / f"{pdf_path.stem}.docx")

    console.print("[cyan]Converting... this can take a moment for large PDFs.[/cyan]")
    try:
        converter = Converter(str(pdf_path))
        converter.convert(str(output_path))
        converter.close()
    except Exception as e:
        console.print(f"[red]Conversion failed: {e}[/red]")
        return

    console.print(f"[green]Converted successfully![/green] Saved to: [cyan]{output_path}[/cyan]")
    open_in_file_manager(out_folder)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 13 — LOCK PDF
# ══════════════════════════════════════════════════════════════════════════

def tool_lock_pdf() -> None:
    section("Lock PDF")
    pypdf = ensure_import("pypdf")
    if not pypdf:
        return
    from pypdf import PdfReader, PdfWriter

    files = pick_files("Select the PDF you want to lock", filetypes=[("PDF files", "*.pdf")], multiple=False)
    if not files:
        console.print("[yellow]No file selected.[/yellow]")
        return
    input_path = files[0]

    password = ask_password("Set password", f'Enter a password to lock "{input_path.name}":')
    if not password:
        console.print("[yellow]No password entered — cancelled.[/yellow]")
        return
    confirm = ask_password("Confirm password", "Re-enter the same password:")
    if password != confirm:
        console.print("[red]Passwords did not match. Cancelled.[/red]")
        return

    try:
        reader = PdfReader(str(input_path))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password)
    except Exception as e:
        console.print(f"[red]Could not lock PDF: {e}[/red]")
        return

    out_folder = get_desktop_path() / "Locked PDF"
    out_folder.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(out_folder / input_path.name)
    try:
        with open(output_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        console.print(f"[red]Could not save locked PDF: {e}[/red]")
        return

    console.print(f"[green]PDF locked successfully![/green] Saved to: [cyan]{output_path}[/cyan]")
    open_in_file_manager(out_folder)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 14 — DOWNLOAD FILEFORGE TOOLKIT (Windows-only companion app)
# ══════════════════════════════════════════════════════════════════════════

FILEFORGE_LATEST_URL = "https://github.com/rahulswargam/ImagePDFToolkit/releases/latest"


def tool_download_fileforge() -> None:
    section("Download FileForge Toolkit")
    console.print("FileForge Toolkit is a [bold]Windows-only[/bold] desktop application.")
    if not is_windows():
        if not questionary.confirm(
            f"You're on {platform.system()}, not Windows. Open the download page anyway?",
            default=True, style=THEME,
        ).ask():
            return
    console.print(f"Opening the latest release: [cyan]{FILEFORGE_LATEST_URL}[/cyan]")
    webbrowser.open(FILEFORGE_LATEST_URL)


# ══════════════════════════════════════════════════════════════════════════
#  TOOL 15 — VISIT MY WEBSITE
# ══════════════════════════════════════════════════════════════════════════

WEBSITE_URL = "https://www.rahulswargam.online"


def tool_visit_website() -> None:
    section("Visit My Website")
    console.print(f"Opening: [cyan]{WEBSITE_URL}[/cyan]")
    webbrowser.open(WEBSITE_URL)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════════════════

def _figlet_banner() -> str | None:
    """Big block-letter banner via pyfiglet's compact 'small' font (~58 cols
    wide, vs. ~70-90 for standard figlet fonts). The earlier hand-written
    banner overlapped/garbled because it was wider than the user's terminal,
    so the wrapped remainder of each row bled into the next — this stays
    narrow enough to fit comfortably even in a half-width terminal."""
    try:
        import pyfiglet
    except ImportError:
        return None
    art = pyfiglet.figlet_format("Rahul's Toolbox", font="small")
    lines = art.rstrip("\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def print_header() -> None:
    console.clear()
    art = _figlet_banner()
    subtitle = Text(f"Running on {platform.system()}  |  {TOTAL_TOOLS} tools loaded", style="dim", justify="center")

    # Only use the big banner if it actually fits — otherwise it wraps and
    # looks like exactly the garbled mess this function exists to avoid.
    art_width = max((len(line) for line in art.split("\n")), default=0) if art else 0
    if art and art_width + 8 <= console.width:
        art_text = Text(art, style="bold cyan", justify="center", no_wrap=True)
        console.print(Panel(Group(art_text, Text(""), subtitle), border_style="cyan", box=box.DOUBLE, padding=(1, 4)))
    else:
        title = Text("RAHUL'S TOOLBOX", style="bold cyan", justify="center")
        console.print(Panel(Group(title, subtitle), border_style="cyan", box=box.DOUBLE, padding=(1, 4)))


MENU_GROUPS = [
    ("Image Tools", [
        ("Compress Images", tool_compress_images),
        ("Images to PDF (JPG/PNG)", tool_images_to_pdf),
        ("Rename Image File Names by Date", tool_rename_images),
    ]),
    ("PDF Tools", [
        ("PDF to JPG", tool_pdf_to_jpg),
        ("PDF to Word", tool_pdf_to_word),
        ("Unlock PDF", tool_unlock_pdf),
        ("Lock PDF", tool_lock_pdf),
    ]),
    ("File Management", [
        ("Find Duplicates (Files or Photos)", tool_find_duplicates),
    ]),
    ("Downloaders", [
        ("YouTube Video Downloader", tool_youtube_video),
        ("YouTube to MP3", tool_youtube_mp3),
        ("Instagram Post or Reel Downloader", tool_instagram_download),
        ("Pinterest Post Downloader", tool_pinterest_download),
    ]),
    ("Video Tools", [
        ("Video Trimmer", tool_video_trimmer),
    ]),
    ("More", [
        ("Download FileForge Toolkit (Windows)", tool_download_fileforge),
        ("Visit My Website", tool_visit_website),
    ]),
]

TOTAL_TOOLS = sum(len(tools) for _, tools in MENU_GROUPS)

CATEGORY_ICONS = {
    "Image Tools": "◆",
    "PDF Tools": "▪",
    "File Management": "▸",
    "Downloaders": "↓",
    "Video Tools": "▶",
    "More": "★",
}


# ══════════════════════════════════════════════════════════════════════════
#  GRID PICKER  —  arrow-key navigable card grid (questionary.select can only
#  scroll a single vertical column; this uses prompt_toolkit directly — the
#  same library questionary is built on — to get real left/right/up/down
#  movement between cards).
# ══════════════════════════════════════════════════════════════════════════

_EXIT = object()

FOOTER_LINE = "Created & Built by Rahul Swargam ❤  All rights reserved."


def _build_grid_model():
    """Flatten MENU_GROUPS into one page: every tool gets a global index,
    grouped into per-category blocks. Each block picks its own column count
    from its own longest tool name (so a block of short names like PDF Tools
    packs tighter than one with long names like Downloaders)."""
    global_items = []  # index -> (label, value)
    blocks = []        # {"header", "icon", "rows": [[gidx, ...], ...], "card_width"}
    gidx = 0

    for category, tools in MENU_GROUPS:
        card_width = max(20, max(len(name) for name, _ in tools) + 4)
        cols = max(1, min(console.width // (card_width + 2), len(tools), 4))
        indices = list(range(gidx, gidx + len(tools)))
        rows = [indices[i:i + cols] for i in range(0, len(indices), cols)]
        for name, fn in tools:
            global_items.append((name, fn))
        gidx += len(tools)
        blocks.append({"header": category, "icon": CATEGORY_ICONS.get(category, "•"), "rows": rows, "card_width": card_width})

    global_items.append(("Exit", _EXIT))
    blocks.append({"header": None, "icon": None, "rows": [[gidx]], "card_width": 20})

    all_rows = []
    for block in blocks:
        all_rows.extend(block["rows"])

    return global_items, blocks, all_rows


def _rows_move(cur_idx: int, key: str, all_rows: list) -> int:
    """Arrow-key math over an explicit list of rows (each row a list of
    global indices). Handles a grid where *every* block's last row can be
    ragged, not just the very last one overall — unlike a fixed-columns
    formula, this just looks up neighboring rows directly."""
    pos = None
    for r, row in enumerate(all_rows):
        if cur_idx in row:
            pos = (r, row.index(cur_idx))
            break
    if pos is None:
        return cur_idx
    r, c = pos

    if key == "left":
        return all_rows[r][c - 1] if c > 0 else cur_idx
    if key == "right":
        return all_rows[r][c + 1] if c < len(all_rows[r]) - 1 else cur_idx
    if key == "up":
        if r == 0:
            return cur_idx
        prev_row = all_rows[r - 1]
        return prev_row[min(c, len(prev_row) - 1)]
    if key == "down":
        if r == len(all_rows) - 1:
            return cur_idx
        next_row = all_rows[r + 1]
        return next_row[min(c, len(next_row) - 1)]
    return cur_idx


def _leaf_card_lines(label: str, width: int) -> list:
    inner = width - 2
    text = label[:inner]
    pad = inner - len(text)
    left = pad // 2
    middle = " " * left + text + " " * (pad - left)
    return ["┌" + "─" * inner + "┐", "│" + middle + "│", "└" + "─" * inner + "┘"]


def _leaf_card_lines_selected(label: str, width: int) -> list:
    """Same as _leaf_card_lines but with a double-line border and a leading
    '> ' marker — a shape-based selection indicator that stays visible even
    if a terminal's color scheme renders the cyan background poorly."""
    inner = width - 2
    text = ("> " + label)[:inner]
    pad = inner - len(text)
    left = pad // 2
    middle = " " * left + text + " " * (pad - left)
    return ["╔" + "═" * inner + "╗", "║" + middle + "║", "╚" + "═" * inner + "╝"]


def _compute_line_spans(blocks: list) -> dict:
    """Every card's (top_line, bottom_line) on the page, purely from the
    model — a card's position never depends on which one is selected, so
    this only needs to run once per grid, not on every redraw. Must mirror
    grid_select_all's get_fragments() line-by-line or the two drift apart."""
    spans = {}
    line_no = 1 + 2  # title line, then instruction line + its trailing blank
    for block in blocks:
        if block["header"]:
            line_no += 2  # header line + its trailing blank
        for row in block["rows"]:
            top, bottom = line_no, line_no + 2  # each card is 3 lines tall
            for i in row:
                spans[i] = (top, bottom)
            line_no += 3
        line_no += 1  # blank line after the block
    return spans


def _render_grid_fragments(blocks, global_items, selected_idx: int, title: str) -> list:
    """Pure rendering: (blocks, global_items, selected index) -> fragments.
    Kept standalone (not a closure inside grid_select_all) so it can be
    called directly in tests without spinning up a real Application, and so
    _compute_line_spans has one exact emission sequence to stay in sync
    with instead of a copy buried in a closure."""
    fragments = []

    def emit(style, text):
        fragments.append((style, text))

    emit("class:instruction", f"{title}\n")
    emit("class:instruction", "(arrow keys to move, Enter to select, Esc to quit)\n\n")

    for block in blocks:
        if block["header"]:
            emit("class:header", f"{block['icon']} {block['header'].upper()}\n\n")
        card_width = block["card_width"]
        for row in block["rows"]:
            lines_per_card = {}
            for i in row:
                render = _leaf_card_lines_selected if i == selected_idx else _leaf_card_lines
                lines_per_card[i] = render(global_items[i][0], card_width)
            for line_idx in range(3):
                for i in row:
                    style = "class:selected" if i == selected_idx else "class:card"
                    emit(style, lines_per_card[i][line_idx])
                    emit("", "  ")
                emit("", "\n")
        emit("", "\n")

    emit("class:footer", FOOTER_LINE)
    return fragments


def grid_select_all(global_items, blocks, all_rows, title: str):
    """One full-screen page showing every tool as a card, grouped under its
    category header, navigable with the arrow keys.

    Scrolling is driven the way prompt_toolkit actually expects: through
    get_cursor_position + scroll_offsets. Window._scroll_without_linewrapping
    recomputes self.vertical_scroll from ui_content.cursor_position on every
    single render — manually assigning window.vertical_scroll ourselves gets
    silently overwritten the very next frame (it falls back to cursor (0, 0)
    with no scroll_offsets registered, which is why the pointer could seem to
    vanish: the view kept snapping back near the top regardless of selection).
    scroll_offsets=(bottom=2) keeps the 2 lines below the cursor line (the
    card's label + bottom border) visible, completing the 3-line card. The
    first-row special case reports the cursor at the absolute top (0) instead
    of the card's real line, which forces scroll all the way to 0 — otherwise
    a top margin only guarantees "N lines above cursor", not "the true top",
    so the title could stay one row short of fully back in view."""
    line_spans = _compute_line_spans(blocks)  # static: doesn't depend on selection
    first_row = set(all_rows[0])
    state = {"idx": 0, "result": 0, "cancelled": False}

    def get_fragments():
        return _render_grid_fragments(blocks, global_items, state["idx"], title)

    def get_cursor_position():
        if state["idx"] in first_row:
            return Point(x=0, y=0)
        top, _ = line_spans[state["idx"]]
        return Point(x=0, y=top)

    kb = KeyBindings()

    @kb.add("left")
    def _(event):
        state["idx"] = _rows_move(state["idx"], "left", all_rows)

    @kb.add("right")
    def _(event):
        state["idx"] = _rows_move(state["idx"], "right", all_rows)

    @kb.add("up")
    def _(event):
        state["idx"] = _rows_move(state["idx"], "up", all_rows)

    @kb.add("down")
    def _(event):
        state["idx"] = _rows_move(state["idx"], "down", all_rows)

    @kb.add("enter")
    def _(event):
        state["result"] = state["idx"]
        event.app.exit()

    @kb.add("c-c")
    @kb.add("escape")
    @kb.add("q")
    def _(event):
        state["cancelled"] = True
        event.app.exit()

    style = PTStyle.from_dict({
        "card": "fg:#6c6c6c",
        "selected": "fg:#000000 bg:#00d7ff bold",
        "instruction": "fg:#00d7ff bold",
        "header": "fg:#ffaf5f bold",
        "footer": "fg:#6c6c6c italic",
    })

    control = FormattedTextControl(get_fragments, get_cursor_position=get_cursor_position)
    window = Window(control, scroll_offsets=ScrollOffsets(bottom=2))
    app = Application(
        layout=Layout(window),
        key_bindings=kb,
        style=style,
        full_screen=True,
    )
    app.run()

    return None if state["cancelled"] else state["result"]


def main() -> None:
    print_header()

    while True:
        global_items, blocks, all_rows = _build_grid_model()
        idx = grid_select_all(global_items, blocks, all_rows, "RAHUL'S TOOLBOX — What do you want to do?")

        if idx is None:
            console.print("\n[cyan]Goodbye![/cyan]")
            break

        label, value = global_items[idx]
        if value is _EXIT:
            console.print("\n[cyan]Goodbye![/cyan]")
            break

        try:
            value()
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Unexpected error: {e}[/red]")

        press_enter_to_continue()
        print_header()


if __name__ == "__main__":
    if not sys.stdin.isatty():
        print(
            "This is an interactive menu and needs a real terminal window.\n"
            "Open a Command Prompt / PowerShell / Terminal.app and run:\n"
            "    python toolbox.py"
        )
        sys.exit(1)
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[cyan]Goodbye![/cyan]")
    except Exception as e:
        if "Windows console" in str(e) or type(e).__name__ == "NoConsoleScreenBufferError":
            print(
                "\nThis menu needs a real Windows console to draw its arrow-key menus "
                "(Command Prompt, PowerShell, or Windows Terminal) — it can't run inside "
                "Git Bash / MinTTY.\n\nOpen PowerShell or cmd.exe and run:\n"
                "    python toolbox.py"
            )
            sys.exit(1)
        raise
