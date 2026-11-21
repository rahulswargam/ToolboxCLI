"""Local PDF operations and conservative, content-verified duplicate cleanup."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import fitz


def pages_from_text(text: str, count: int, *, repeat=False) -> list[int]:
    """Parse one-based page ranges, preserving the requested order."""
    result = []
    try:
        for token in text.split(","):
            ends = [int(x.strip()) for x in token.strip().split("-")]
            if len(ends) == 1:
                values = ends
            elif len(ends) == 2 and ends[0] <= ends[1]:
                values = range(ends[0], ends[1] + 1)
            else:
                raise ValueError
            for page in values:
                if page < 1 or page > count:
                    raise ValueError
                if repeat or page - 1 not in result:
                    result.append(page - 1)
    except ValueError:
        raise ValueError(f"Enter page numbers from 1 to {count}, for example 1,3-5.") from None
    if not result:
        raise ValueError("Select at least one page.")
    return result


def open_pdf(path):
    doc = fitz.open(path)
    if doc.needs_pass:
        doc.close()
        raise ValueError("Unlock this PDF first using the Unlock PDF tool.")
    if not doc.is_pdf or not len(doc):
        doc.close()
        raise ValueError("Choose a PDF with at least one page.")
    return doc


def save_pdf(doc, destination):
    """Never overwrite the source or an existing output."""
    destination = Path(destination)
    data = doc.tobytes(garbage=4, deflate=True)
    with destination.open("xb") as handle:
        handle.write(data)
    return destination


def merge_pdf(files, destination, progress=lambda *_: None):
    if len(files) < 2:
        raise ValueError("Choose at least two PDFs to merge.")
    with fitz.open() as result:
        for i, path in enumerate(files):
            with open_pdf(path) as source:
                result.insert_pdf(source)
            progress(i + 1, len(files))
        return save_pdf(result, destination)


def edit_pdf(source, destination, action, pages, angle=90):
    with open_pdf(source) as doc:
        if not pages or any(p < 0 or p >= len(doc) for p in pages):
            raise ValueError("Choose valid pages.")
        if action == "rotate":
            if angle not in (90, 180, 270):
                raise ValueError("Rotation must be 90, 180 or 270 degrees.")
            for index in pages:
                doc[index].set_rotation((doc[index].rotation + angle) % 360)
        elif action == "remove":
            keep = [p for p in range(len(doc)) if p not in pages]
            if not keep:
                raise ValueError("A PDF must retain at least one page.")
            doc.select(keep)
        elif action == "organize":
            doc.select(pages)
        else:
            raise ValueError("Unknown PDF operation.")
        return save_pdf(doc, destination)


def sign_pdf(source, destination, page_index, png, box):
    """Place a visual signature in normalized displayed-page coordinates."""
    with open_pdf(source) as doc:
        page = doc[page_index]
        x, y, w, h = box
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > 1.001 or y + h > 1.001:
            raise ValueError("Keep the signature inside the page.")
        r = page.rect
        rect = fitz.Rect(x * r.width, y * r.height, (x+w)*r.width, (y+h)*r.height)
        rect = rect * page.derotation_matrix
        page.insert_image(rect, stream=png, keep_proportion=True, rotate=page.rotation)
        return save_pdf(doc, destination)


def compress_pdf(source, destination, target_kb, progress=lambda *_: None):
    """Optimize PDF structure, then images, always retaining the smallest result."""
    from toolboxcli.core.runners import _resize_pdf_attempt
    target = int(target_kb)
    if target <= 0:
        raise ValueError("Enter a positive target size.")
    original = Path(source).read_bytes()
    with open_pdf(source) as doc:
        candidate = doc.tobytes(garbage=4, deflate=True, use_objstms=1)
        has_images = any(page.get_images() for page in doc)
    best = min((original, candidate), key=len)
    attempts = [(q, s) for s in (1.0, .75, .5, .35) for q in (85, 70, 55, 40, 25, 15)]
    if has_images and len(best) > target * 1024:
        for i, (quality, scale) in enumerate(attempts):
            candidate = _resize_pdf_attempt(original, quality, scale, fitz)
            best = min((best, candidate), key=len)
            progress(i+1, len(attempts))
            if len(best) <= target * 1024:
                break
    with Path(destination).open("xb") as handle:
        handle.write(best)
    return Path(destination), len(original), len(best), len(best) <= target * 1024


@dataclass(frozen=True)
class Duplicate:
    copy: Path
    original: Path
    size: int
    digest: str


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def scan_duplicates(folder, recursive=False, progress=lambda *_: None):
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Select a folder.")
    files, warnings = [], []
    # Do not cross Windows junctions or symbolic links while walking.
    for root, dirs, names in os.walk(folder, followlinks=False,
                                     onerror=lambda exc: warnings.append(f"Skipped folder: {exc}")):
        dirs[:] = sorted(d for d in dirs if not Path(root, d).is_symlink()
                         and not Path(root, d).is_junction()) if recursive else []
        for name in sorted(names):
            path = Path(root, name)
            if path.is_symlink():
                continue
            try:
                files.append((path, path.stat().st_size))
            except OSError as exc:
                warnings.append(f"Skipped {path}: {exc}")
    sizes = {}
    for path, size in files:
        sizes.setdefault(size, []).append(path)
    candidates = [(path, size) for size, paths in sizes.items() if len(paths) > 1 for path in paths]
    seen, duplicates = {}, []
    for i, (path, size) in enumerate(candidates):
        try:
            hashed = digest(path)
            key = (size, hashed)
            if key in seen:
                duplicates.append(Duplicate(path, seen[key], size, hashed))
            else:
                seen[key] = path
        except OSError as exc:
            warnings.append(f"Skipped {path}: {exc}")
        progress(i + 1, len(candidates))
    return duplicates, warnings, len(files)


def recycle_duplicates(items, folder, progress=lambda *_: None):
    from send2trash import send2trash
    root = Path(folder).resolve(strict=True)
    removed, errors = [], []
    for i, item in enumerate(items):
        try:
            copy = item.copy.resolve(strict=True)
            original = item.original.resolve(strict=True)
            if not copy.is_relative_to(root) or not original.is_relative_to(root) or copy == original:
                raise ValueError("File is outside the scanned folder.")
            if item.copy.is_symlink() or item.original.is_symlink():
                raise ValueError("Symbolic links are not removed.")
            if copy.stat().st_size != item.size or original.stat().st_size != item.size:
                raise ValueError("A file has changed; scan again.")
            if digest(copy) != item.digest or digest(original) != item.digest:
                raise ValueError("A file has changed; scan again.")
            send2trash(str(copy))
            removed.append(copy)
        except Exception as exc:
            errors.append(f"{item.copy}: {exc}")
        progress(i + 1, len(items))
    return removed, errors
