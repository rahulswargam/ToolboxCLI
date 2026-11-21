"""Task runners.

Every runner is a generator that yields progress events and finishes by
yielding a Done event. Because they're plain generators — not Textual
widgets — each one can be driven and asserted on in a test without a
terminal, and the UI layer stays free to render events however it likes.

Event protocol:
    Step(text)              -> a new step started
    Progress(done, total)   -> advance the bar
    Log(text)               -> a line for the log panel
    Done(summary, folder)   -> success; folder is revealed in Explorer/Finder
"""

from __future__ import annotations

import hashlib
import io
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .platform import is_mac, output_folder, require_module, unique_path


@dataclass
class Step:
    text: str


@dataclass
class Progress:
    done: int
    total: int


@dataclass
class Log:
    text: str


@dataclass
class Done:
    summary: str
    folder: Path | None = None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tiff", ".tif", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".avi", ".m4v", ".mkv"}


# ── Image tools ───────────────────────────────────────────────────────────

def _flatten_to_rgb(img):
    from PIL import Image
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        return background.convert("RGB")
    return img.convert("RGB")


def compress_one(img, target_kb: int) -> tuple[bytes, float]:
    """Shrink an image under target_kb. Quality first, then downscale."""
    from PIL import Image as PILImage
    img = _flatten_to_rgb(img)

    quality = 95
    while quality >= 20:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        size_kb = buf.tell() / 1024
        if size_kb <= target_kb:
            return buf.getvalue(), size_kb
        quality -= 5

    width, height = img.size
    while True:
        width, height = int(width * 0.9), int(height * 0.9)
        img = img.resize((width, height), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        size_kb = buf.tell() / 1024
        if size_kb <= target_kb or width < 100 or height < 100:
            return buf.getvalue(), size_kb


def run_compress_images(files, target_kb="100", **_):
    require_module("PIL", "pillow")
    from PIL import Image

    files = [Path(f) for f in files]
    try:
        target = int(str(target_kb).strip() or 100)
    except ValueError:
        target = 100

    out = output_folder("Compressed")
    yield Step(f"Compressing {len(files)} image(s) to under {target} KB")

    ok = 0
    for i, path in enumerate(files, start=1):
        try:
            before_kb = path.stat().st_size / 1024
            data, after_kb = compress_one(Image.open(path), target)
            dest = unique_path(out / (path.stem + ".jpg"))
            dest.write_bytes(data)
            if after_kb <= target:
                ok += 1
            yield Log(f"{path.name}: {before_kb:.0f} KB -> {after_kb:.0f} KB")
        except Exception as exc:
            yield Log(f"{path.name}: FAILED ({exc})")
        yield Progress(i, len(files))

    yield Done(f"{ok}/{len(files)} compressed under {target} KB", out)


def run_images_to_pdf(files, mode="Combine into one PDF", **_):
    require_module("PIL", "pillow")
    from PIL import Image

    files = [Path(f) for f in files]
    out = output_folder("Images to PDF")
    combine = str(mode).lower().startswith("combine")

    if combine:
        yield Step(f"Combining {len(files)} image(s) into one PDF")
        images = []
        for i, path in enumerate(files, start=1):
            images.append(_flatten_to_rgb(Image.open(path)))
            yield Progress(i, len(files))
        dest = unique_path(out / "Combined.pdf")
        images[0].save(dest, save_all=True, append_images=images[1:])
        yield Log(f"Wrote {dest.name} ({len(images)} pages)")
        yield Done(f"Created 1 PDF with {len(images)} page(s)", out)
    else:
        yield Step(f"Converting {len(files)} image(s) to individual PDFs")
        for i, path in enumerate(files, start=1):
            dest = unique_path(out / f"{path.stem}.pdf")
            _flatten_to_rgb(Image.open(path)).save(dest)
            yield Log(f"Wrote {dest.name}")
            yield Progress(i, len(files))
        yield Done(f"Created {len(files)} PDF file(s)", out)


def _date_taken(path: Path) -> datetime:
    if is_mac():
        try:
            result = subprocess.run(
                ["mdls", "-name", "kMDItemContentCreationDate", "-raw", str(path)],
                capture_output=True, text=True,
            )
            raw = result.stdout.strip()
            if raw and raw != "(null)":
                return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
        except Exception:
            pass
    else:
        try:
            from PIL import Image, ExifTags
            exif = Image.open(path).getexif()
            tag = next((k for k, v in ExifTags.TAGS.items() if v == "DateTimeOriginal"), None)
            if tag and tag in exif:
                return datetime.strptime(exif[tag], "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def run_rename_by_date(folder, **_):
    folder = Path(folder)
    images = [f for f in folder.rglob("*")
              if f.is_file() and not f.name.startswith(".")
              and f.suffix.lower() in IMAGE_EXTENSIONS]
    if not images:
        yield Done("No supported images found in that folder.", None)
        return

    yield Step(f"Sorting {len(images)} image(s) by date taken")
    images.sort(key=_date_taken)

    # Two-pass rename through temp names so existing IMG_00N files can't collide.
    yield Step("Renaming")
    temps = []
    for i, path in enumerate(images, start=1):
        temp = path.with_name(f"__TB_TMP_{i:05d}{path.suffix}")
        try:
            path.rename(temp)
            temps.append((temp, path.suffix))
        except Exception as exc:
            yield Log(f"{path.name}: {exc}")

    renamed = 0
    for i, (temp, suffix) in enumerate(temps, start=1):
        try:
            temp.rename(temp.with_name(f"IMG_{i:03d}{suffix}"))
            renamed += 1
        except Exception as exc:
            yield Log(f"{temp.name}: {exc}")
        yield Progress(i, len(temps))

    yield Done(f"Renamed {renamed} image(s)", folder)


# ── PDF tools ─────────────────────────────────────────────────────────────

def run_pdf_to_jpg(file, dpi="300", **_):
    fitz = require_module("fitz", "pymupdf")
    path = Path(file)
    try:
        render_dpi = int(str(dpi).strip() or 300)
    except ValueError:
        render_dpi = 300

    out = output_folder("JPG Converted")
    with fitz.open(str(path)) as doc:
        total = doc.page_count
        yield Step(f"Rendering {total} page(s) at {render_dpi} DPI")
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=render_dpi, alpha=False)
            dest = unique_path(out / f"{path.stem}_page_{i}.jpg")
            dest.write_bytes(pix.tobytes("jpeg"))
            yield Progress(i, total)
    yield Done(f"Converted {total} page(s)", out)


def run_pdf_to_word(file, **_):
    require_module("pdf2docx")
    from pdf2docx import Converter

    path = Path(file)
    out = output_folder("Word Converted")
    dest = unique_path(out / f"{path.stem}.docx")

    yield Step("Converting PDF to Word (this can take a moment)")
    yield Progress(0, 1)
    converter = Converter(str(path))
    try:
        converter.convert(str(dest))
    finally:
        converter.close()
    yield Progress(1, 1)
    yield Done(f"Wrote {dest.name}", out)


def run_unlock_pdf(file, password="", **_):
    require_module("pypdf")
    from pypdf import PdfReader, PdfWriter

    path = Path(file)
    reader = PdfReader(str(path))

    if reader.is_encrypted:
        yield Step("Decrypting")
        if not reader.decrypt(password or ""):
            raise RuntimeError("Incorrect password — could not unlock this PDF.")
    else:
        yield Log("This PDF was not password-protected; saving a plain copy.")

    yield Step(f"Copying {len(reader.pages)} page(s)")
    writer = PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
        writer.add_page(page)
        yield Progress(i, len(reader.pages))

    out = output_folder("Unlocked PDF")
    dest = unique_path(out / path.name)
    with open(dest, "wb") as handle:
        writer.write(handle)
    yield Done(f"Unlocked -> {dest.name}", out)


def run_lock_pdf(file, password="", **_):
    require_module("pypdf")
    from pypdf import PdfReader, PdfWriter

    if not password:
        raise RuntimeError("A password is required to lock a PDF.")

    path = Path(file)
    reader = PdfReader(str(path))
    writer = PdfWriter()

    yield Step(f"Encrypting {len(reader.pages)} page(s)")
    for i, page in enumerate(reader.pages, start=1):
        writer.add_page(page)
        yield Progress(i, len(reader.pages))
    writer.encrypt(password, algorithm="AES-256")

    out = output_folder("Locked PDF")
    dest = unique_path(out / path.name)
    with open(dest, "wb") as handle:
        writer.write(handle)
    yield Done(f"Locked -> {dest.name}", out)


# Quality/scale ladder tried in order until the PDF fits under target, or
# the ladder runs out (whichever attempt got smallest wins either way).
_RESIZE_QUALITY_LADDER = (85, 70, 55, 40, 25, 15)
_RESIZE_SCALE_LADDER = (1.0, 0.75, 0.5, 0.35)


def _resize_pdf_attempt(original_bytes: bytes, quality: int, scale: float, fitz) -> bytes:
    """Recompress every embedded image at (quality, scale) and return the
    resulting PDF bytes.

    Always rebuilds from the ORIGINAL bytes rather than mutating a shared
    fitz.Document across attempts: PyMuPDF's replace_image() invalidates the
    xref it just replaced, so calling it again against a xref captured
    before an earlier replacement corrupts the document (confirmed while
    building this — it silently produced a valid-looking but blank PDF)."""
    from PIL import Image as PILImage

    doc = fitz.open(stream=original_bytes, filetype="pdf")
    try:
        processed = set()
        for page in doc:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                if xref in processed:
                    continue
                processed.add(xref)
                base = doc.extract_image(xref)
                img = PILImage.open(io.BytesIO(base["image"]))
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                if scale < 1.0:
                    w, h = img.size
                    img = img.resize(
                        (max(1, int(w * scale)), max(1, int(h * scale))),
                        PILImage.LANCZOS,
                    )
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                page.replace_image(xref, stream=buf.getvalue())
        out = io.BytesIO()
        doc.save(out, garbage=4, deflate=True, clean=True)
        return out.getvalue()
    finally:
        doc.close()


def run_resize_pdf(file, target_kb="500", **_):
    fitz = require_module("fitz", "pymupdf")
    require_module("PIL", "pillow")

    path = Path(file)
    try:
        target = int(str(target_kb).strip() or 500)
    except ValueError:
        target = 500

    original = path.read_bytes()
    before_kb = len(original) / 1024
    yield Step(f"Resizing {path.name} ({before_kb:.0f} KB) under {target} KB")

    image_count = 0
    with fitz.open(stream=original, filetype="pdf") as probe:
        for page in probe:
            image_count += len(page.get_images(full=True))

    if image_count == 0:
        raise RuntimeError(
            "This PDF has no embedded images to recompress — it's likely "
            "already as small as its text/vector content allows."
        )

    attempts = [(q, s) for s in _RESIZE_SCALE_LADDER for q in _RESIZE_QUALITY_LADDER]
    best_bytes, best_kb = original, before_kb

    for i, (quality, scale) in enumerate(attempts, start=1):
        candidate = _resize_pdf_attempt(original, quality, scale, fitz)
        candidate_kb = len(candidate) / 1024
        yield Progress(i, len(attempts))
        if candidate_kb < best_kb:
            best_bytes, best_kb = candidate, candidate_kb
        if candidate_kb <= target:
            break

    out = output_folder("Resized PDF")
    dest = unique_path(out / path.name)
    dest.write_bytes(best_bytes)

    if best_kb <= target:
        yield Done(f"{before_kb:.0f} KB -> {best_kb:.0f} KB (under {target} KB target)", out)
    else:
        yield Done(
            f"{before_kb:.0f} KB -> {best_kb:.0f} KB — could not reach {target} KB "
            f"without visible quality loss; this is the smallest usable result.",
            out,
        )


# ── File management ───────────────────────────────────────────────────────

def file_hash(path: Path) -> str | None:
    hasher = hashlib.md5()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def find_duplicates_by_name(folder: Path):
    seen, dupes = {}, []
    files = [f for f in folder.rglob("*") if f.is_file()]
    for path in files:
        try:
            key = (path.name.lower(), path.stat().st_size, path.suffix.lower())
        except OSError:
            continue
        if key in seen:
            dupes.append((path, seen[key]))
        else:
            seen[key] = path
    return dupes, len(files)


def find_duplicates_by_content(folder: Path):
    by_stem = defaultdict(set)
    media = []
    for path in folder.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS or suffix in VIDEO_EXTENSIONS:
            by_stem[(str(path.parent), path.stem)].add(suffix)
            media.append(path)

    live_photos = sum(
        1 for exts in by_stem.values()
        if (exts & IMAGE_EXTENSIONS) and (exts & VIDEO_EXTENSIONS)
    )

    seen, dupes = {}, []
    for path in media:
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        digest = file_hash(path)
        if not digest:
            continue
        if digest in seen:
            dupes.append((path, seen[digest]))
        else:
            seen[digest] = path
    return dupes, len(media), live_photos


def run_find_duplicates(folder, mode="Quick", **_):
    folder = Path(folder)
    thorough = "thorough" in str(mode).lower()

    yield Step(f"Scanning {folder}")
    if thorough:
        dupes, total, live = find_duplicates_by_content(folder)
        yield Log(f"Scanned {total} media file(s); found {live} Live Photo pair(s).")
    else:
        dupes, total = find_duplicates_by_name(folder)
        yield Log(f"Scanned {total} file(s).")

    if not dupes:
        yield Done("No duplicates found.", folder)
        return

    yield Step(f"Found {len(dupes)} duplicate(s)")
    for dup, original in dupes[:200]:
        yield Log(f"DUP  {dup}\n  of  {original}")
    if len(dupes) > 200:
        yield Log(f"... and {len(dupes) - 200} more")

    yield Done(
        f"Found {len(dupes)} duplicate(s). Nothing was deleted — "
        f"review the list above and remove them yourself.",
        folder,
    )


RUNNERS = {
    "compress_images": run_compress_images,
    "images_to_pdf": run_images_to_pdf,
    "rename_by_date": run_rename_by_date,
    "pdf_to_jpg": run_pdf_to_jpg,
    "pdf_to_word": run_pdf_to_word,
    "unlock_pdf": run_unlock_pdf,
    "lock_pdf": run_lock_pdf,
    "resize_pdf": run_resize_pdf,
    "find_duplicates": run_find_duplicates,
}
