"""Theme tokens and terminal capability detection.

Single source of truth for the palette. Both the Textual CSS and the
plain-text fallback renderer read from here, so changing a colour in one
place changes it everywhere.
"""

from __future__ import annotations

import os
import sys

# ── Palette ───────────────────────────────────────────────────────────────
CHARCOAL = "#1A1B26"
CHARCOAL_LIGHT = "#24283B"
CYAN = "#7AA2F7"      # cursor / active selection
AMBER = "#FF9E64"     # section headers
MAGENTA = "#BB9AF7"   # secondary accents
EMERALD = "#9ECE6A"   # success / active execution
RED = "#F7768E"       # failure
DIM = "#565F89"
FOREGROUND = "#C0CAF5"

# ── Box drawing ───────────────────────────────────────────────────────────
# Two sets: the pretty one, and an ASCII-only fallback for terminals that
# can't render UTF-8 box characters.
BOX_UNICODE = {
    "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
    "h": "─", "v": "│",
    "tl_active": "╔", "tr_active": "╗", "bl_active": "╚", "br_active": "╝",
    "h_active": "═", "v_active": "║",
    "cursor": "▶",
}

BOX_ASCII = {
    "tl": "+", "tr": "+", "bl": "+", "br": "+",
    "h": "-", "v": "|",
    "tl_active": "+", "tr_active": "+", "bl_active": "+", "br_active": "+",
    "h_active": "=", "v_active": "|",
    "cursor": ">",
}

CATEGORY_ICONS_UNICODE = {
    "Image Tools": "◆",
    "PDF Tools": "■",
    "File Management": "▶",
    "Downloaders": "⬎",
    "Video Tools": "▶",
}

CATEGORY_ICONS_ASCII = {
    "Image Tools": "*",
    "PDF Tools": "#",
    "File Management": ">",
    "Downloaders": "v",
    "Video Tools": ">",
}

TOOL_ICONS_UNICODE = {
    "compress_images": "▽",
    "images_to_pdf": "⇒",
    "rename_by_date": "↻",
    "pdf_to_jpg": "▥",
    "pdf_to_word": "▤",
    "unlock_pdf": "⊙",
    "lock_pdf": "⊘",
    "resize_pdf": "▣",
    "find_duplicates": "⧉",
}

TOOL_ICONS_ASCII = {key: "-" for key in TOOL_ICONS_UNICODE}


def tool_icons() -> dict:
    return TOOL_ICONS_UNICODE if supports_unicode() else TOOL_ICONS_ASCII


def force_utf8_stdout() -> None:
    """Reconfigure stdout/stderr to UTF-8 where possible.

    Windows reports cp1252 for sys.stdout.encoding even in Windows Terminal,
    which renders box-drawing characters perfectly well. Without this, the
    capability probe below would needlessly downgrade a capable terminal to
    the ASCII fallback.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def supports_unicode() -> bool:
    """Whether the terminal can render box-drawing characters."""
    if os.environ.get("TOOLBOX_ASCII"):
        return False
    # Windows Terminal / VS Code / iTerm and friends advertise themselves and
    # handle UTF-8 fine regardless of what the codepage claims.
    if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM"):
        return True
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if "utf" in encoding:
        return True
    try:
        "╭─╮".encode(encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def supports_color() -> bool:
    """Whether ANSI colour should be emitted at all."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TOOLBOX_MONO"):
        return False
    return sys.stdout.isatty()


def box_chars() -> dict:
    return BOX_UNICODE if supports_unicode() else BOX_ASCII


def category_icons() -> dict:
    return CATEGORY_ICONS_UNICODE if supports_unicode() else CATEGORY_ICONS_ASCII


SPINNER_FRAMES_UNICODE = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_FRAMES_ASCII = ["|", "/", "-", "\\"]


def spinner_frames() -> list[str]:
    return SPINNER_FRAMES_UNICODE if supports_unicode() else SPINNER_FRAMES_ASCII


BADGE_OK = "✔" if supports_unicode() else "OK"
BADGE_FAIL = "✖" if supports_unicode() else "X"
BADGE_RUNNING = "●" if supports_unicode() else "*"

AUTHOR = "Rahul Swargam"
VERSION = "2.0.0"
LICENSE = "MIT License"
