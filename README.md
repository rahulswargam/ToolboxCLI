# 🧰 RAHUL'S TOOLBOX

**A modern terminal dashboard for everyday file work.**

Not a menu. A *dashboard* — categories laid out as horizontal rows of
button-cards, driven entirely by the arrow keys, with a focused task panel
that shows live spinners, progress bars, and streaming logs while your job
runs. Cross-platform: **Windows and macOS**, same experience on both.

```
╔══════════════════════════════════════════════════════════════════════════╗
                            RAHUL'S TOOLBOX
              [↑↓←→] Navigate   [Enter] Select   [Esc] Quit
 DIR ~/Projects/Codes   |   13 tools   |   v2.0.0
╚══════════════════════════════════════════════════════════════════════════╝

◆  IMAGE TOOLS
╔════════════════════╗ ╭───────────────────────────╮ ╭─────────────────────╮
║ ▶ Compress Images  ║ │   Images to PDF (JPG/PNG) │ │   Rename by Date    │
╚════════════════════╝ ╰───────────────────────────╯ ╰─────────────────────╯

■  PDF TOOLS
╭──────────────╮ ╭───────────────╮ ╭──────────────╮ ╭─────────────╮
│  PDF to JPG  │ │  PDF to Word  │ │  Unlock PDF  │ │  Lock PDF   │
╰──────────────╯ ╰───────────────╯ ╰──────────────╯ ╰─────────────╯
```

---

## ✨ Features

| Category | Tools |
|---|---|
| ◆ **Image Tools** | Compress Images · Images to PDF (JPG/PNG) · Rename Image File Names by Date |
| ■ **PDF Tools** | PDF to JPG · PDF to Word · Unlock PDF · Lock PDF |
| ▶ **File Management** | Find Duplicates (Files or Photos) |
| ⬎ **Downloaders** | YouTube Video · YouTube to MP3 · Instagram Post/Reel · Pinterest Post |
| ▶ **Video Tools** | Video Trimmer |

**True 2D navigation.** `↑`/`↓` jump between category rows, `←`/`→` cycle
through the tools in a row (wrapping at both ends). Moving from a wide row
onto a narrow one clamps to the nearest existing card, so the cursor can
never land on nothing.

**Native file pickers.** Any tool that needs a file or folder opens your
real OS dialog — Explorer on Windows, Finder on macOS — rather than making
you type paths.

**Live task panel.** Each run shows a stepped checklist with `⠋` spinners,
a `[████████░░] 80%` progress bar, `✔`/`✖` status badges, and a scrollable
log. Results land in a clearly named Desktop folder that opens automatically
when the job finishes.

---

## 🎨 Theme

Tokyo-Night-inspired, defined once in `toolboxcli/core/theme.py` and
`toolboxcli/theme.tcss`:

| Token | Colour | Used for |
|---|---|---|
| Charcoal | `#1A1B26` | background |
| Cyan | `#7AA2F7` | cursor / active selection |
| Amber | `#FF9E64` | section headers |
| Magenta | `#BB9AF7` | secondary accents, prompts |
| Emerald | `#9ECE6A` | success / completion |
| Red | `#F7768E` | failures |

**Graceful fallback.** Terminals that can't do UTF-8 box characters get an
ASCII skin automatically (`+--+`, `>`, `OK`/`X`). Force it with
`TOOLBOX_ASCII=1`, or disable colour with `NO_COLOR=1`. Running without a
real TTY prints a readable text summary instead of crashing.

---

## 🚀 Quick start

### 1. Requirements

- **Python 3.10+**
- **A real terminal** — Windows Terminal, PowerShell, or Command Prompt on
  Windows; Terminal.app or iTerm2 on macOS. (Git Bash / MinTTY can't host a
  full-screen TUI.)

### 2. Install

```bash
pip install -r requirements.txt
```

Two things are **not** pip packages and only matter for specific tools:

```bash
# ffmpeg — needed by Video Trimmer and YouTube to MP3
winget install Gyan.FFmpeg     # Windows
brew install ffmpeg            # macOS

# tkinter — powers the file pickers. Bundled with python.org installers.
brew install python-tk         # macOS, only if you use Homebrew Python
```

### 3. Run

```bash
python toolbox.py
```

or as a module:

```bash
python -m toolboxcli
```

---

## 🏗️ Architecture

Deliberately modular — the layout engine, navigation model, data catalog,
and task runners are all separate and independently testable.

```
toolboxcli/
├── app.py                 # App entry point, screen routing, TTY fallback
├── theme.tcss             # All visual styling (Textual CSS)
│
├── core/
│   ├── theme.py           # Palette tokens + terminal capability detection
│   ├── navigation.py      # 2D grid movement — pure logic, zero Textual imports
│   ├── platform.py        # Native pickers, Desktop paths, dependency checks
│   └── runners.py         # Task runners as event-emitting generators
│
├── data/
│   └── catalog.py         # THE source of truth: categories, tools, inputs
│
├── screens/
│   ├── dashboard.py       # Category rows of tool cards
│   └── task.py            # Task Execution Panel
│
└── widgets/
    └── cards.py           # ToolCard, AppHeader, StatusBar, FooterCredit
```

**Two design decisions worth knowing:**

*Navigation is framework-free.* `core/navigation.py` imports nothing from
Textual — it's pure index math over ragged rows. That's why every possible
move from every possible position can be verified exhaustively in
milliseconds, without a terminal.

*Runners are generators, not UI code.* Each tool `yield`s
`Step` / `Progress` / `Log` / `Done` events. The UI decides how to render
them; the runner just describes what's happening. So every tool is testable
headlessly, and the same runner could drive a web UI or a plain CLI unchanged.

---

## 🧩 Adding a new tool

Three steps, no UI code required — the grid builds itself from the catalog.

**1.** Write a runner in `core/runners.py`:

```python
def run_my_tool(file, **_):
    yield Step("Doing the thing")
    yield Progress(0, 1)
    ...
    yield Progress(1, 1)
    yield Done("All finished", output_folder("My Tool"))
```

**2.** Register it in the `RUNNERS` dict at the bottom of the same file:

```python
RUNNERS = { ..., "my_tool": run_my_tool }
```

**3.** Add it to `data/catalog.py` under whichever category fits:

```python
Tool(
    "my_tool", "My New Tool",
    "One-line description shown in the task panel.",
    (InputSpec("file", "Pick a file", "file",
               filetypes=(("Text", "*.txt"),)),),
)
```

That's it. The card appears, navigation adjusts to the new row width, and the
task screen builds its prompts from `InputSpec`. A test asserts the catalog
and `RUNNERS` never drift apart, so a missing runner fails CI rather than
crashing at runtime.

`InputSpec` kinds: `text`, `file`, `files`, `folder`, `password`, `choice`.

---

## 🧪 Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

24 tests covering the navigation model (exhaustively — every move from every
position), catalog/runner integrity, real file round-trips for the image and
PDF tools, and the live UI driven headlessly through Textual's `Pilot`
(simulated key presses asserting the right card highlights and the right
screen opens).

---

## ⚠️ One behaviour change

**Find Duplicates now reports instead of deleting.** The previous version
offered to send duplicates to the Recycle Bin. It now lists what it found and
leaves removal to you — a scan bug that deletes the wrong file is
unrecoverable, and the report costs one extra step.

---

## 🌿 Branches

- **`master`** — stable, working builds.
- **`dev`** — active development; merges into `master` once tried out.

---

## 📜 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Created & Built by Rahul Swargam** ❤️

</div>
