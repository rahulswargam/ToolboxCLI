from pathlib import Path
import io

import fitz
import pytest
from PIL import Image

from toolboxdesktop.operations import (pages_from_text, merge_pdf, edit_pdf, sign_pdf,
                                      scan_duplicates, recycle_duplicates, compress_pdf)


@pytest.fixture
def document(tmp_path):
    path = tmp_path / "source.pdf"
    with fitz.open() as doc:
        for index in range(3):
            page = doc.new_page(width=300, height=400)
            page.insert_text((30, 40), f"Original page {index + 1}")
        doc.save(path)
    return path


def test_page_ranges_validate_bounds_and_keep_order():
    assert pages_from_text("3,1-2", 3) == [2, 0, 1]
    for value in ("0", "4", "2-1", "", "1-2-3"):
        with pytest.raises(ValueError):
            pages_from_text(value, 3)


def test_merge_preserves_document_order_and_original(document, tmp_path):
    before = document.read_bytes()
    path = merge_pdf([document, document], tmp_path / "merged.pdf")
    with fitz.open(path) as doc:
        assert len(doc) == 6
        assert "Original page 1" in doc[3].get_text()
    assert before == document.read_bytes()


def test_compress_text_pdf_keeps_text_and_never_increases_size(document, tmp_path):
    path, before, after, reached = compress_pdf(document, tmp_path / "compressed.pdf", 500)
    assert after <= before and reached
    with fitz.open(path) as doc:
        assert len(doc) == 3 and "Original page 2" in doc[1].get_text()


def test_rotate_organize_remove(document, tmp_path):
    rotated = edit_pdf(document, tmp_path / "rotated.pdf", "rotate", [1], 90)
    with fitz.open(rotated) as doc:
        assert [p.rotation for p in doc] == [0, 90, 0]
    ordered = edit_pdf(document, tmp_path / "ordered.pdf", "organize", [2, 0, 1])
    with fitz.open(ordered) as doc:
        assert [p.get_text().strip() for p in doc] == ["Original page 3", "Original page 1", "Original page 2"]
    removed = edit_pdf(document, tmp_path / "removed.pdf", "remove", [1])
    with fitz.open(removed) as doc:
        assert len(doc) == 2
        assert "Original page 3" in doc[1].get_text()
    with pytest.raises(ValueError):
        edit_pdf(document, tmp_path / "empty.pdf", "remove", [0, 1, 2])
    with pytest.raises(FileExistsError):
        edit_pdf(document, document, "rotate", [0])


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_signature_is_visible_on_selected_rotated_page(document, tmp_path, rotation):
    source = edit_pdf(document, tmp_path / f"source{rotation}.pdf", "rotate", [1], rotation or 90) if rotation else document
    png = io.BytesIO()
    Image.new("RGBA", (150, 40), (0, 0, 200, 255)).save(png, "PNG")
    path = sign_pdf(source, tmp_path / f"signed{rotation}.pdf", 1, png.getvalue(), (.1, .6, .5, .15))
    with fitz.open(path) as doc:
        assert not doc[0].get_image_info()
        assert len(doc[1].get_image_info()) == 1
        pix = doc[1].get_pixmap()
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        pixel = image.getpixel((int(pix.width * .35), int(pix.height * .675)))
        assert pixel[2] > 150 and pixel[0] < 30


def test_duplicates_all_types_and_scoped_scan(tmp_path):
    (tmp_path / "a.txt").write_text("identical")
    (tmp_path / "b.bin").write_text("identical")
    (tmp_path / "c.txt").write_text("different")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.txt").write_text("identical")
    items, warnings, count = scan_duplicates(tmp_path)
    assert count == 3 and len(items) == 1 and not warnings
    items, _, count = scan_duplicates(tmp_path, True)
    assert count == 4 and len(items) == 2


def test_recycle_rechecks_content_and_keeps_original(tmp_path, monkeypatch):
    import send2trash
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("identical")
    b.write_text("identical")
    items, _, _ = scan_duplicates(tmp_path)
    recycled = []
    monkeypatch.setattr(send2trash, "send2trash", lambda path: recycled.append(path))
    removed, errors = recycle_duplicates(items, tmp_path)
    assert removed == [b] and not errors and recycled == [str(b)]
    assert a.exists()
    b.write_text("DIFFERENT")
    removed, errors = recycle_duplicates(items, tmp_path)
    assert not removed and errors
    assert len(recycled) == 1


def test_recycle_rejects_wrong_root(tmp_path, monkeypatch):
    import send2trash
    (tmp_path / "a").write_text("same")
    (tmp_path / "b").write_text("same")
    items, _, _ = scan_duplicates(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr(send2trash, "send2trash", lambda path: pytest.fail("Must not recycle"))
    removed, errors = recycle_duplicates(items, other)
    assert not removed and errors
