"""Recognize writable blanks, grouping printed character cells into comb fields.

Geometry is retained in PDF coordinates; labels never determine cell spacing.
"""
from __future__ import annotations
from hashlib import sha1
import re
import statistics
import fitz

SIGN = re.compile(r"signature|sign\s+here|signed\s+by|हस्ताक्षर", re.I)
FORM_LABEL = re.compile(r"name|address|date|birth|phone|mobile|account|a/c|aadhaar|aadhar|pan|pin.?code|pincode|city|state|country|others|amount|rs\.?|email|e-mail", re.I)


def norm(rect, page):
    r = fitz.Rect(rect)*page.rotation_matrix
    return [r.x0/page.rect.width, r.y0/page.rect.height, r.width/page.rect.width, r.height/page.rect.height]


def field_label(rect, words, right=False):
    cy = (rect.y0+rect.y1)/2
    if right:
        candidates = sorted((w for w in words if abs((w[1]+w[3])/2-cy) < max(7, rect.height*.65) and rect.x1-1 <= w[0] <= rect.x1+100), key=lambda w:w[0])
        parts, end = [], rect.x1
        for word in candidates:
            if word[0]-end > (24 if not parts else 8) or len(" ".join(parts)) > 45:
                break
            if word[4] in ("/", "|"):
                break
            parts.append(word[4].strip("/"))
            end = word[2]
        if parts:
            return " ".join(parts)
    candidates = [w for w in words if rect.y0-1 <= (w[1]+w[3])/2 <= rect.y1+1 and w[2] <= rect.x0+1.5 and rect.x0-w[2] < 200]
    if candidates:
        height = max(w[3]-w[1] for w in candidates)
        candidates = [w for w in candidates if w[3]-w[1] >= height*.65]
    candidates.sort(key=lambda w:w[2], reverse=True)
    chain, left = [], rect.x0
    for word in candidates:
        if left-word[2] > (110 if not chain else 12):
            break
        chain.append(word)
        left = min(left, word[0])
    if chain:
        # Include the second line of short labels such as "Mother's maiden name".
        near = [w for w in candidates if left-2 <= w[0] and w[2] <= rect.x0+2]
        return " ".join(w[4] for w in sorted(near, key=lambda w:(round(w[1]/4),w[0])))[:100]
    above = [w for w in words if 0 <= rect.y0-w[3] < 18 and rect.x0-3 <= w[0] <= rect.x1]
    return " ".join(w[4] for w in sorted(above,key=lambda w:(w[1],w[0])))[:100]


def _dedupe(rects):
    result = []
    buckets = {}
    for r in sorted(rects, key=lambda r:r.get_area(), reverse=True):
        if r.is_empty:
            continue
        key = (round((r.x0+r.x1)/8), round((r.y0+r.y1)/8))
        neighbors = [old for dx in (-1,0,1) for dy in (-1,0,1) for old in buckets.get((key[0]+dx,key[1]+dy),[])]
        if any(abs(r.width-old.width) < 4 and abs(r.height-old.height) < 4 and (r & old).get_area()/max(1,min(r.get_area(),old.get_area())) > .82 for old in neighbors):
            continue
        result.append(r)
        buckets.setdefault(key,[]).append(r)
    return result


def raster_rectangles(page):
    """Find small closed cells even when they are part of a connected grid."""
    import cv2
    import numpy as np
    scale = min(3, 2600/max(page.rect.width, page.rect.height))
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
    gray = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    mask = cv2.threshold(gray,225,255,cv2.THRESH_BINARY_INV)[1]
    horizontal = cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(10,round(5*scale)),1)))
    vertical = cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(10,round(5*scale)))))
    grid = cv2.bitwise_or(horizontal,vertical)
    grid = cv2.morphologyEx(grid,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(2,2)))
    contours, _ = cv2.findContours(grid,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    for contour in contours:
        x,y,w,h = cv2.boundingRect(contour)
        wpt,hpt = w/scale,h/scale
        if not (5 <= wpt <= page.rect.width*.91 and 5 <= hpt <= 100):
            continue
        shape = cv2.approxPolyDP(contour,.025*cv2.arcLength(contour,True),True)
        if len(shape) != 4 or cv2.contourArea(contour)/max(1,w*h) < .7:
            continue
        interior = gray[y+max(2,round(scale)):y+h-max(2,round(scale)),x+max(2,round(scale)):x+w-max(2,round(scale))]
        if interior.size and float((interior<160).mean()) > .23:
            continue
        rects.append(fitz.Rect(x/scale,y/scale,(x+w)/scale,(y+h)/scale)*page.derotation_matrix)
    return _dedupe(rects)


def detect_blanks(page, words, extra_rects=()):
    occupied = [fitz.Rect(w.rect) for w in page.widgets() or []]
    rectangles, lines = [], []
    for drawing in page.get_drawings():
        # Solid logos, colored section headers and font outlines are not blanks.
        if "s" not in drawing["type"] or drawing.get("fill") is not None and min(drawing["fill"]) < .9:
            continue
        for item in drawing["items"]:
            if item[0] == "re":
                r = fitz.Rect(item[1])
                if 5 <= r.width <= page.cropbox.width*.92 and 5 <= r.height <= 105:
                    rectangles.append(r)
            elif item[0] == "l":
                a,b = item[1:3]
                if abs(a.y-b.y) < .6 and abs(a.x-b.x) >= 35:
                    lines.append(fitz.Rect(min(a.x,b.x),max(0,a.y-13),max(a.x,b.x),a.y+.2))
    if len(rectangles) < 4 and (page.get_images() or len(lines)>3):
        rectangles.extend(raster_rectangles(page))
    rectangles.extend(fitz.Rect(r) for r in extra_rects)
    rectangles = _dedupe(rectangles)
    def native_overlap(r):
        return any((r & old).get_area() > min(r.get_area(),old.get_area())*.65 for old in occupied)
    def contains_print(r):
        inside = r+fitz.Rect(1.3,1.3,-1.3,-1.3)
        found = [w[4] for w in words if inside.x0 < (w[0]+w[2])/2 < inside.x1 and inside.y0 < (w[1]+w[3])/2 < inside.y1]
        return bool(found) and not all(re.fullmatch(r"[DMYdm y\s]{1,8}",s) for s in found)
    rectangles = [r for r in rectangles if not native_overlap(r) and not contains_print(r)]
    cells = [r for r in rectangles if 5 <= r.width <= 32 and 5 <= r.height <= 32 and .65 <= r.width/r.height <= 1.65]
    rows = []
    for r in sorted(cells,key=lambda r:((r.y0+r.y1)/2,r.x0)):
        match = next((row for row in rows if abs((row[0].y0+row[0].y1)/2-(r.y0+r.y1)/2) <= max(1.2,r.height*.18)),None)
        if match is None:
            rows.append([r])
        else:
            match.append(r)
    groups, used = [], set()
    def finish(run):
        pair_label=""
        if len(run)==2:
            pair=fitz.Rect(run[0])|run[1]
            pair_label=field_label(pair,words)+" "+field_label(pair,words,right=True)
        if len(run) >= 3 or len(run)==2 and re.search(r"year|month|date|birth|since|\bage\b|\bYY\b|\bMM\b|\bDD\b",pair_label,re.I):
            groups.append(run[:])
            used.update(tuple(r) for r in run)
    for row in rows:
        run = []
        for r in sorted(row,key=lambda r:r.x0):
            if run:
                previous = run[-1]
                gap = r.x0-previous.x1
                between_text = any(previous.x1+.3 < (w[0]+w[2])/2 < r.x0-.3 and abs((w[1]+w[3])/2-(r.y0+r.y1)/2)<r.height*.5 for w in words)
                if not (-.8 <= gap <= max(4,previous.width*.7) and .75 <= r.width/previous.width <= 1.3 and .8 <= r.height/previous.height <= 1.25) or between_text:
                    finish(run)
                    run = []
            run.append(r)
        finish(run)
    result = []
    def make(rect,kind,label,cells=None):
        coords = ",".join(f"{v:.1f}" for v in rect)
        key = f"blank-{page.number}-"+sha1((kind+coords).encode()).hexdigest()[:16]
        box = norm(rect,page)
        if min(box)<-.001 or box[0]+box[2]>1.001 or box[1]+box[3]>1.001:
            return
        input_type = "text"
        if not re.search(r"email|e-mail",label,re.I) and re.search(r"date|birth|mobile|phone|pincode|pin.?code|aadhaar|aadhar|customer.?id|account|a/c|year|month|since",label,re.I):
            input_type = "digits"
        result.append(dict(id=key,page=page.number,kind=kind,label=label or ("Character boxes" if kind=="comb" else "Checkbox" if kind=="checkbox" else "Text blank"),
                           rect=list(rect),box=box,native=False,readonly=False,required="*" in label,value="",choices=[],signed=False,
                           input_type=input_type,uppercase=bool(re.search(r"\bPAN\b",label,re.I)),
                           cell_rects=[list(c) for c in cells or []],max_length=len(cells) if cells else 0,multiline=kind=="text" and rect.height>35))
    for run in groups:
        rect = fitz.Rect(run[0])
        for cell in run[1:]: rect |= cell
        label=field_label(rect,words)
        if len(run)==2:label=(label+" "+field_label(rect,words,right=True)).strip()
        make(rect,"comb",label,run)
    group_bounds=[]
    for run in groups:
        bound=fitz.Rect(run[0])
        for cell in run[1:]:bound|=cell
        group_bounds.append(bound)
    for rect in rectangles:
        if tuple(rect) in used:
            continue
        if any((rect&bound).get_area() > min(rect.get_area(),bound.get_area())*.7 for bound in group_bounds):
            continue
        kind = "checkbox" if rect in cells else "text"
        label = field_label(rect,words,right=kind=="checkbox")
        if SIGN.search(label) and kind!="checkbox":
            kind="signature"
        make(rect,kind,label)
    for line in lines:
        label = field_label(line,words)
        if not native_overlap(line) and FORM_LABEL.search(label) and not any((line & fitz.Rect(f['rect'])).get_area()>line.get_area()*.35 for f in result):
            make(line,"signature" if SIGN.search(label) else "text",label)
    for word in words:
        if not SIGN.search(word[4]):
            continue
        label_rect=fitz.Rect(word[:4])
        nearby=[f for f in result if f["kind"] in ("text","signature") and fitz.Rect(f["rect"]).width>=50 and min(abs(f["rect"][3]-label_rect.y0),abs(f["rect"][1]-label_rect.y1))<55 and abs(f["rect"][0]-label_rect.x0)<220]
        if nearby:
            nearest=min(nearby,key=lambda f:min(abs(f['rect'][3]-label_rect.y0),abs(f['rect'][1]-label_rect.y1))+abs(f['rect'][0]-label_rect.x0)*.25)
            nearest["kind"]="signature"
            nearest["label"]=word[4]
        else:
            r=fitz.Rect(label_rect.x0,max(0,label_rect.y0-32),min(page.cropbox.width,label_rect.x0+170),label_rect.y0-2)
            if r.height>10 and not native_overlap(r) and not any((r & fitz.Rect(f['rect'])).get_area()>r.get_area()*.3 for f in result):
                make(r,"signature",word[4])
    return sorted(result,key=lambda f:(round(f["rect"][1]/5),f["rect"][0]))
