"""The tool catalog: the single source of truth for what appears in the UI.

Adding a tool means adding one Tool(...) entry here and one runner function
in core/runners.py — the grid, navigation, and task screens all build
themselves from this structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Tool:
    """One action card in the grid."""
    key: str                      # stable id, used to look up the runner
    label: str                    # shown on the card
    description: str              # shown in the task panel subtitle
    inputs: tuple = ()            # InputSpec entries the task screen prompts for


@dataclass(frozen=True)
class InputSpec:
    """One prompt shown before a tool runs."""
    name: str
    prompt: str
    kind: str = "text"            # text | file | files | folder | password | choice
    default: str = ""
    choices: tuple = ()
    filetypes: tuple = ()


@dataclass(frozen=True)
class Category:
    name: str
    tools: tuple = field(default_factory=tuple)


CATALOG: tuple[Category, ...] = (
    Category("Image Tools", (
        Tool(
            "compress_images", "Compress Images",
            "Shrink JPG/PNG files under a target size, keeping quality as high as possible.",
            (
                InputSpec("files", "Select images to compress", "files",
                          filetypes=(("Images", "*.jpg *.jpeg *.png *.webp *.bmp"),)),
                InputSpec("target_kb", "Target size per image (KB)", "text", default="100"),
            ),
        ),
        Tool(
            "images_to_pdf", "Images to PDF (JPG/PNG)",
            "Combine images into a single PDF, or export one PDF per image.",
            (
                InputSpec("files", "Select images to convert", "files",
                          filetypes=(("Images", "*.jpg *.jpeg *.png"),)),
                InputSpec("mode", "How should they be combined?", "choice",
                          choices=("Combine into one PDF", "One PDF per image")),
            ),
        ),
        Tool(
            "rename_by_date", "Rename Image File Names by Date",
            "Sort images by date taken and rename them IMG_001, IMG_002, ...",
            (InputSpec("folder", "Select the folder containing images", "folder"),),
        ),
    )),
    Category("PDF Tools", (
        Tool(
            "pdf_to_jpg", "PDF to JPG",
            "Render every page of a PDF as a JPG image.",
            (
                InputSpec("file", "Select a PDF to convert", "file",
                          filetypes=(("PDF files", "*.pdf"),)),
                InputSpec("dpi", "Render quality (DPI)", "text", default="300"),
            ),
        ),
        Tool(
            "pdf_to_word", "PDF to Word",
            "Convert a PDF into an editable .docx document.",
            (InputSpec("file", "Select a PDF to convert", "file",
                       filetypes=(("PDF files", "*.pdf"),)),),
        ),
        Tool(
            "unlock_pdf", "Unlock PDF",
            "Remove password protection from a PDF you can already open.",
            (
                InputSpec("file", "Select the locked PDF", "file",
                          filetypes=(("PDF files", "*.pdf"),)),
                InputSpec("password", "PDF password (leave blank to try empty)", "password"),
            ),
        ),
        Tool(
            "lock_pdf", "Lock PDF",
            "Add password protection to a PDF.",
            (
                InputSpec("file", "Select the PDF to lock", "file",
                          filetypes=(("PDF files", "*.pdf"),)),
                InputSpec("password", "Password to set", "password"),
            ),
        ),
    )),
    Category("File Management", (
        Tool(
            "find_duplicates", "Find Duplicates (Files or Photos)",
            "Scan a folder for duplicates by name/size or by content hash.",
            (
                InputSpec("folder", "Select the folder to scan", "folder"),
                InputSpec("mode", "Detection method", "choice",
                          choices=("Quick - name, size & extension",
                                   "Thorough - content hash + Live Photo pairing")),
            ),
        ),
    )),
    Category("Downloaders", (
        Tool(
            "youtube_video", "YouTube Video Downloader",
            "Download a YouTube video or playlist as MP4.",
            (
                InputSpec("url", "YouTube video or playlist URL", "text"),
                InputSpec("folder", "Where should it be saved?", "folder"),
            ),
        ),
        Tool(
            "youtube_mp3", "YouTube to MP3",
            "Extract audio from YouTube as a 192kbps MP3. Requires ffmpeg.",
            (
                InputSpec("url", "YouTube video or playlist URL", "text"),
                InputSpec("folder", "Where should it be saved?", "folder"),
            ),
        ),
        Tool(
            "instagram", "Instagram Post or Reel Downloader",
            "Download a public Instagram post or reel.",
            (
                InputSpec("url", "Instagram post/reel URL or username", "text"),
                InputSpec("folder", "Where should it be saved?", "folder"),
            ),
        ),
        Tool(
            "pinterest", "Pinterest Post Downloader",
            "Download a Pinterest pin or board.",
            (
                InputSpec("url", "Pinterest pin or board URL", "text"),
                InputSpec("folder", "Where should it be saved?", "folder"),
            ),
        ),
    )),
    Category("Video Tools", (
        Tool(
            "video_trim", "Video Trimmer",
            "Cut a clip out of a video without re-encoding. Requires ffmpeg.",
            (
                InputSpec("file", "Select the video to trim", "file",
                          filetypes=(("Videos", "*.mp4 *.mov *.mkv *.avi *.m4v"),)),
                InputSpec("start", "Start time (HH:MM:SS)", "text", default="00:00:00"),
                InputSpec("end", "End time (HH:MM:SS)", "text"),
            ),
        ),
    )),
)


def all_tools() -> list[Tool]:
    return [tool for category in CATALOG for tool in category.tools]


def find_tool(key: str) -> Tool | None:
    return next((t for t in all_tools() if t.key == key), None)


TOTAL_TOOLS = len(all_tools())
