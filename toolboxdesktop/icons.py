"""Small, resolution-independent icons painted with Qt."""
from PySide6.QtCore import Qt, QRectF, QPoint
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPainterPath, QPalette
from PySide6.QtWidgets import QApplication


def icon(kind, size=40, color=None):
    color = color or QApplication.palette().color(QPalette.ColorRole.WindowText).name()
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 40, size / 40)
    p.setPen(QPen(QColor(color), 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == "upload":
        p.drawLine(20, 6, 20, 26)
        p.drawLine(12, 14, 20, 6); p.drawLine(28, 14, 20, 6)
        p.drawLine(7, 25, 7, 34); p.drawLine(7, 34, 33, 34); p.drawLine(33, 34, 33, 25)
    elif kind in ("file", "compress", "remove", "pen", "rotate", "lock"):
        p.drawRoundedRect(QRectF(10, 5, 23, 30), 3, 3)
        if kind == "compress":
            p.drawLine(15, 15, 27, 15); p.drawLine(15, 21, 24, 21); p.drawLine(15, 27, 21, 27)
        elif kind == "remove":
            p.drawLine(16, 16, 27, 27); p.drawLine(27, 16, 16, 27)
        elif kind == "pen":
            p.drawLine(6, 31, 28, 14); p.drawLine(6, 31, 5, 36); p.drawLine(5, 36, 11, 34)
        elif kind == "rotate":
            p.drawArc(13, 13, 16, 16, 20*16, 280*16); p.drawLine(28, 12, 29, 19); p.drawLine(29, 19, 23, 17)
        elif kind == "lock":
            p.drawRoundedRect(QRectF(15, 20, 13, 10), 2, 2); p.drawArc(17, 12, 9, 13, 0, 180*16)
        else:
            p.drawLine(15, 16, 27, 16); p.drawLine(15, 23, 27, 23)
    elif kind == "copy":
        p.drawRoundedRect(QRectF(6, 5, 21, 26), 3, 3); p.drawRoundedRect(QRectF(14, 12, 21, 25), 3, 3)
    elif kind == "merge":
        p.drawLine(8, 7, 20, 20); p.drawLine(32, 7, 20, 20); p.drawLine(20, 20, 20, 34)
        p.drawLine(14, 28, 20, 34); p.drawLine(26, 28, 20, 34)
    elif kind == "image":
        p.drawRoundedRect(QRectF(5, 7, 30, 27), 3, 3); p.drawEllipse(12, 12, 5, 5)
        p.drawPolyline([QPoint(*x) for x in [(7,30),(17,21),(23,26),(29,19),(34,24)]])
    elif kind == "folder":
        p.drawPolyline([QPoint(*x) for x in [(5,13),(5,8),(16,8),(20,13),(35,13),(35,33),(5,33),(5,13)]])
    else:
        for x in (7, 23):
            for y in (7, 23):
                p.drawRoundedRect(QRectF(x, y, 11, 11), 2, 2)
    p.end()
    return QIcon(pix)


def brand_icon(size=64, dark=False):
    """An original T monogram nested in a tool tray, drawn at any resolution."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 64, size / 64)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#f4f4f4" if dark else "#161616"))
    painter.drawRoundedRect(QRectF(0, 0, 64, 64), 16, 16)
    painter.setPen(QPen(QColor("#161616" if dark else "#ffffff"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(16, 18, 48, 18)
    painter.drawLine(32, 18, 32, 36)
    tray = QPainterPath()
    tray.moveTo(16, 31); tray.lineTo(16, 43)
    tray.quadTo(16, 48, 21, 48); tray.lineTo(43, 48)
    tray.quadTo(48, 48, 48, 43); tray.lineTo(48, 31)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(tray)
    painter.end()
    return QIcon(pix)
