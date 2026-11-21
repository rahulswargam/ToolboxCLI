"""On-page editors that type into the printed blanks, including character cells."""
from __future__ import annotations
import re
from PySide6.QtCore import Qt, QRectF, QTextBoundaryFinder, QSize, QPointF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QValidator, QKeySequence
from PySide6.QtWidgets import QLineEdit, QApplication, QMenu


def graphemes(text):
    data=text.encode("utf-16-le")
    finder=QTextBoundaryFinder(QTextBoundaryFinder.BoundaryType.Grapheme,text)
    result=[]
    start=0
    while True:
        end=finder.toNextBoundary()
        if end<0: break
        result.append((data[start*2:end*2].decode("utf-16-le"),start,end))
        start=end
    return result


class CellValidator(QValidator):
    def __init__(self,count,digits=False,parent=None):
        super().__init__(parent)
        self.count,self.digits=count,digits

    def validate(self,text,position):
        valid=len(graphemes(text))<=self.count and (not self.digits or not text or text.isdecimal())
        return (QValidator.State.Acceptable if valid else QValidator.State.Invalid,text,position)


class CombLineEdit(QLineEdit):
    """One logical input, painted and clicked at the exact printed cell coordinates."""
    def __init__(self,field):
        super().__init__()
        self.field=field
        x0,y0,x1,y1=field["rect"]
        self.cells=[QRectF(r[0]-x0,r[1]-y0,r[2]-r[0],r[3]-r[1]) for r in field["cell_rects"]]
        self.limit=len(self.cells)
        self.setValidator(CellValidator(self.limit,field.get("input_type")=="digits",self))
        self.setFrame(False)
        self.setMinimumSize(1,1)
        self.setStyleSheet("background:transparent; border:none; padding:0; margin:0;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.textChanged.connect(lambda:self.update())
        self.cursorPositionChanged.connect(lambda:self.update())
        self.selectionChanged.connect(self.update)
        self.anchor=0

    def sizeHint(self):
        return QSize(round(self.field["rect"][2]-self.field["rect"][0]),round(self.field["rect"][3]-self.field["rect"][1]))

    def minimumSizeHint(self):
        return QSize(1,1)

    def clean(self,text):
        text=text.replace("\n","").replace("\r","")
        if self.field.get("input_type")=="digits":
            text=re.sub(r"[\s/+.()-]","",text)
        if self.field.get("uppercase"):
            text=text.upper()
        return text

    def paste_clean(self):
        self.insert(self.clean(QApplication.clipboard().text()))

    def keyPressEvent(self,event):
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste_clean()
            event.accept()
            return
        if event.text() and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.AltModifier) and event.key() not in (Qt.Key.Key_Backspace,Qt.Key.Key_Delete,Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Tab,Qt.Key.Key_Backtab):
            cleaned=self.clean(event.text())
            if cleaned != event.text():
                self.insert(cleaned)
                event.accept()
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self,event):
        menu=QMenu(self)
        menu.addAction("Copy",self.copy)
        menu.addAction("Cut",self.cut)
        menu.addAction("Paste",self.paste_clean)
        menu.addSeparator()
        menu.addAction("Select all",self.selectAll)
        menu.exec(event.globalPos())

    def position_at(self,point):
        if not self.cells: return 0
        index=min(range(len(self.cells)),key=lambda i:abs(self.cells[i].center().x()-point.x())+abs(self.cells[i].center().y()-point.y())*2)
        chars=graphemes(self.text())
        if index>=len(chars): return len(self.text().encode('utf-16-le'))//2
        return chars[index][1] if point.x()<=self.cells[index].center().x() else chars[index][2]

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.anchor=self.position_at(event.position())
            self.setCursorPosition(self.anchor)
            event.accept()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            end=self.position_at(event.position())
            self.setSelection(self.anchor,end-self.anchor)
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self,event):
        self.selectAll()
        event.accept()

    def focusInEvent(self,event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self,event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font=QFont("Courier New")
        font.setPixelSize(max(6,round(min(r.height() for r in self.cells)*.72)))
        painter.setFont(font)
        chars=graphemes(self.text())
        start=self.selectionStart()
        end=start+len(self.selectedText().encode('utf-16-le'))//2 if start>=0 else -1
        placeholder="DDMMYYYY" if self.limit==8 and re.search(r"date|birth",self.field["label"],re.I) else ""
        for index,rect in enumerate(self.cells):
            inside=rect.adjusted(.7,.7,-.7,-.7)
            painter.fillRect(inside,QColor("white"))
            if index<len(chars):
                char,a,b=chars[index]
                selected=start>=0 and a<end and b>start
                if selected: painter.fillRect(inside,QColor("#d7d7d7"))
                painter.setPen(QColor("black"))
                painter.drawText(inside,Qt.AlignmentFlag.AlignCenter,char)
            elif placeholder:
                painter.setPen(QColor("#bbbbbb"))
                painter.drawText(inside,Qt.AlignmentFlag.AlignCenter,placeholder[index])
        if self.hasFocus() and self.cells:
            painter.setPen(QPen(QColor("#333333"),.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(0,0,self.width(),self.height()).adjusted(.2,.2,-.2,-.2))
            cursor=next((i for i,(_,a,b) in enumerate(chars) if a>=self.cursorPosition()),len(chars))
            rect=self.cells[min(cursor,self.limit-1)]
            x=rect.left()+2 if cursor<self.limit else rect.right()-2
            painter.setPen(QPen(QColor("black"),.7))
            painter.drawLine(QPointF(x,rect.top()+2),QPointF(x,rect.bottom()-2))
