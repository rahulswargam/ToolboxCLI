"""Reusable UI components: the tool card, banner header, and hint bar."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ..core import theme

TAGLINE = "Developer & Utility Toolkit"


class ToolCard(Static):
    """One selectable action button in the grid.

    The active state is driven by the `active` reactive rather than by focus,
    because navigation is owned by the screen's GridNavigator — the cards are
    purely presentational, which keeps the movement model testable in
    isolation from Textual. Selection is conveyed with a filled background
    and bold colour rather than a heavier (double-line) border, per the
    "avoid harsh double-lines" styling brief — see .-active in theme.tcss.
    """

    active = reactive(False)

    def __init__(self, label: str, tool_key: str, row: int, col: int) -> None:
        super().__init__("", markup=False)
        self.tool_label = label
        self.tool_key = tool_key
        self.row = row
        self.col = col
        self.icon = theme.tool_icons().get(tool_key, "•")

    def render(self) -> str:
        cursor = theme.box_chars()["cursor"]
        prefix = f"{cursor} " if self.active else "  "
        return f"{prefix}{self.icon} {self.tool_label}"

    def watch_active(self, active: bool) -> None:
        self.set_class(active, "-active")


def _figlet_rows(width: int) -> list[Text] | None:
    """Big block-letter title via pyfiglet's compact 'small' font, two-tone
    ("RAHUL'S" in accent cyan, "TOOLBOX" in brand violet) like JobSprint's
    banner — only used when it'll actually fit, otherwise the terminal
    would wrap it into exactly the garbled mess a banner is meant to avoid."""
    if not theme.supports_unicode():
        return None
    try:
        import pyfiglet
    except ImportError:
        return None
    try:
        left = pyfiglet.figlet_format("RAHUL'S", font="small").rstrip("\n").split("\n")
        right = pyfiglet.figlet_format("TOOLBOX", font="small").rstrip("\n").split("\n")
    except Exception:
        return None
    if len(left) != len(right):
        return None

    rows = []
    for left_part, right_part in zip(left, right):
        row = Text()
        row.append(left_part, style=f"bold {theme.ACCENT}")
        row.append(" ")
        row.append(right_part, style=f"bold {theme.BRAND}")
        rows.append(row)
    while rows and not rows[0].plain.strip():
        rows.pop(0)
    while rows and not rows[-1].plain.strip():
        rows.pop()
    if not rows:
        return None

    banner_width = max(row.cell_len for row in rows)
    if banner_width + 4 > width:
        return None
    return rows


class AppHeader(Static):
    """Title bar: big two-tone banner (or a plain title when there's no
    room), an underline rule, an italic tagline, and a "Created by" credit —
    all inside the one double-border box, JobSprint style."""

    def __init__(self) -> None:
        super().__init__("", id="app-header", markup=False)

    def on_mount(self) -> None:
        self.call_after_refresh(self.refresh)

    def on_resize(self, event) -> None:
        self.refresh()

    def render(self) -> Text:
        # content_size (not size) — the header now has a border and padding,
        # so the outer widget size overstates the space actually available
        # for text before it would wrap.
        width = self.content_size.width or 80
        rows = _figlet_rows(width)

        text = Text(justify="center")
        if rows:
            for row in rows:
                text.append_text(row)
                text.append("\n")
            title_width = max(row.cell_len for row in rows)
        else:
            text.append("RAHUL'S", style=f"bold {theme.ACCENT}")
            text.append(" ")
            text.append("TOOLBOX\n", style=f"bold {theme.BRAND}")
            title_width = len("RAHUL'S TOOLBOX")

        text.append("─" * title_width + "\n", style=theme.MUTED)
        text.append(f"{TAGLINE}\n\n", style="italic grey70")
        text.append("Created by ", style=theme.MUTED)
        text.append(theme.AUTHOR, style=f"bold {theme.BRAND}")
        return text


class HintBar(Static):
    """Keybinding hints as muted text with the key itself in accent cyan —
    no reverse-video or filled keycap blocks."""

    def __init__(self) -> None:
        keys = "↑ ↓ ← →" if theme.supports_unicode() else "Arrow keys"
        markup = (
            f"{theme.key_hint(keys, 'Navigate')}"
            f"    {theme.key_hint('Enter', 'Select')}"
            f"    {theme.key_hint('Esc', 'Quit')}"
        )
        super().__init__(markup, id="hint-bar", markup=True)


class FooterCredit(Static):
    """A muted footer line: license and version — author credit already
    lives in the banner, so it isn't repeated down here."""

    def __init__(self) -> None:
        markup = (
            f"[{theme.MUTED}]{theme.LICENSE}[/]   [{theme.MUTED}]•[/]   "
            f"[bold {theme.ACCENT}]v{theme.VERSION}[/]"
        )
        super().__init__(markup, id="footer-credit", markup=True)
