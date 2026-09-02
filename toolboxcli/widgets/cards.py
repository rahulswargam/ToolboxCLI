"""Reusable UI components: the tool card, banner header, and hint bar."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from ..core import theme


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


def _figlet_banner(width: int) -> str | None:
    """Big block-letter title via pyfiglet's compact 'small' font (~58 cols),
    only used when it'll actually fit — otherwise the terminal wraps it into
    exactly the garbled mess a banner is supposed to avoid."""
    if not theme.supports_unicode():
        return None
    try:
        import pyfiglet
    except ImportError:
        return None
    try:
        art = pyfiglet.figlet_format("Rahul's Toolbox", font="small")
    except Exception:
        return None
    lines = [line for line in art.rstrip("\n").split("\n") if line.strip() or True]
    while lines and not lines[-1].strip():
        lines.pop()
    banner_width = max((len(line) for line in lines), default=0)
    if not lines or banner_width + 4 > width:
        return None
    return "\n".join(lines)


class AppHeader(Static):
    """Title bar: big banner when there's room, plain title otherwise."""

    def __init__(self) -> None:
        super().__init__("", id="app-header", markup=False)

    def on_mount(self) -> None:
        self.call_after_refresh(self.refresh)

    def on_resize(self, event) -> None:
        self.refresh()

    def render(self) -> str:
        # content_size (not size) — the header now has a border and padding,
        # so the outer widget size overstates the space actually available
        # for text before it would wrap.
        width = self.content_size.width or 80
        banner = _figlet_banner(width)
        return banner if banner else "RAHUL'S TOOLBOX"


class HintBar(Static):
    """Keybinding hints styled as keycaps (reverse-video blocks)."""

    def __init__(self) -> None:
        if theme.supports_unicode():
            keys = "↑ ↓ ← →"
        else:
            keys = "Arrow keys"
        markup = (
            f"[reverse] {keys} [/]  [dim]Navigate[/]"
            f"    [on {theme.PRIMARY} {theme.CHARCOAL} bold] Enter [/]  [dim]Select[/]"
            f"    [on {theme.RED} {theme.CHARCOAL} bold] Esc [/]  [dim]Quit[/]"
        )
        super().__init__(markup, id="hint-bar", markup=True)


class StatusBar(Static):
    """Live status: working directory, tool count, version."""

    status_text = reactive("")

    def __init__(self, status_text: str = "") -> None:
        super().__init__("", id="status-bar", markup=False)
        self.status_text = status_text

    def render(self) -> str:
        return self.status_text


class FooterCredit(Static):
    """A colorful credit line: author, a heart, license, and version each
    in their own accent colour rather than one flat dim string."""

    def __init__(self) -> None:
        heart = "❤" if theme.supports_unicode() else "<3"
        markup = (
            f"[dim]Created & Built by[/] [bold {theme.CYAN}]{theme.AUTHOR}[/] "
            f"[{theme.RED}]{heart}[/]   [dim]•[/]   "
            f"[bold {theme.MAGENTA}]{theme.LICENSE}[/]   [dim]•[/]   "
            f"[bold {theme.AMBER}]v{theme.VERSION}[/]"
        )
        super().__init__(markup, id="footer-credit", markup=True)
