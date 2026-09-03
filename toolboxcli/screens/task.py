"""Task Execution Panel: prompts for inputs, then runs the tool with a
clean animated loading state, a progress bar, and a log panel that only
appears if the tool actually has something worth showing."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, LoadingIndicator, OptionList, ProgressBar, RichLog, Static
from textual.widgets.option_list import Option

from ..core import platform as plat
from ..core import theme
from ..core.runners import RUNNERS, Done, Log, Progress, Step
from ..data.catalog import find_tool

INPUT_ICONS = {
    "text": "✎",
    "password": "⊙",
    "choice": "▣",
    "file": "▤",
    "files": "▤",
    "folder": "▥",
}


class TaskScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
    ]

    def __init__(self, tool_key: str) -> None:
        super().__init__()
        self.tool = find_tool(tool_key)
        self.tool_key = tool_key
        self.values: dict = {}
        self.input_index = 0
        self.finished = False
        self._has_logs = False

    def compose(self) -> ComposeResult:
        icon = theme.tool_icons().get(self.tool_key, "•")
        yield Static(f"▶  {icon}  {self.tool.label}", id="task-title")
        yield Static(self.tool.description, id="task-desc")

        yield Static("", id="prompt-label")
        yield Input(id="prompt-input")
        yield OptionList(id="prompt-choices")

        with Vertical(id="loading-area"):
            yield LoadingIndicator(id="loading-spinner")
            yield Static("", id="loading-step")
        yield ProgressBar(id="task-progress", show_eta=False)
        yield RichLog(id="log-panel", markup=True, wrap=True)
        yield Static("", id="result-banner")

    def on_mount(self) -> None:
        self.query_one("#prompt-choices", OptionList).display = False
        self.query_one("#loading-area", Vertical).display = False
        self.query_one("#task-progress", ProgressBar).display = False
        self.query_one("#log-panel", RichLog).display = False
        self.query_one("#result-banner", Static).display = False
        self._ask_next_input()

    # ── Input collection ─────────────────────────────────────────────────

    def _ask_next_input(self) -> None:
        specs = self.tool.inputs
        label = self.query_one("#prompt-label", Static)
        field = self.query_one("#prompt-input", Input)
        choices = self.query_one("#prompt-choices", OptionList)

        while self.input_index < len(specs):
            spec = specs[self.input_index]

            # File/folder inputs use the native OS picker. Textual's suspend()
            # releases the terminal so the tkinter dialog takes focus properly
            # instead of opening behind the TUI.
            if spec.kind in ("file", "files", "folder"):
                def _pick():
                    if spec.kind == "folder":
                        picked = plat.pick_folder(spec.prompt)
                        return str(picked) if picked else ""
                    paths = plat.pick_files(
                        spec.prompt,
                        filetypes=spec.filetypes,
                        multiple=(spec.kind == "files"),
                    )
                    if spec.kind == "files":
                        return [str(p) for p in paths]
                    return str(paths[0]) if paths else ""

                try:
                    # suspend() hands the terminal back so the native dialog
                    # takes focus rather than opening behind the TUI. It isn't
                    # available in every context (headless tests, some hosts),
                    # so fall back to calling the picker inline.
                    try:
                        with self.app.suspend():
                            value = _pick()
                    except Exception:
                        value = _pick()
                except Exception as exc:
                    self._fail(str(exc))
                    return

                if not value:
                    # Cancelled the picker -> abandon the task, return to grid.
                    self.app.pop_screen()
                    return

                self.values[spec.name] = value
                self.input_index += 1
                continue

            icon = INPUT_ICONS.get(spec.kind, "▸")

            if spec.kind == "choice":
                field.display = False
                choices.display = True
                label.update(f"[bold {theme.ACCENT}]{icon}  {spec.prompt}[/]")
                label.display = True
                choices.clear_options()
                choices.add_options([Option(c, id=c) for c in spec.choices])
                choices.focus()
                choices.highlighted = 0
                return

            # Plain text-ish input: show the prompt and wait for Enter.
            field.display = True
            choices.display = False
            label.update(f"[bold {theme.ACCENT}]{icon}  {spec.prompt}[/]")
            field.value = spec.default
            field.password = (spec.kind == "password")
            field.display = True
            label.display = True
            field.focus()
            return

        self._start_run()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        specs = self.tool.inputs
        if self.input_index >= len(specs):
            return
        spec = specs[self.input_index]
        raw = event.value.strip()

        self.values[spec.name] = raw or spec.default
        self.input_index += 1
        event.input.value = ""
        self._ask_next_input()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        specs = self.tool.inputs
        if self.input_index >= len(specs):
            return
        spec = specs[self.input_index]
        if spec.kind != "choice":
            return
        self.values[spec.name] = str(event.option.id)
        self.input_index += 1
        self._ask_next_input()

    # ── Execution ────────────────────────────────────────────────────────

    def _start_run(self) -> None:
        self.query_one("#prompt-label", Static).display = False
        self.query_one("#prompt-input", Input).display = False
        self.query_one("#prompt-choices", OptionList).display = False
        self.query_one("#loading-area", Vertical).display = True
        self.query_one("#task-progress", ProgressBar).display = True
        self.query_one("#loading-step", Static).update("Starting...")
        self.run_task()

    def _set_step(self, text: str) -> None:
        badge = theme.badge("Working", theme.ACCENT)
        self.query_one("#loading-step", Static).update(f"{badge}  [bold {theme.ACCENT}]{text}[/]")

    @work(thread=True)
    def run_task(self) -> None:
        """Run the tool in a worker thread so the UI keeps redrawing.

        Runners are plain generators yielding Step/Progress/Log/Done events;
        each event is marshalled back onto the UI thread via call_from_thread.
        """
        runner = RUNNERS[self.tool_key]
        try:
            for event in runner(**self.values):
                if isinstance(event, Step):
                    self.app.call_from_thread(self._set_step, event.text)
                elif isinstance(event, Progress):
                    self.app.call_from_thread(self._set_progress, event.done, event.total)
                elif isinstance(event, Log):
                    self.app.call_from_thread(self._write_log, event.text)
                elif isinstance(event, Done):
                    self.app.call_from_thread(self._succeed, event.summary, event.folder)
        except Exception as exc:
            self.app.call_from_thread(self._fail, str(exc))

    def _set_progress(self, done: int, total: int) -> None:
        bar = self.query_one("#task-progress", ProgressBar)
        bar.total = max(total, 1)
        bar.progress = done

    def _write_log(self, text: str) -> None:
        # The log panel stays hidden entirely for tools that never emit a Log
        # event (most of them) — only tools with real reviewable output
        # (e.g. a list of duplicates found) reveal it, on the first line.
        if not self._has_logs:
            self._has_logs = True
            self.query_one("#log-panel", RichLog).display = True
        self.query_one("#log-panel", RichLog).write(text)

    def _finish_common(self) -> None:
        self.query_one("#loading-area", Vertical).display = False
        self.finished = True

    def _succeed(self, summary: str, folder=None) -> None:
        self._finish_common()
        banner = self.query_one("#result-banner", Static)
        banner.remove_class("-fail")
        banner.add_class("-ok")
        badge = theme.badge("Done", theme.OK)
        banner.update(
            f"{badge}  [bold {theme.OK}]{summary}[/]\n\n"
            f"[{theme.MUTED}]Press[/] {theme.key_hint('Esc', 'to go back to the dashboard')}"
        )
        banner.display = True
        if folder:
            plat.open_in_file_manager(Path(folder))

    def _fail(self, message: str) -> None:
        self._finish_common()
        banner = self.query_one("#result-banner", Static)
        banner.remove_class("-ok")
        banner.add_class("-fail")
        badge = theme.badge("Failed", theme.BAD)
        banner.update(
            f"{badge}  [bold {theme.BAD}]{message}[/]\n\n"
            f"[{theme.MUTED}]Press[/] {theme.key_hint('Esc', 'to go back to the dashboard')}"
        )
        banner.display = True

    def action_go_back(self) -> None:
        self.app.pop_screen()
