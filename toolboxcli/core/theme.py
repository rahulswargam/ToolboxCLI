"""Theme tokens and terminal capability detection.

Single source of truth for the palette. Both the Textual CSS and the
plain-text fallback renderer read from here, so changing a colour in one
place changes it everywhere.
"""

from __future__ import annotations

import os
import sys

# ── Palette ───────────────────────────────────────────────────────────────
# Dracula-inspired. Semantic buckets per the design brief: soft purple/blue
# for primary UI elements, muted grey for borders/secondary text, soft
# cyan/green for success, soft red/amber for errors and warnings.
CHARCOAL = "#282A36"        # background
CHARCOAL_LIGHT = "#343746"  # panels, inputs, elevated surfaces
CHARCOAL_DARK = "#21222C"   # recessed surfaces (log panel)
BORDER = "#44475A"          # default (inactive) borders
PRIMARY = "#BD93F9"         # cursor / active selection / primary accent
CYAN = "#8BE9FD"            # secondary highlight
AMBER = "#FFB86C"           # section headers, warnings
MAGENTA = "#FF79C6"         # secondary accents (prompts, decoration)
EMERALD = "#50FA7B"         # success
RED = "#FF5555"             # errors / failure
DIM = "#6272A4"             # muted borders / secondary text
FOREGROUND = "#F8F8F2"

# ── Box drawing ───────────────────────────────────────────────────────────
# Rounded corners only — no double-line or heavy borders anywhere in this
# theme; the active/selected state is conveyed with colour and a filled
# background instead of a heavier border weight.
BOX_UNICODE = {
    "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
    "h": "─", "v": "│",
    "cursor": "▶",
}

BOX_ASCII = {
    "tl": "+", "tr": "+", "bl": "+", "br": "+",
    "h": "-", "v": "|",
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


def badge(text: str, bg: str, fg: str = CHARCOAL) -> str:
    """A filled pill/badge label, e.g. badge("done", EMERALD) -> ' DONE '
    on a solid background — Rich markup, for use inside markup=True widgets."""
    return f"[on {bg} {fg} bold] {text.upper()} [/]"


AUTHOR = "Rahul Swargam"
VERSION = "2.0.0"
LICENSE = "MIT License"
