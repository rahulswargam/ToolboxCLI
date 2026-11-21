"""Form inspection, conservative field suggestions, and non-destructive export."""
from __future__ import annotations
import html
import re
from pathlib import Path
import fitz
from .operations import open_pdf, save_pdf

SIGNATURE = re.compile(r"signature|sign\s+here|signed\s+by|हस्ताक्षर", re.I)
LABEL = re.compile(r"name|address|email|e-mail|phone|mobile|date|birth|occupation|city|state|pin\s*code|zip|signature|applicant|passport|nationality", re.I)


def normalized(rect, page):
    rect = fitz.Rect(rect) * page.rotation_matrix
    r = page.rect
    return [rect.x0/r.width, rect.y0/r.height, rect.width/r.width, rect.height/r.height]


def display_rect(box, page):
    x, y, w, h = box
    r = page.rect
    return fitz.Rect(x*r.width, y*r.height, (x+w)*r.width, (y+h)*r.height)


def native_fields(page):
    fields = []
    kinds = {fitz.PDF_WIDGET_TYPE_TEXT: "text", fitz.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
             fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "radio", fitz.PDF_WIDGET_TYPE_COMBOBOX: "choice",
             fitz.PDF_WIDGET_TYPE_LISTBOX: "choice", fitz.PDF_WIDGET_TYPE_SIGNATURE: "signature"}
    for widget in page.widgets() or []:
        if widget.field_type not in kinds:
            continue
        kind = kinds[widget.field_type]
        if kind == "text" and widget.field_flags & fitz.PDF_TX_FIELD_IS_COMB and widget.text_maxlen:
            kind = "comb"
        value = widget.field_value
        if kind == "radio":
            value = value == widget.on_state()
        elif kind == "checkbox":
            value = bool(value) and value != "Off"
        label = widget.field_label or widget.field_name or f"Field {len(fields)+1}"
        rect = widget.rect
        cells = [[rect.x0+i*rect.width/widget.text_maxlen,rect.y0,rect.x0+(i+1)*rect.width/widget.text_maxlen,rect.y1] for i in range(widget.text_maxlen)] if kind == "comb" else []
        fields.append(dict(id=str(widget.xref), page=page.number, kind=kind,
                           label=widget.field_label or widget.field_name or f"Field {len(fields)+1}",
                           name=widget.field_name, box=normalized(widget.rect, page),
                           rect=list(widget.rect),
                           value=value, choices=widget.choice_values or [],
                           on=widget.on_state() if kind in ("checkbox", "radio") else None,
                           readonly=bool(widget.field_flags & fitz.PDF_FIELD_IS_READ_ONLY),
                           required=bool(widget.field_flags & fitz.PDF_FIELD_IS_REQUIRED),
                           signed=bool(widget.is_signed) if kind == "signature" else False,
                           multiline=bool(widget.field_flags & fitz.PDF_TX_FIELD_IS_MULTILINE) if kind == "text" else False,
                           max_length=widget.text_maxlen if kind == "text" else 0,
                           cell_rects=cells,
                           input_type="digits" if not re.search(r"email|e-mail",label,re.I) and re.search(r"date|birth|mobile|phone|pincode|pin.?code|aadhaar|aadhar|customer.?id|account|a/c",label,re.I) else "text",
                           uppercase=bool(re.search(r"\bPAN\b",label,re.I)),
                           native=True))
        if kind == "comb":
            fields[-1]["max_length"] = len(cells)
    return fields


def _label_near(rect, words):
    left = [word for word in words if abs((word[1]+word[3])/2-(rect.y0+rect.y1)/2) < 12 and word[2] <= rect.x0+3 and rect.x0-word[2] < 190]
    above = [word for word in words if 0 <= rect.y0-word[3] < 25 and rect.x0-8 <= word[0] <= rect.x1]
    return " ".join(w[4] for w in (left or above))[:100]


def detect_fields(source, page_index, use_ocr=False):
    """Find real blanks and editable comb groups, rather than individual letter checkboxes."""
    from .blank_fields import detect_blanks
    with open_pdf(source) as doc:
        page = doc[page_index]
        words = list(page.get_text("words"))
        used_ocr = False
        if use_ocr and len(words) < 8:
            import numpy as np
            from rapidocr_onnxruntime import RapidOCR
            scale = min(2.5, 2400/max(page.rect.width,page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
            image = np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
            engine = RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
            results,_ = engine(image)
            for polygon,text,confidence in results or []:
                if confidence < .55: continue
                xs,ys = zip(*polygon)
                rect = fitz.Rect(min(xs)/scale,min(ys)/scale,max(xs)/scale,max(ys)/scale)*page.derotation_matrix
                words.append((rect.x0,rect.y0,rect.x1,rect.y1,text,0,0,0))
            used_ocr = True
        fields = native_fields(page) + detect_blanks(page,words)
        fields.sort(key=lambda f:(round(f["rect"][1]/5),f["rect"][0]))
        return fields, ("Local OCR and blank detection finished. " if used_ocr else "Printed blanks and interactive fields detected. ") + "Click a blank and type; review detection before saving."


def save_filled_pdf(source, destination, values, annotations, flatten=False, detected_fields=None):
    """Update true fields, then add visual entries, preserving original source."""
    with open_pdf(source) as doc:
        radio_groups = {}
        for page in doc:
            for widget in page.widgets() or []:
                key = str(widget.xref)
                if widget.field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
                    parent_kind, parent_ref = doc.xref_get_key(widget.xref, "Parent")
                    parent = int(parent_ref.split()[0]) if parent_kind == "xref" else widget.xref
                    radio_groups.setdefault(parent, []).append((key, widget.xref, widget.on_state(), widget.field_value == widget.on_state(), bool(widget.field_flags & fitz.PDF_FIELD_IS_READ_ONLY)))
                    continue
                if key not in values:
                    continue
                if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE or widget.field_flags & fitz.PDF_FIELD_IS_READ_ONLY:
                    continue
                value = values[key]
                if widget.field_type in (fitz.PDF_WIDGET_TYPE_CHECKBOX, fitz.PDF_WIDGET_TYPE_RADIOBUTTON):
                    widget.field_value = widget.on_state() if value else "Off"
                else:
                    widget.field_value = str(value)
                widget.update()
        def pdf_name(value):
            return "/" + "".join(chr(b) if chr(b).isalnum() and b < 128 or chr(b) in "_.-" else f"#{b:02X}" for b in str(value).encode("utf-8"))
        for parent, group in radio_groups.items():
            if not any(key in values for key, *_ in group) or any(readonly for *_, readonly in group):
                continue
            selected = [item for item in group if item[0] in values and values[item[0]]]
            if not selected:
                selected = [item for item in group if item[0] not in values and item[3]]
            if len(selected) > 1:
                raise ValueError("Select only one option in each radio-button group.")
            chosen = selected[0] if selected else None
            doc.xref_set_key(parent, "V", pdf_name(chosen[2]) if chosen else "/Off")
            for key, xref, on, current, readonly in group:
                doc.xref_set_key(xref, "AS", pdf_name(on) if chosen and chosen[0] == key else "/Off")
        for field in detected_fields or []:
            if field.get("native") or field["kind"] not in ("text","comb","checkbox"):
                continue
            page = doc[field["page"]]
            value = values.get(field["id"],field.get("value",""))
            rect = fitz.Rect(field["rect"])
            widget = fitz.Widget()
            widget.field_name = "toolbox_"+field["id"]
            widget.field_label = field["label"]
            widget.rect = rect
            widget.border_width = 0
            widget.text_color = (0,0,0)
            widget.field_flags = fitz.PDF_FIELD_IS_REQUIRED if field.get("required") else 0
            if field["kind"] == "checkbox":
                widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                created = page.add_widget(widget)
                created.field_value = created.on_state() if value else "Off"
                created.update()
            else:
                widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                widget.field_value = str(value or "")
                widget.text_fontsize = 0
                if field["kind"] == "comb":
                    widget.field_flags |= fitz.PDF_TX_FIELD_IS_COMB
                    widget.text_maxlen = len(field["cell_rects"])
                    widget.text_font = "Cour"
                    widget.text_fontsize = max(6,min(12,min(c[3]-c[1] for c in field["cell_rects"])*.65))
                    # Remove printed DD/MM/YYYY hints only inside filled cells.
                    # The original grid strokes and all neighboring labels remain intact.
                    for index,char in enumerate(str(value or "")):
                        if index >= len(field["cell_rects"]):
                            raise ValueError(f"{field['label']} has {len(field['cell_rects'])} character boxes.")
                        cell = fitz.Rect(field["cell_rects"][index])
                        page.draw_rect(cell+fitz.Rect(.8,.8,-.8,-.8),color=None,fill=(1,1,1),overlay=True)
                elif field.get("multiline"):
                    widget.field_flags |= fitz.PDF_TX_FIELD_IS_MULTILINE
                page.add_widget(widget)
        for entry in annotations:
            page_index = int(entry["page"])
            if not 0 <= page_index < len(doc):
                raise ValueError("An entry refers to an invalid page.")
            page = doc[page_index]
            box = entry["box"]
            if min(box) < 0 or min(box[2:]) <= 0 or box[0]+box[2] > 1.001 or box[1]+box[3] > 1.001:
                raise ValueError("Keep every entry inside its page.")
            rect = display_rect(box, page) * page.derotation_matrix
            kind = entry["kind"]
            if kind == "signature":
                page.insert_image(rect, stream=entry["png"], rotate=page.rotation, keep_proportion=True)
            elif kind in ("check", "cross"):
                # Draw in displayed space, then map each vertex back to PDF space.
                r = display_rect(box, page)
                points = [(r.x0+.15*r.width, r.y0+.5*r.height), (r.x0+.4*r.width, r.y0+.8*r.height), (r.x0+.9*r.width, r.y0+.15*r.height)]
                if kind == "cross":
                    points = [(r.x0+.15*r.width, r.y0+.15*r.height), (r.x0+.85*r.width, r.y0+.85*r.height)]
                points = [fitz.Point(*p)*page.derotation_matrix for p in points]
                page.draw_polyline(points, color=(0, 0, 0), width=max(.8, min(r.width, r.height)*.08), overlay=True)
                if kind == "cross":
                    a = fitz.Point(r.x0+.85*r.width, r.y0+.15*r.height)*page.derotation_matrix
                    b = fitz.Point(r.x0+.15*r.width, r.y0+.85*r.height)*page.derotation_matrix
                    page.draw_line(a, b, color=(0, 0, 0), width=max(.8, min(r.width, r.height)*.08))
            else:
                text = html.escape(str(entry.get("text", ""))).replace("\n", "<br>")
                size = max(6, min(72, float(entry.get("font", 12))))
                page.insert_htmlbox(rect, text, css=f"* {{font-family: sans-serif; font-size: {size}pt; color: black; margin:0; padding:0;}}", rotate=page.rotation)
        if flatten:
            doc.bake(annots=False, widgets=True)
        return save_pdf(doc, destination)
