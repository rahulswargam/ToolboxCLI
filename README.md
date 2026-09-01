# 🧰 RAHUL'S TOOLBOX

**A modern terminal dashboard for everyday file work.**

Not a menu. A *dashboard* — categories laid out as horizontal rows of
button-cards, driven entirely by the arrow keys, with a focused task panel
that shows live spinners, progress bars, and streaming logs while your job
runs. Cross-platform: **Windows and macOS**, same experience on both.

```
╔══════════════════════════════════════════════════════════════════════════╗
   ___      _        _ _      _____         _ _
  | _ \__ _| |_ _  _| ( )___ |_   _|__  ___| | |__  _____ __
  |   / _` | ' \ || | |/(_-<   | |/ _ \/ _ \ | '_ \/ _ \ \ /
  |_|_\__,_|_||_\_,_|_| /__/   |_|\___/\___/_|_.__/\___/_\_\
╚══════════════════════════════════════════════════════════════════════════╝
  [↑ ↓ ← →] Navigate    [Enter] Select    [Esc] Quit
  DIR ~/Projects/Codes   |   9 tools   |   v2.0.0

◆  IMAGE TOOLS
╔══════════════════════╗ ╭─────────────────────────────╮ ╭───────────────────────────────────╮
║ ▶ ▽ Compress Images  ║ │   ⇒ Images to PDF (JPG/PNG) │ │   ↻ Rename Image File Names by Date│
╚══════════════════════╝ ╰─────────────────────────────╯ ╰───────────────────────────────────╯

■  PDF TOOLS
╭────────────────╮ ╭─────────────────╮ ╭────────────────╮ ╭───────────────╮ ╭──────────────────╮
│  ▥ PDF to JPG  │ │  ▤ PDF to Word  │ │  ⊙ Unlock PDF  │ │  ⊘ Lock PDF   │ │  ▣ Resize PDF     │
╰────────────────╯ ╰─────────────────╯ ╰────────────────╯ ╰───────────────╯ ╰──────────────────╯
```

*(the real banner is generated live by `pyfiglet` — it only appears when your
terminal is wide enough, falling back to a plain title otherwise)*

---

## ✨ Features

| Category | Tools |
|---|---|
| ◆ **Image Tools** | ▽ Compress Images · ⇒ Images to PDF (JPG/PNG) · ↻ Rename Image File Names by Date |
| ■ **PDF Tools** | ▥ PDF to JPG · ▤ PDF to Word · ⊙ Unlock PDF · ⊘ Lock PDF · ▣ Resize PDF |
| ▶ **File Management** | ⧉ Find Duplicates (Files or Photos) |

**True 2D navigation.** `↑`/`↓` jump between category rows, `←`/`→` cycle
through the tools in a row (wrapping at both ends). Moving from a wide row
onto a narrow one clamps to the nearest existing card, so the cursor can
never land on nothing.

**Native file pickers.** Any tool that needs a file or folder opens your
real OS dialog — Explorer on Windows, Finder on macOS — rather than making
you type paths.

**Arrow keys everywhere it makes sense.** Multiple-choice prompts (like
Images to PDF's "combine into one, or one each?") are a real arrow-navigable
list, not a number you type. Free-text fields — a target size, a password —
are still typed, because there's nothing to navigate between.

**Live task panel.** A pulsing loading indicator and the current step,
a `[████████░░] 80%` progress bar, and `✔`/`✖` result badges — clean by
default. A log panel only appears for tools that actually have something
worth reviewing (like a list of duplicates found); tools with nothing to
show don't clutter the screen with one. Results land in a clearly named
Desktop folder that opens automatically when the job finishes.

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
ASCII skin automatically (`+--+`, `>`, `OK`/`X`) — the figlet banner and every
tool icon fall back too. Force it with `TOOLBOX_ASCII=1`, or disable colour
with `NO_COLOR=1`. Running without a real TTY prints a readable text summary
instead of crashing.

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

One thing is **not** a pip package: `tkinter` powers the native file/folder
pickers and ships with the official python.org installer on both platforms.
Only Homebrew Python on macOS needs it added separately:

```bash
brew install python-tk
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

30 tests covering the navigation model (exhaustively — every move from every
position), catalog/runner integrity, real file round-trips for the image and
PDF tools (including a genuine Resize PDF shrink-and-reopen check), and the
live UI driven headlessly through Textual's `Pilot` (simulated key presses
asserting the right card highlights and the right screen opens).

---

## ⚠️ Behaviour notes

**Find Duplicates reports instead of deleting.** It lists what it found and
leaves removal to you — a scan bug that deletes the wrong file is
unrecoverable, and the report costs one extra step.

**Resize PDF recompresses images, not pages.** It finds every embedded image
in the PDF and re-encodes it at progressively lower JPEG quality (and, if
needed, smaller pixel dimensions) until the file fits the target — text and
vector content are left untouched, so the result stays searchable and crisp.
A PDF with no embedded images (pure text/vector) is already about as small as
it can get, and the tool says so rather than pretending to help.

**Downloaders and Video Tools were removed** from this build to keep the
toolkit focused on local file work. The architecture makes them trivial to
bring back — see *Adding a new tool* below.

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
