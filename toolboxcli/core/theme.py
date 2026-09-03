"""Theme tokens and terminal capability detection.

Single source of truth for the palette. Both the Textual CSS and the
plain-text fallback renderer read from here, so changing a colour in one
place changes it everywhere.
"""

from __future__ import annotations

import os
import sys

# ── Palette ───────────────────────────────────────────────────────────────
# JobSprint house style: violet brand accent + cyan interaction accent over
# plain terminal-dark surfaces — no filled colour panels. Selection is shown
# with a bold cyan indicator and border, never a solid background fill.
CHARCOAL = "#121212"        # background
CHARCOAL_LIGHT = "#1c1c1c"  # panels, inputs, elevated surfaces
CHARCOAL_DARK = "#0a0a0a"   # recessed surfaces (log panel)
BORDER = "grey37"           # default (inactive) borders
BRAND = "#d787ff"           # violet — headings, outer double-line borders
ACCENT = "#00d7ff"          # cyan — prompts, selection, active indicators
MUTED = "grey54"            # help text, footers, inactive items
OK = "#5fd75f"               # success
WARN = "#ffaf5f"             # warnings
BAD = "#ff5f5f"              # errors / failure
FOREGROUND = "#e4e4e4"

# ── Box drawing ───────────────────────────────────────────────────────────
# Rounded corners everywhere except the banner (double-line, JobSprint
# style); the active/selected state is conveyed with a cyan border and the
# "»" indicator rather than a heavier border weight or a filled background.
BOX_UNICODE = {
    "tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
    "h": "─", "v": "│",
    "cursor": "»",
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


def badge(text: str, color: str) -> str:
    """An outlined status label, e.g. badge("done", OK) -> '● DONE' in colour
    with no filled background — Rich markup, for use inside markup=True
    widgets."""
    return f"[bold {color}]● {text.upper()}[/]"


def key_hint(key: str, label: str) -> str:
    """A muted keybinding hint, e.g. 'Enter select' with the key in the
    accent colour and the label muted — no reverse-video or filled block."""
    return f"[bold {ACCENT}]{key}[/] [{MUTED}]{label}[/]"


AUTHOR = "Rahul Swargam"
VERSION = "2.0.0"
LICENSE = "MIT License"
