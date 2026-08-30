"""Task Execution Panel: prompts for inputs, then runs the tool with a
live step list, progress bar, and scrollable log."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Input, ProgressBar, RichLog, Static

from ..core import platform as plat
from ..core import theme
from ..core.runners import RUNNERS, Done, Log, Progress, Step
from ..data.catalog import find_tool


class StepLine(Static):
    """One line in the multi-step progress list, with a status badge."""

    def __init__(self, text: str) -> None:
        super().__init__("", classes="step-pending")
        self.step_text = text
        self.state = "pending"
        self._frame = 0

    def render(self) -> str:
        if self.state == "running":
            frames = theme.spinner_frames()
            badge = frames[self._frame % len(frames)]
        elif self.state == "done":
            badge = theme.BADGE_OK
        elif self.state == "failed":
            badge = theme.BADGE_FAIL
        else:
            badge = theme.BADGE_RUNNING
        return f"{badge}  {self.step_text}"

    def set_state(self, state: str) -> None:
        self.state = state
        self.remove_class("step-pending", "step-running", "step-done", "step-failed")
        self.add_class(f"step-{state}")
        self.refresh()

    def tick(self) -> None:
        if self.state == "running":
            self._frame += 1
            self.refresh()


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
        self._steps: list[StepLine] = []

    def compose(self) -> ComposeResult:
        yield Static(f"▶  {self.tool.label}", id="task-title")
        yield Static(self.tool.description, id="task-desc")
        yield Static("", id="prompt-label")
        yield Input(id="prompt-input")
        with VerticalScroll(id="step-list"):
            pass
        yield ProgressBar(id="task-progress", show_eta=False)
        yield RichLog(id="log-panel", markup=True, wrap=True)
        yield Static("", id="result-banner")

    def on_mount(self) -> None:
        self.query_one("#task-progress", ProgressBar).display = False
        self.query_one("#result-banner", Static).display = False
        self._ask_next_input()

    # ── Input collection ─────────────────────────────────────────────────

    def _ask_next_input(self) -> None:
        specs = self.tool.inputs
        label = self.query_one("#prompt-label", Static)
        field = self.query_one("#prompt-input", Input)

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

            # Text-ish input: show the prompt and wait for Enter.
            hint = ""
            if spec.kind == "choice":
                options = "  /  ".join(f"[{i+1}] {c}" for i, c in enumerate(spec.choices))
                hint = f"\n{options}"
            label.update(f"{spec.prompt}{hint}")
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

        if spec.kind == "choice":
            # Accept either the number or free text matching a choice.
            if raw.isdigit() and 1 <= int(raw) <= len(spec.choices):
                raw = spec.choices[int(raw) - 1]
            elif not raw:
                raw = spec.choices[0]

        self.values[spec.name] = raw or spec.default
        self.input_index += 1
        event.input.value = ""
        self._ask_next_input()

    # ── Execution ────────────────────────────────────────────────────────

    def _start_run(self) -> None:
        self.query_one("#prompt-label", Static).display = False
        self.query_one("#prompt-input", Input).display = False
        self.query_one("#task-progress", ProgressBar).display = True
        self.set_interval(0.1, self._tick_spinners)
        self.run_task()

    def _tick_spinners(self) -> None:
        for step in self._steps:
            step.tick()

    def _add_step(self, text: str) -> StepLine:
        for step in self._steps:
            if step.state == "running":
                step.set_state("done")
        line = StepLine(text)
        self.query_one("#step-list", VerticalScroll).mount(line)
        line.set_state("running")
        self._steps.append(line)
        return line

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
                    self.app.call_from_thread(self._add_step, event.text)
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
        self.query_one("#log-panel", RichLog).write(text)

    def _succeed(self, summary: str, folder=None) -> None:
        for step in self._steps:
            if step.state == "running":
                step.set_state("done")
        banner = self.query_one("#result-banner", Static)
        banner.remove_class("-fail")
        banner.add_class("-ok")
        banner.update(f"{theme.BADGE_OK}  {summary}\n\n[Esc] Back to dashboard")
        banner.display = True
        self.finished = True
        if folder:
            plat.open_in_file_manager(Path(folder))

    def _fail(self, message: str) -> None:
        for step in self._steps:
            if step.state == "running":
                step.set_state("failed")
        banner = self.query_one("#result-banner", Static)
        banner.remove_class("-ok")
        banner.add_class("-fail")
        banner.update(f"{theme.BADGE_FAIL}  {message}\n\n[Esc] Back to dashboard")
        banner.display = True
        self.finished = True

    def action_go_back(self) -> None:
        self.app.pop_screen()
