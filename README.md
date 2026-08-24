# 🧰 ToolboxCLI

**One command. Fifteen tools. Zero folder-hunting.**

ToolboxCLI is a single-file, arrow-key-driven command line app that bundles a
whole shelf of everyday file utilities — image compression, PDF wrangling,
duplicate hunting, and a few social/media downloaders — behind one clean
full-screen menu. No hunting through a folder of half-remembered `.py`
scripts, no typing paths by hand: every tool that needs a file or folder pops
a native picker, on **Windows and macOS alike**.

```
╔═════════════════════════════════════════════════════════════════════════════╗
║                                                                             ║
║                 ___      _        _ _      _____         _ _                ║
║         | _ \__ _| |_ _  _| ( )___ |_   _|__  ___| | |__  _____ __          ║
║         |   / _` | ' \ || | |/(_-<   | |/ _ \/ _ \ | '_ \/ _ \ \ /          ║
║         |_|_\__,_|_||_\_,_|_| /__/   |_|\___/\___/_|_.__/\___/_\_\          ║
║                                                                             ║
║                   Running on Windows  |  15 tools loaded                    ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝

◆ IMAGE TOOLS          ▪ PDF TOOLS            ↓ DOWNLOADERS
┌─────────────────┐    ┌──────────────┐       ┌───────────────────────┐
│ Compress Images │    │ PDF to JPG   │       │ YouTube Video/MP3     │
└─────────────────┘    └──────────────┘       └───────────────────────┘
```

## ✨ What's inside

| Category | Tools |
|---|---|
| 🖼️ **Image Tools** | Compress Images · Images to PDF (JPG/PNG) · Rename Image File Names by Date |
| 📄 **PDF Tools** | PDF to JPG · PDF to Word · Unlock PDF · Lock PDF |
| 🗂️ **File Management** | Find Duplicates (Files or Photos) — by name/size or by content hash, with Live Photo pairing |
| ⬇️ **Downloaders** | YouTube Video Downloader · YouTube to MP3 · Instagram Post or Reel Downloader · Pinterest Post Downloader |
| 🎬 **Video Tools** | Video Trimmer |
| ⭐ **More** | Download FileForge Toolkit (Windows companion app) · Visit My Website |

Every tool that reads or writes a file opens a native **file/folder picker**
(the same dialog you'd get from Explorer or Finder) instead of asking you to
type a path — pick a file, pick a destination folder, done. Output always
lands in a clearly named folder on your Desktop (`Compressed/`,
`Unlocked PDF/`, `Word Converted/`, etc.).

## 🎮 Controls

The whole menu lives on one screen — no digging through submenus.

| Key | Action |
|---|---|
| `←` `→` `↑` `↓` | Move between tool cards |
| `Enter` | Run the highlighted tool |
| `Esc` / `q` / `Ctrl+C` | Quit |

## 🚀 Getting started

### 1. Requirements

- **Python 3.10+**
- On **Windows**: use the official [python.org](https://www.python.org/downloads/) installer (it bundles Tk, needed for the file pickers).
- On **macOS**: same story. If you installed Python via Homebrew instead, grab Tk separately:
  ```bash
  brew install python-tk
  ```
- **ffmpeg** on your `PATH` — only needed for **Video Trimmer** and **YouTube to MP3** (it's a system binary, not a pip package):
  ```bash
  # Windows
  winget install Gyan.FFmpeg

  # macOS
  brew install ffmpeg
  ```

### 2. Install the Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run it

```bash
python toolbox.py
```

> **Heads up:** the menu is a full-screen interactive app, so it needs a real
> terminal window — Command Prompt, PowerShell, or Windows Terminal on
> Windows; Terminal.app or iTerm2 on macOS. It won't render correctly inside
> Git Bash / MinTTY or a non-interactive shell, and the app will tell you so
> instead of crashing if that happens.

## 🌿 Branches

- **`master`** — stable, working builds only.
- **`dev`** — active development. New tools and fixes land here first and
  get merged into `master` once they've been tried out.

## 🛠️ Built with

[`rich`](https://github.com/Textualize/rich) for the styled output,
[`questionary`](https://github.com/tmbo/questionary) +
[`prompt_toolkit`](https://github.com/prompt-toolkit/python-prompt-toolkit)
for the arrow-key grid navigation, and a small stack of focused libraries
(`Pillow`, `pypdf`, `PyMuPDF`, `pdf2docx`, `yt-dlp`, `instaloader`,
`gallery-dl`) each doing exactly one job well.

## 📜 License

MIT — see [LICENSE](LICENSE).

---

Created & Built by **Rahul Swargam** ❤️
