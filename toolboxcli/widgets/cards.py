"""Reusable UI components: the tool card and the app header."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static

from ..core import theme


class ToolCard(Static):
    """One selectable action button in the grid.

    The active state is driven by the `active` reactive rather than by focus,
    because navigation is owned by the screen's GridNavigator — the cards are
    purely presentational, which keeps the movement model testable in
    isolation from Textual.
    """

    active = reactive(False)

    def __init__(self, label: str, tool_key: str, row: int, col: int) -> None:
        super().__init__("")
        self.tool_label = label
        self.tool_key = tool_key
        self.row = row
        self.col = col

    def render(self) -> str:
        cursor = theme.box_chars()["cursor"]
        if self.active:
            return f"{cursor} {self.tool_label}"
        return f"  {self.tool_label}"

    def watch_active(self, active: bool) -> None:
        self.set_class(active, "-active")


class AppHeader(Static):
    """Title bar with keybinding hints and a live status line."""

    status = reactive("")

    def __init__(self) -> None:
        super().__init__("", id="app-header")

    def render(self) -> str:
        return "RAHUL'S TOOLBOX"


class HintBar(Static):
    def __init__(self) -> None:
        hints = "[↑↓←→] Navigate   [Enter] Select   [Esc] Quit"
        if not theme.supports_unicode():
            hints = "[Arrows] Navigate   [Enter] Select   [Esc] Quit"
        super().__init__(hints, id="hint-bar")


class StatusBar(Static):
    """Live status: working directory, tool count, version."""

    status_text = reactive("")

    def __init__(self, status_text: str = "") -> None:
        super().__init__("", id="status-bar")
        self.status_text = status_text

    def render(self) -> str:
        return self.status_text


class FooterCredit(Static):
    def __init__(self) -> None:
        super().__init__(
            f"{theme.AUTHOR}  ·  v{theme.VERSION}",
            id="footer-credit",
        )
