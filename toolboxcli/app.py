"""ToolboxCLI — application entry point.

Created & Built by Rahul Swargam.
"""

from __future__ import annotations

import sys
from pathlib import Path

from textual.app import App

from .core import theme
from .screens.dashboard import DashboardScreen
from .screens.task import TaskScreen


class ToolboxApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "RAHUL'S TOOLBOX"

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())

    def launch_tool(self, tool_key: str) -> None:
        self.push_screen(TaskScreen(tool_key))


def _fallback_notice() -> str:
    from .data.catalog import CATALOG
    lines = [
        "RAHUL'S TOOLBOX",
        "=" * 60,
        "",
        "This dashboard needs an interactive terminal to run.",
        "",
        "On Windows : Command Prompt, PowerShell, or Windows Terminal",
        "On macOS   : Terminal.app or iTerm2",
        "",
        "It cannot render inside Git Bash / MinTTY, a pipe, or a",
        "non-interactive shell.",
        "",
        "Available tools:",
    ]
    for category in CATALOG:
        lines.append(f"  {category.name}:")
        for tool in category.tools:
            lines.append(f"    - {tool.label}")
    lines += ["", theme.AUTHOR, ""]
    return "\n".join(lines)


def main() -> int:
    theme.force_utf8_stdout()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(_fallback_notice())
        return 1
    try:
        ToolboxApp().run()
        return 0
    except Exception as exc:
        # Windows consoles that can't provide a screen buffer (MinTTY etc.)
        if "console" in str(exc).lower() or type(exc).__name__ == "NoConsoleScreenBufferError":
            print(_fallback_notice())
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
