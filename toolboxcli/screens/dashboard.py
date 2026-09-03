"""The main dashboard: category rows of horizontally-aligned tool cards."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ..core import theme
from ..core.navigation import GridNavigator
from ..data.catalog import CATALOG
from ..widgets.cards import AppHeader, FooterCredit, HintBar, ToolCard


class CardRow(HorizontalScroll):
    """A scrollable card row that does NOT steal the arrow keys.

    Textual's scrollable containers bind the arrows for their own scrolling
    and are focusable by default, so without this the row would consume
    up/down before the screen's navigation bindings ever saw them.
    Scrolling is driven by scroll_visible() on the active card instead.
    """

    can_focus = False
    can_focus_children = False
    BINDINGS = []


class DashboardScreen(Screen):
    # priority=True so these win over any focused child widget's own bindings.
    BINDINGS = [
        Binding("up", "move('up')", "Up", show=False, priority=True),
        Binding("down", "move('down')", "Down", show=False, priority=True),
        Binding("left", "move('left')", "Left", show=False, priority=True),
        Binding("right", "move('right')", "Right", show=False, priority=True),
        Binding("home", "move('home')", "First", show=False, priority=True),
        Binding("end", "move('end')", "Last", show=False, priority=True),
        Binding("enter", "select", "Select", show=False, priority=True),
        Binding("escape", "quit_app", "Quit", show=False, priority=True),
        Binding("q", "quit_app", "Quit", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.navigator = GridNavigator([len(c.tools) for c in CATALOG])

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield HintBar()

        with VerticalScroll(id="grid-body"):
            icons = theme.category_icons()
            for row, category in enumerate(CATALOG):
                icon = icons.get(category.name, "*")
                yield Static(f"{icon}  {category.name.upper()}", classes="category-header")
                with CardRow(classes="card-row"):
                    for col, tool in enumerate(category.tools):
                        yield ToolCard(tool.label, tool.key, row, col)

        yield FooterCredit()

    def on_mount(self) -> None:
        self._refresh_active()

    def _cards(self) -> list[ToolCard]:
        return list(self.query(ToolCard))

    def _refresh_active(self) -> None:
        row, col = self.navigator.position
        active_card = None
        for card in self._cards():
            is_active = (card.row == row and card.col == col)
            card.active = is_active
            if is_active:
                active_card = card
        if active_card is not None:
            active_card.scroll_visible(animate=False)

    def action_move(self, direction: str) -> None:
        self.navigator.move(direction)
        self._refresh_active()

    def action_select(self) -> None:
        row, col = self.navigator.position
        tool = CATALOG[row].tools[col]
        self.app.launch_tool(tool.key)

    def action_quit_app(self) -> None:
        self.app.exit()
