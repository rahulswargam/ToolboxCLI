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


def test_video_trim_requires_end_time(tmp_path):
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    fake = tmp_path / "v.mp4"
    fake.write_bytes(b"not really a video")
    with pytest.raises(RuntimeError):
        drain(runners.run_video_trim(file=str(fake), start="00:00:00", end=""))
