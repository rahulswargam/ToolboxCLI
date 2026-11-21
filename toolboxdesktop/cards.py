"""Tool cards with shared text slots and aligned action baselines."""
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QSizePolicy, QAbstractButton
from .common import label, button
from .icons import icon


def sharp_pixmap(image_icon, size):
    pixmap = image_icon.pixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    return pixmap


class ToolCard(QFrame):
    def __init__(self, tool, favorite, selected, open_tool, toggle_favorite):
        super().__init__()
        self.tool = tool
        self.open_tool = open_tool
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tool.label)
        self.setObjectName("card")
        self.setMinimumWidth(270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        content = QVBoxLayout(self)
        content.setContentsMargins(18, 16, 18, 16)
        content.setSpacing(8)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(0)
        graphic = label("")
        graphic.setFixedSize(30, 32)
        graphic.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        graphic.setPixmap(sharp_pixmap(icon(tool.icon, 60), 30))
        top.addWidget(graphic)
        top.addStretch()
        star = button("★" if favorite else "☆", lambda: toggle_favorite(tool.key))
        self.favorite_button = star
        star.setObjectName("favorite")
        star.setFixedSize(32, 32)
        star.setToolTip("Remove favorite" if favorite else "Add favorite")
        star.setAccessibleName(f"Favorite {tool.label}")
        top.addWidget(star)
        content.addLayout(top)
        self.title = label(tool.label, "cardTitle", True)
        self.description = label(tool.description, "cardDescription", True)
        for widget in (self.title, self.description):
            widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            widget.ensurePolished()
        self.title.setFixedHeight(self.title.fontMetrics().lineSpacing() * 2 + 2)
        self.description.setFixedHeight(self.description.fontMetrics().lineSpacing() * 3 + 2)
        content.addWidget(self.title)
        content.addWidget(self.description)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        categories = {"Image Tools": "IMAGE", "PDF Tools": "PDF", "File Management": "FILES"}
        self.category = label(categories[tool.category], "eyebrow")
        self.category.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bottom.addWidget(self.category)
        bottom.addStretch()
        self.launch = button("Use tool  ↗", lambda: open_tool(tool))
        self.launch.setObjectName("cardAction")
        self.launch.setFixedHeight(30)
        self.launch.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.addWidget(self.launch)
        content.addLayout(bottom)
        self.setFixedHeight(content.sizeHint().height())
        for widget in (graphic, self.title, self.description, self.category):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_favorite(self, active):
        self.favorite_button.setText("★" if active else "☆")
        self.favorite_button.setToolTip("Remove favorite" if active else "Add favorite")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.open_tool(self.tool)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.open_tool(self.tool)
            event.accept()
        else:
            super().keyPressEvent(event)
