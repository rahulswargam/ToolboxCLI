"""Tests for the pure navigation model and the live Textual app.

Run with:  python -m pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from toolboxcli.app import ToolboxApp
from toolboxcli.core.navigation import GridNavigator
from toolboxcli.core.runners import RUNNERS
from toolboxcli.data.catalog import CATALOG, all_tools
from toolboxcli.screens.dashboard import DashboardScreen
from toolboxcli.widgets.cards import ToolCard

ROWS = [len(c.tools) for c in CATALOG]


# ── Pure navigation model ────────────────────────────────────────────────

def test_every_move_stays_in_bounds():
    for row in range(len(ROWS)):
        for col in range(ROWS[row]):
            for direction in ("left", "right", "up", "down", "home", "end"):
                nav = GridNavigator(ROWS, row, col)
                new_row, new_col = nav.move(direction)
                assert 0 <= new_row < len(ROWS)
                assert 0 <= new_col < ROWS[new_row]


def test_horizontal_wraps_within_row():
    nav = GridNavigator(ROWS, 0, 0)
    assert nav.move("left") == (0, ROWS[0] - 1)
    nav = GridNavigator(ROWS, 0, ROWS[0] - 1)
    assert nav.move("right") == (0, 0)


def test_vertical_wraps_between_rows():
    nav = GridNavigator(ROWS, 0, 0)
    assert nav.move("up")[0] == len(ROWS) - 1
    nav = GridNavigator(ROWS, len(ROWS) - 1, 0)
    assert nav.move("down")[0] == 0


def test_column_clamps_onto_shorter_row():
    """PDF Tools has 4 tools; File Management has 1. Moving down from the
    4th column must land on the only column that exists below."""
    pdf_row = next(i for i, c in enumerate(CATALOG) if c.name == "PDF Tools")
    nav = GridNavigator(ROWS, pdf_row, 3)
    new_row, new_col = nav.move("down")
    assert new_col < ROWS[new_row]


def test_flat_index_round_trip():
    total = sum(ROWS)
    for i in range(total):
        nav = GridNavigator(ROWS)
        nav.set_flat_index(i)
        assert nav.flat_index() == i


def test_rejects_empty_rows():
    with pytest.raises(ValueError):
        GridNavigator([])
    with pytest.raises(ValueError):
        GridNavigator([2, 0, 1])


# ── Catalog integrity ────────────────────────────────────────────────────

def test_every_tool_has_a_runner():
    tool_keys = {t.key for t in all_tools()}
    assert tool_keys == set(RUNNERS)


def test_tool_keys_are_unique():
    keys = [t.key for t in all_tools()]
    assert len(keys) == len(set(keys))


# ── Live app (headless, via Textual's Pilot) ─────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_renders_every_tool():
    app = ToolboxApp()
    async with app.run_test(size=(120, 40)) as pilot:
        cards = list(app.screen.query(ToolCard))
        assert len(cards) == sum(ROWS)


@pytest.mark.asyncio
async def test_exactly_one_card_is_active_at_all_times():
    app = ToolboxApp()
    async with app.run_test(size=(120, 40)) as pilot:
        for keys in (
            [], ["right"], ["right", "right"], ["down"], ["down", "down"],
            ["down", "down", "down"], ["up"], ["left"], ["end"], ["home"],
            ["down", "right", "down", "left", "up"],
        ):
            for key in keys:
                await pilot.press(key)
            active = [c for c in app.screen.query(ToolCard) if c.active]
            assert len(active) == 1, f"after {keys}: {len(active)} active"
            await pilot.press("home")


@pytest.mark.asyncio
async def test_arrows_move_the_active_card():
    app = ToolboxApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.screen
        assert screen.navigator.position == (0, 0)
        await pilot.press("right")
        assert screen.navigator.position == (0, 1)
        await pilot.press("down")
        assert screen.navigator.position[0] == 1
        await pilot.press("left")
        await pilot.press("up")
        await pilot.press("home")
        assert screen.navigator.position == (0, 0)


@pytest.mark.asyncio
async def test_enter_opens_the_task_screen(monkeypatch):
    """Enter on a card pushes its TaskScreen.

    The first tool prompts with a native file picker, so that's stubbed —
    this test is about the screen transition, not the dialog.
    """
    from toolboxcli.core import platform as plat
    monkeypatch.setattr(plat, "pick_files", lambda *a, **k: [Path("stub.jpg")])
    monkeypatch.setattr(plat, "pick_folder", lambda *a, **k: Path("."))

    app = ToolboxApp()
    async with app.run_test(size=(120, 40)) as pilot:
        assert isinstance(app.screen, DashboardScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "TaskScreen"
        assert app.screen.tool_key == CATALOG[0].tools[0].key


@pytest.mark.asyncio
async def test_cancelling_the_picker_returns_to_dashboard(monkeypatch):
    """Dismissing the file dialog abandons the task instead of stranding
    the user on a half-filled task screen."""
    from toolboxcli.core import platform as plat
    monkeypatch.setattr(plat, "pick_files", lambda *a, **k: [])
    monkeypatch.setattr(plat, "pick_folder", lambda *a, **k: None)

    app = ToolboxApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)
