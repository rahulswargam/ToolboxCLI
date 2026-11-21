# Direct form filling — 3.3.0

The earlier Fill & Sign workspace treated character boxes as independent checkboxes and relied on floating annotations. The default interaction now detects writable blanks and embeds inline editors in the page. Clicking outside a blank adds nothing. Manual annotation tools remain available under Manual tools.

## Research

- [Adobe: field properties](https://helpx.adobe.com/vn_en/acrobat/desktop/work-with-pdf-forms/customize-form-fields/field-properties.html): comb fields distribute characters across a fixed number of cells. This informs the single logical field, cell capacity, and keyboard behavior.
- [Adobe: fill and sign](https://helpx.adobe.com/acrobat/desktop/work-with-pdf-forms/fill-sign-forms/fill-sign.html): direct field interaction and keyboard navigation.
- [Apple Preview: fill forms](https://support.apple.com/en-az/guide/preview/prvw35725/mac): click recognized fields and type; recognition is not available for every PDF.
- [OpenCV: line morphology](https://docs.opencv.org/4.10.0/dd/dd7/tutorial_morph_lines_detection.html): horizontal and vertical line extraction supports recognition of connected grids on scanned pages.
- [Qt QLineEdit](https://doc.qt.io/qt-6/qlineedit.html): native editing, clipboard, selection, validators and keyboard behavior.
- [PyMuPDF PDF constants](https://pymupdf.readthedocs.io/en/latest/vars.html): native PDF comb flags and maximum character counts support editable export.

## Implementation and verification

Native PDF fields take precedence. For flat documents, stroked rectangles and scanned grid contours identify blank cells. Adjacent cells of comparable height and spacing become a single comb field. Printed content, photographs and filled section headings are excluded. Labels inform numeric fields and signature regions; exact cell geometry determines on-screen character placement.

Comb editors provide direct typing, selection, clipboard operations, capacity enforcement, leading-zero preservation, and Tab/Shift+Tab navigation. Dates pasted with separators are normalized for numeric cells. Default filling creates no free-floating annotations. Detected fields export as actual editable AcroForm widgets; flattening remains optional.

The [public HDFC minor-to-major form](https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/forms-centre/personal-banking/customer-profile-updation-forms/minor-to-major-upgradation-form.pdf) matching the reported screenshot was downloaded into ignored QA artifacts. It has four pages and no native form widgets. Tests verify Customer ID (9), account number (14), date (8), PAN (10), Aadhaar (12), mobile (10), email (31), mother's name (31), and nationality (19) character rows. Test values are synthetic. The bank template is not redistributed in the installer or source archive.

Automated tests also cover a synthetic flat form, connected grids rasterized as a scan, popup-free typing, Tab, paste, checkboxes, editable export, character centers inside printed cells, and flattening.

## Practical limits

Recognition is local and geometric, with optional local OCR for scanned labels. Unusual dotted lines, low-quality scans, skewed pages, handwriting and ambiguous table cells still require review. This release does not claim universal recognition or implement Apple contact-data autofill. Manual tools allow completion when a blank is missed. Signatures are visual marks rather than certificate-based digital signatures.
