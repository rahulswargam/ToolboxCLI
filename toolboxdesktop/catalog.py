from dataclasses import dataclass
from toolboxcli.data.catalog import CATALOG


@dataclass(frozen=True)
class DesktopTool:
    key: str
    label: str
    description: str
    category: str
    icon: str


ICONS = {"compress_images": "image", "images_to_pdf": "image", "rename_by_date": "folder",
         "pdf_to_jpg": "image", "pdf_to_word": "file", "unlock_pdf": "lock",
         "lock_pdf": "lock", "resize_pdf": "compress", "find_duplicates": "copy"}
TOOLS = [DesktopTool(t.key, "Compress PDF" if t.key == "resize_pdf" else t.label,
                     "Optimize your PDF and recompress images toward a target file size." if t.key == "resize_pdf" else t.description,
                     c.name, ICONS[t.key]) for c in CATALOG for t in c.tools]
TOOLS += [
    DesktopTool("fill_pdf", "Fill PDF Forms", "Detect blanks and character boxes, type directly into fields, and sign your forms.", "PDF Tools", "pen"),
    DesktopTool("merge_pdf", "Merge PDF", "Bring multiple documents together in your preferred order.", "PDF Tools", "merge"),
    DesktopTool("sign_pdf", "Sign PDF", "Place a PNG signature or a handwritten-style name on a page.", "PDF Tools", "pen"),
    DesktopTool("rotate_pdf", "Rotate PDF", "Preview pages and turn them 90, 180 or 270 degrees.", "PDF Tools", "rotate"),
    DesktopTool("organize_pdf", "Organize PDF", "Drag page thumbnails to rearrange your document.", "PDF Tools", "grid"),
    DesktopTool("remove_pages", "Remove Pages", "Select unwanted pages and save a clean copy.", "PDF Tools", "remove"),
    DesktopTool("remove_duplicates", "Remove Duplicate Files", "Review identical files and send selected copies to the Recycle Bin.", "File Management", "copy"),
]
