"""A zoomable PDF canvas with bounded, directly resizable fill/sign entries."""
from __future__ import annotations
from copy import deepcopy
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPixmap, QPainter, QTextDocument
from PySide6.QtWidgets import QGraphicsView, QGraphicsObject, QGraphicsItem, QGraphicsRectItem


class PageView(QGraphicsView):
    pageClicked = Signal(QPointF)
    deleteRequested = Signal()
    zoomChanged = Signal(int)

    def __init__(self, scene):
        super().__init__(scene)
        self.mode = "select"
        self.fit_mode = "page"
        self.page_rect = QRectF()
        self.setMinimumSize(120, 120)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def set_page_rect(self, rect):
        self.page_rect = QRectF(rect)
        self.scene().setSceneRect(rect)
        QTimer.singleShot(0, self.fit_page)

    def fit_page(self):
        self.fit_mode = "page"
        if not self.page_rect.isEmpty():
            self.fitInView(self.page_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.zoomChanged.emit(round(self.transform().m11()*100))

    def fit_width(self):
        self.fit_mode = "width"
        if self.page_rect.width():
            self.set_zoom((self.viewport().width()-24)/self.page_rect.width(), keep_fit=True)
            self.centerOn(self.page_rect.center().x(), self.page_rect.top()+self.viewport().height()/2/self.transform().m11())

    def set_zoom(self, factor, keep_fit=False):
        if not keep_fit:
            self.fit_mode = "manual"
        factor = max(.1, min(5, factor))
        self.resetTransform()
        self.scale(factor, factor)
        self.zoomChanged.emit(round(factor*100))

    def zoom_by(self, factor):
        self.set_zoom(self.transform().m11()*factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode == "page":
            QTimer.singleShot(0, self.fit_page)
        elif self.fit_mode == "width":
            QTimer.singleShot(0, self.fit_width)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1/1.15)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        if self.mode not in ("select", "fill") and event.button() == Qt.MouseButton.LeftButton and self.page_rect.contains(point):
            self.pageClicked.emit(point)
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and not self.scene().focusItem():
            self.deleteRequested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class EntryItem(QGraphicsObject):
    """Drag body to move; drag any selected corner to resize."""
    def __init__(self, entry, page_rect, begin, commit, edit):
        super().__init__()
        self.entry = entry
        self.area = QRectF(page_rect)
        self.begin = begin
        self.commit = commit
        self.edit = edit
        x, y, w, h = entry["box"]
        self.rect = QRectF(0, 0, w*self.area.width(), h*self.area.height())
        self.setPos(x*self.area.width(), y*self.area.height())
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(20)
        self.resizing = None
        self.image = QPixmap()
        if entry["kind"] == "signature":
            self.image.loadFromData(entry["png"], "PNG")

    def boundingRect(self):
        return self.rect.adjusted(-5, -5, 5, 5)

    def corners(self):
        return [self.rect.topLeft(), self.rect.topRight(), self.rect.bottomLeft(), self.rect.bottomRight()]

    def corner_at(self, point):
        if self.isSelected():
            for index, corner in enumerate(self.corners()):
                if (point-corner).manhattanLength() < 12:
                    return index
        return None

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        kind = self.entry["kind"]
        if kind == "signature":
            painter.drawPixmap(self.rect, self.image, QRectF(self.image.rect()))
        elif kind in ("check", "cross"):
            painter.setPen(QPen(QColor("black"), max(1, min(self.rect.width(), self.rect.height())*.08), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            w, h = self.rect.width(), self.rect.height()
            if kind == "check":
                painter.drawLine(QPointF(.15*w, .5*h), QPointF(.4*w, .8*h))
                painter.drawLine(QPointF(.4*w, .8*h), QPointF(.9*w, .15*h))
            else:
                painter.drawLine(QPointF(.15*w, .15*h), QPointF(.85*w, .85*h))
                painter.drawLine(QPointF(.85*w, .15*h), QPointF(.15*w, .85*h))
        else:
            painter.save()
            painter.setClipRect(self.rect)
            font = QFont("Arial")
            font.setPixelSize(round(self.entry.get("font", 12)))
            painter.setFont(font)
            painter.setPen(QColor("black"))
            painter.drawText(self.rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self.entry.get("text", ""))
            painter.restore()
        if self.isSelected():
            pen = QPen(QColor("#222222"), 0, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect)
            painter.setBrush(QColor("white"))
            painter.setPen(QPen(QColor("#111111"), 0))
            for corner in self.corners():
                painter.drawRect(QRectF(corner.x()-4, corner.y()-4, 8, 8))

    def hoverMoveEvent(self, event):
        corner = self.corner_at(event.pos())
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if corner in (0, 3) else Qt.CursorShape.SizeBDiagCursor if corner is not None else Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self.before = self.begin()
        corner = self.corner_at(event.pos())
        if corner is not None:
            self.resizing = corner
            self.anchor = self.mapToScene(self.corners()[3-corner])
            event.accept()
        else:
            super().mousePressEvent(event)

    def resize_from_corner(self, point):
        anchor = self.anchor
        point = QPointF(max(0, min(point.x(), self.area.width())), max(0, min(point.y(), self.area.height())))
        w, h = max(10, abs(point.x()-anchor.x())), max(10, abs(point.y()-anchor.y()))
        if self.entry["kind"] == "signature":
            ratio = self.image.width()/max(1, self.image.height())
            w = min(w, self.area.width(), self.area.height()*ratio)
            h = w/ratio
        left = point.x() < anchor.x()
        above = point.y() < anchor.y()
        x, y = anchor.x()-w if left else anchor.x(), anchor.y()-h if above else anchor.y()
        x, y = max(0, min(x, self.area.width()-w)), max(0, min(y, self.area.height()-h))
        w, h = min(w, self.area.width()-x), min(h, self.area.height()-y)
        self.prepareGeometryChange()
        self.rect = QRectF(0, 0, w, h)
        self.setPos(x, y)
        self.update()

    def mouseMoveEvent(self, event):
        if self.resizing is not None:
            self.resize_from_corner(event.scenePos())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def sync(self):
        self.entry["box"] = [self.pos().x()/self.area.width(), self.pos().y()/self.area.height(), self.rect.width()/self.area.width(), self.rect.height()/self.area.height()]

    def mouseReleaseEvent(self, event):
        self.resizing = None
        super().mouseReleaseEvent(event)
        self.sync()
        self.commit(self.before)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return QPointF(max(0, min(value.x(), self.area.width()-self.rect.width())), max(0, min(value.y(), self.area.height()-self.rect.height())))
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.edit(self)
        event.accept()


class FieldHint(QGraphicsRectItem):
    def __init__(self, field, rect, clicked):
        super().__init__(rect)
        self.field = field
        self.clicked = clicked
        self.setZValue(5)
        self.setPen(QPen(QColor("#555555"), 0, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(180, 180, 180, 28)))
        self.setToolTip(("Signature area: " if field["kind"] == "signature" else "Suggested field: ") + field["label"])
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        self.clicked(self.field)
        event.accept()
