# 🧰 RAHUL'S TOOLBOX

## Windows desktop application — v3.3.0

The project now includes a native **Qt / PySide6 Windows desktop application**
with a monochrome dashboard, custom icons, searchable tool cards, favorites, recent
activity, background processing, native file dialogs and configurable output.
The original terminal application is also available (documented below).

### Monochrome workspace, themes and file suggestions

### Fill & Sign workspace — v3.3.0

**Fill PDF Forms** and **Sign PDF** open the new maximizable page workspace.
Every tool dialog is resizable and sized to the available screen; long forms
use scrolling controls and keep the final action visible. Click anywhere on
a tool card to open it. Favorite stars update in place without opening a tool
or resetting the dashboard's scroll position.

* **Interactive PDFs:** edit text (including multiline fields), choose from
  dropdowns, tick checkboxes, and select radio buttons directly on the page.
  Required and read-only fields are identified. Values remain PDF fields
  unless **Flatten interactive fields when saving** is selected.
* **Flat and scanned forms:** detect writable blanks and type directly on the
  page. Adjacent character boxes become one field, with one character per cell,
  capacity limits, date paste support and Tab/Shift+Tab navigation. Printed
  blanks export as editable PDF fields. Manual annotation tools are collapsed
  by default and remain available for missed blanks.
* **Signature placement:** create a cursive name or import a PNG, click to place
  it, then drag the body to move it or a corner handle to resize it. Smaller
  and Larger buttons are also available. Clicking a detected signature area
  fits the signature into that box. Multiple pages can contain signatures.
* **Document view:** Fit page, Fit width, zoom buttons, Ctrl+wheel zoom, page
  navigation, Focus page to hide the panels, and F11 for full-screen viewing.
* **Field detection:** native AcroForm fields are identified exactly. Printed
  boxes, lines and signature labels are suggested using document geometry.
  **Detect fields on this page** can use bundled local OCR for scanned pages;
  image-only first pages start local detection automatically. Form contents
  never need to leave the computer. Inspect all suggestions before saving:
  recognition depends on scan quality, language and form layout.

Saving always creates a new PDF. Embedded scripts and dynamic XFA forms are
not executed or supported as interactive forms; manual overlay filling is
available when the page can be rendered. Visual signatures do not create or
validate certificate-based digital signatures, and edits can invalidate an
existing certificate signature. OCR is assisted detection, not a guarantee
that every field or signature area will be recognized.

Version 3.3.0 aligns card titles, descriptions and actions in shared slots;
uses consistent navigation and upload button sizes; keeps the sidebar logo
fully visible; and switches from three card columns to two in narrow windows.
Icons are rendered at double resolution for Windows display scaling. The
tool grid includes edge padding so the final row is fully visible at the end
of scrolling. Alignment checks cover both themes and multiple window sizes.

The desktop UI uses black, white and neutral shades throughout. In **Settings →
Appearance**, choose **Dark**, **Light**, or **Auto · follow Windows**. Changes
apply immediately, are saved between launches, and Auto reacts to Windows app
theme changes while the application is running.

Preferences are generated at `%APPDATA%\RahulsToolbox\settings\preferences.json`.
The Settings screen includes an **Open settings folder** button. This folder
stores the theme, output location, favorites and local activity; preferences
from the original desktop registry settings are migrated on first launch.

Use **Choose files**, **Choose folder**, or drag local files onto the dashboard.
The dashboard suggests compatible tools: a PDF exposes PDF actions, multiple
PDFs offer merging, JPG/PNG images offer compression and PDF creation, and a
folder offers duplicate cleanup and image renaming. Opening a suggested tool
preloads the selection. Mixed or unsupported selections receive guidance
without starting a conversion. Selecting a file never sends it to a server.

The original monochrome T/tray logo is included as an editable SVG and as
high-resolution PNG/ICO assets; installer artwork uses the same identity.

### Install on Windows 10 / 11 (64-bit)

Download **RahulsToolbox-3.3.0-Setup.exe** from the
[v3.3.0 release](https://github.com/rahulswargam/ToolboxCLI/releases/tag/v3.3.0)
and follow the setup wizard.
The installer bundles Python, Qt and the PDF/image libraries. No separate
Python, pip, Office, Adobe Reader or network connection is needed at runtime.
It installs for the current user, adds a Start menu shortcut, offers a desktop
shortcut, and includes an uninstaller. This development build is unsigned.

### Desktop tools

* Images: compression, images to PDF, rename by date.
* PDFs: fill forms, PDF to JPG, PDF to Word, unlock, lock, compress, merge, sign,
  rotate, organize and remove pages.
* Files: the existing duplicate report plus content-verified duplicate removal.

**Duplicate removal:** choose a folder; subfolders are optional. The scan
compares SHA-256 content hashes across all file types, including differently
named copies. Review the duplicate and retained original side by side, select
copies, and confirm moving them to the Windows Recycle Bin. Contents are
checked again before removal. Matching names alone do not prove duplication.
Symbolic links and directory junctions are not traversed.

**Merge:** add PDFs, drag documents into the required order, then save a new PDF.
**Organize:** drag page thumbnails to change page order.
**Rotate / remove:** select thumbnails; hold Ctrl for multiple pages.
**Sign:** open a PDF, choose a page, import a PNG or create a cursive-style name,
adjust the width and drag the signature into position. This is a visual
signature, not a certificate-based digital signature.
**Compress:** optimizes PDF structure and recompresses embedded images. It
reports when the requested target cannot be reached; output never grows.

PDF edits save new files and preserve originals. Rename by date renames
original images in place and requests confirmation. Password-protected PDFs
should be unlocked first. PDF-to-Word conversion is not OCR and complex layouts
may need adjustment. New forms, bookmarks and digital signatures should be
checked after page edits; this app does not validate digital signatures.

### Run from source

Use Python 3.12 on Windows for the tested build:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-desktop.lock.txt
.\.venv\Scripts\python -m toolboxdesktop
```

### Build the installer

Install Inno Setup 6, then run:

```powershell
winget install --id JRSoftware.InnoSetup --exact
powershell -ExecutionPolicy Bypass -File packaging/build.ps1
```

Outputs: `dist/RahulsToolbox/RahulsToolbox.exe`,
`release/RahulsToolbox-3.3.0-Setup.exe` and the matching source ZIP.
Keep the entire portable `dist/RahulsToolbox` folder together.
Build scripts use PyInstaller and Inno Setup; dependency versions are recorded
in `requirements-desktop.lock.txt`. Third-party notices and collected license
texts are included in the bundle; see `THIRD_PARTY_NOTICES.md`.

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

Desktop source is in `toolboxdesktop/`; shared terminal runners are reused
for the original tools. `packaging/` contains reproducible build scripts.

### Branches and releases

`dev` is the integration branch. Tested releases are promoted to `prod` and
tagged with their version, such as `v3.3.0`. GitHub Releases carry the Windows
installer, matching source archive and SHA-256 checksums. Generated builds,
virtual environments, local settings, downloaded QA documents and test caches
are excluded from Git.

See [the v3.3.0 release notes](docs/releases/v3.3.0.md) and
[form-filling research](docs/form-filling-research.md).

---

## Original terminal application (v2)

**A modern terminal dashboard for everyday file work.**

Not a menu. A *dashboard* — categories laid out as horizontal rows of
button-cards, driven entirely by the arrow keys, with a focused task panel
that shows live spinners, progress bars, and streaming logs while your job
runs. Cross-platform: **Windows and macOS**, same experience on both.

```
╔══════════════════════════════════════════════════════════════════════════╗
║    ___      _        _ _      _____         _ _                          ║
║   | _ \__ _| |_ _  _| ( )___ |_   _|__  ___| | |__  _____ __             ║
║   |   / _` | ' \ || | |/(_-<   | |/ _ \/ _ \ | '_ \/ _ \ \ /             ║
║   |_|_\__,_|_||_\_,_|_| /__/   |_|\___/\___/_|_.__/\___/_\_\             ║
║                                                                            ║
║                     Developer & Utility Toolkit                          ║
║                                                                            ║
║                      Created by Rahul Swargam                            ║
╚══════════════════════════════════════════════════════════════════════════╝
  [↑ ↓ ← →] Navigate    [Enter] Select    [Esc] Quit

◆  IMAGE TOOLS
┌──────────────────────┐ ╭─────────────────────────────╮ ╭───────────────────────────────────╮
│ » ▽ Compress Images  │ │   ⇒ Images to PDF (JPG/PNG) │ │   ↻ Rename Image File Names by Date│
└──────────────────────┘ ╰─────────────────────────────╯ ╰───────────────────────────────────╯
  (shown with a cyan outline in the real app — Markdown can't render colour)

■  PDF TOOLS
╭────────────────╮ ╭─────────────────╮ ╭────────────────╮ ╭───────────────╮ ╭──────────────────╮
│  ▥ PDF to JPG  │ │  ▤ PDF to Word  │ │  ⊙ Unlock PDF  │ │  ⊘ Lock PDF   │ │  ▣ Resize PDF     │
╰────────────────╯ ╰─────────────────╯ ╰────────────────╯ ╰───────────────╯ ╰──────────────────╯

                              MIT License  •  v2.0.0
```

*(the real banner is generated live by `pyfiglet`, split two-tone across
"RAHUL'S" and "TOOLBOX" — it only appears when your terminal is wide enough,
falling back to a plain title otherwise. Directory and tool count aren't
shown anywhere; license and version appear once, at the very bottom.)*

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

**Live task panel.** A pulsing loading indicator next to a filled `WORKING`
pill and the current step, a `[████████░░] 80%` progress bar, and a filled
`DONE`/`FAILED` pill on the result — clean by default. A log panel only
appears for tools that actually have something worth reviewing (like a list
of duplicates found); tools with nothing to show don't clutter the screen
with one. Results land in a clearly named Desktop folder that opens
automatically when the job finishes.

---

## 🎨 Theme

JobSprint house style — violet brand accent, cyan interaction accent, plain
dark terminal surfaces with no filled colour panels. Rounded borders
everywhere except the title banner, which uses a double-line violet border.
Selection is shown with a cyan border and a `»` indicator, never a solid
colour fill. Defined once in `toolboxcli/core/theme.py` and
`toolboxcli/theme.tcss`:

| Token | Colour | Used for |
|---|---|---|
| Charcoal | `#121212` | background |
| Brand | `#d787ff` | headings, banner border, author credit |
| Accent | `#00d7ff` | cursor / active selection, prompts, hint keys |
| Muted | `grey54` | help text, footers, inactive items |
| OK | `#5fd75f` | success / completion |
| Warn | `#ffaf5f` | warnings |
| Bad | `#ff5f5f` | failures |

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
    └── cards.py           # ToolCard, AppHeader, HintBar, FooterCredit
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
