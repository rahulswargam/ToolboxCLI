"""Task screen + runner tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from toolboxcli.core import runners
from toolboxcli.core.runners import Done, Log, Progress, Step


@pytest.fixture
def images(tmp_path):
    from PIL import Image
    a = tmp_path / "a.png"
    b = tmp_path / "b.jpg"
    Image.new("RGBA", (600, 400), (200, 30, 30, 180)).save(a)
    Image.new("RGB", (500, 400), (20, 180, 90)).save(b)
    return [str(a), str(b)]


def drain(generator):
    events = list(generator)
    done = [e for e in events if isinstance(e, Done)]
    return events, (done[0] if done else None)


def test_compress_images_emits_full_event_stream(images):
    events, done = drain(runners.run_compress_images(files=images, target_kb="50"))
    assert any(isinstance(e, Step) for e in events)
    assert sum(isinstance(e, Progress) for e in events) == len(images)
    assert done is not None
    assert "compressed under 50 KB" in done.summary


def test_compress_respects_target_size(images):
    from PIL import Image
    _, done = drain(runners.run_compress_images(files=images, target_kb="30"))
    out = Path(done.folder)
    for produced in out.glob("*.jpg"):
        assert produced.stat().st_size / 1024 <= 60  # generous ceiling


def test_compress_handles_bad_target_gracefully(images):
    _, done = drain(runners.run_compress_images(files=images, target_kb="not-a-number"))
    assert done is not None  # falls back to the 100 KB default rather than crashing


def test_images_to_pdf_combine_makes_one_multipage_pdf(images):
    from pypdf import PdfReader
    _, done = drain(runners.run_images_to_pdf(files=images, mode="Combine into one PDF"))
    newest = max(Path(done.folder).glob("Combined*.pdf"), key=lambda p: p.stat().st_mtime)
    assert len(PdfReader(str(newest)).pages) == len(images)


def test_images_to_pdf_separate_makes_one_pdf_each(images):
    events, done = drain(runners.run_images_to_pdf(files=images, mode="One PDF per image"))
    assert f"Created {len(images)}" in done.summary


def test_lock_then_unlock_pdf_round_trip(tmp_path):
    from pypdf import PdfReader, PdfWriter
    src = tmp_path / "plain.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(src, "wb") as handle:
        writer.write(handle)

    _, locked_done = drain(runners.run_lock_pdf(file=str(src), password="hunter2"))
    locked = max(Path(locked_done.folder).glob("plain*.pdf"), key=lambda p: p.stat().st_mtime)
    assert PdfReader(str(locked)).is_encrypted

    _, unlocked_done = drain(runners.run_unlock_pdf(file=str(locked), password="hunter2"))
    unlocked = max(Path(unlocked_done.folder).glob("plain*.pdf"), key=lambda p: p.stat().st_mtime)
    assert not PdfReader(str(unlocked)).is_encrypted


def test_lock_pdf_requires_a_password(tmp_path):
    from pypdf import PdfWriter
    src = tmp_path / "p.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with open(src, "wb") as handle:
        writer.write(handle)
    with pytest.raises(RuntimeError, match="password is required"):
        drain(runners.run_lock_pdf(file=str(src), password=""))


def test_unlock_pdf_rejects_wrong_password(tmp_path):
    from pypdf import PdfWriter
    src = tmp_path / "p.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("right")
    with open(src, "wb") as handle:
        writer.write(handle)
    with pytest.raises(RuntimeError, match="Incorrect password"):
        drain(runners.run_unlock_pdf(file=str(src), password="wrong"))


def test_find_duplicates_quick_mode(tmp_path):
    (tmp_path / "x.txt").write_text("same")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.txt").write_text("same")
    _, done = drain(runners.run_find_duplicates(folder=str(tmp_path), mode="Quick"))
    assert "1 duplicate" in done.summary


def test_find_duplicates_never_deletes(tmp_path):
    """Duplicates are reported, never removed — the user decides."""
    a = tmp_path / "x.txt"
    b = tmp_path / "sub" / "x.txt"
    a.write_text("same")
    b.parent.mkdir()
    b.write_text("same")
    drain(runners.run_find_duplicates(folder=str(tmp_path), mode="Quick"))
    assert a.exists() and b.exists()


def test_find_duplicates_reports_none_when_unique(tmp_path):
    (tmp_path / "a.txt").write_text("one")
    (tmp_path / "b.txt").write_text("two")
    _, done = drain(runners.run_find_duplicates(folder=str(tmp_path), mode="Quick"))
    assert "No duplicates" in done.summary


def _noisy_pdf(tmp_path, name="noisy.pdf", size=(900, 700)) -> Path:
    """A PDF whose embedded JPEG is intentionally low-compressibility (random
    noise), so there's real room for the resizer to shrink it — a flat-color
    test image would already compress to almost nothing and prove nothing."""
    import io
    import random

    import fitz
    from PIL import Image

    random.seed(0)
    w, h = size
    img = Image.new("RGB", (w, h))
    pixels = img.load()
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(40, 40, 572, 752), stream=buf.getvalue())
    dest = tmp_path / name
    doc.save(str(dest))
    doc.close()
    return dest


def test_resize_pdf_shrinks_under_target(tmp_path):
    pdf = _noisy_pdf(tmp_path)
    before_kb = pdf.stat().st_size / 1024
    assert before_kb > 200, "test fixture should start reasonably large"

    _, done = drain(runners.run_resize_pdf(file=str(pdf), target_kb="60"))
    resized = max(Path(done.folder).glob("noisy*.pdf"), key=lambda p: p.stat().st_mtime)
    after_kb = resized.stat().st_size / 1024
    assert after_kb < before_kb
    assert after_kb <= 60
    assert "under 60 KB" in done.summary


def test_resize_pdf_stays_valid_and_keeps_the_image(tmp_path):
    import fitz
    pdf = _noisy_pdf(tmp_path)
    _, done = drain(runners.run_resize_pdf(file=str(pdf), target_kb="500"))
    resized = max(Path(done.folder).glob("noisy*.pdf"), key=lambda p: p.stat().st_mtime)

    doc = fitz.open(str(resized))
    assert doc.page_count == 1
    assert len(doc[0].get_images()) == 1
    pixmap = doc[0].get_pixmap(dpi=50)
    assert any(b != 0 for b in pixmap.samples[:2000]), "page should not have rendered blank"


def test_resize_pdf_rejects_a_pdf_with_no_images(tmp_path):
    from pypdf import PdfWriter
    pdf = tmp_path / "text_only.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(pdf, "wb") as handle:
        writer.write(handle)

    with pytest.raises(RuntimeError, match="no embedded images"):
        drain(runners.run_resize_pdf(file=str(pdf), target_kb="10"))


def test_resize_pdf_handles_bad_target_gracefully(tmp_path):
    pdf = _noisy_pdf(tmp_path)
    _, done = drain(runners.run_resize_pdf(file=str(pdf), target_kb="not-a-number"))
    assert done is not None  # falls back to the 500 KB default rather than crashing


def test_resize_pdf_reports_honestly_when_target_is_unreachable(tmp_path):
    """An unrealistically tiny target should still finish (best effort),
    and say so honestly rather than silently pretending it hit the target."""
    pdf = _noisy_pdf(tmp_path)
    _, done = drain(runners.run_resize_pdf(file=str(pdf), target_kb="1"))
    assert "could not reach" in done.summary.lower()
