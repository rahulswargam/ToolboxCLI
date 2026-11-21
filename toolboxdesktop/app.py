from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QHBoxLayout,
    QVBoxLayout, QGridLayout, QLineEdit, QScrollArea, QStackedWidget, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QLayout, QSizePolicy)
from .catalog import TOOLS
from .common import label, button, reveal, error
from .icons import icon, brand_icon
from .style import apply_theme, system_theme
from .preferences import Preferences
from .intake import DropZone, selection_kind, recommended_keys
from .forms import ToolForm
from .pdf_editor import PdfEditor
from .duplicates import DuplicateDialog
from .cards import ToolCard, sharp_pixmap
from .pdf_workspace import PdfWorkspace


class MainWindow(QMainWindow):
    def __init__(self, settings_dir=None):
        super().__init__()
        self.settings = Preferences(settings_dir)
        self.theme_mode = self.settings.value("theme", "auto")
        self.active_theme = self.theme_mode if self.theme_mode != "auto" else system_theme(QApplication.instance())
        apply_theme(QApplication.instance(), self.active_theme)
        self.setWindowTitle("Rahul's Toolbox")
        self.setWindowIcon(brand_icon())
        self.resize(1280, 850)
        self.setMinimumSize(960, 640)
        self.card_widgets = []
        self.card_columns = 3
        self.output_root = self.settings.value("output", str(Path.home() / "Documents" / "Rahul's Toolbox"))
        Path(self.output_root).mkdir(parents=True, exist_ok=True)
        self.history = self.settings.value("history", [])
        self.favorites = set(self.settings.value("favorites", []))
        self.selected_paths = []
        self.category = "All tools"
        root = QWidget()
        self.setCentralWidget(root)
        body = QHBoxLayout(root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(208)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(20, 24, 20, 20)
        nav.setSpacing(0)
        self.brand_mark = label("")
        self.brand_mark.setFixedSize(48, 48)
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        nav.addWidget(self.brand_mark)
        nav.addSpacing(12)
        brand_title = label("Toolbox", "brand")
        brand_title.setFixedHeight(30)
        nav.addWidget(brand_title)
        byline = label("BY RAHUL SWARGAM", "eyebrow")
        byline.setFixedHeight(20)
        nav.addWidget(byline)
        nav.addSpacing(26)
        self.sidebar_section(nav, "WORKSPACE")
        self.nav_buttons = {}
        for name in ("All tools", "Favorites", "PDF Tools", "Image Tools", "File Management"):
            self.add_nav(nav, name)
        nav.addSpacing(18)
        self.sidebar_section(nav, "YOUR SPACE")
        for name in ("Recent activity", "Settings"):
            self.add_nav(nav, name)
        nav.addStretch(1)
        nav.addSpacing(24)
        privacy = label("LOCAL BY DESIGN", "eyebrow")
        privacy.setFixedHeight(20)
        nav.addWidget(privacy)
        tagline = label("Your files stay with you.", "muted")
        tagline.setFixedHeight(24)
        nav.addWidget(tagline)
        nav.addSpacing(12)
        version = label("Desktop edition  /  3.3.0", "muted")
        version.setFixedHeight(22)
        nav.addWidget(version)
        body.addWidget(sidebar)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        self.build_dashboard()
        self.build_history()
        self.build_settings()
        self.refresh_brand()
        self.navigate("All tools")
        QApplication.instance().styleHints().colorSchemeChanged.connect(self.system_theme_changed)

    def add_nav(self, layout, name):
        item = button(name, lambda checked=False, n=name: self.navigate(n))
        item.setObjectName("nav")
        item.setCheckable(True)
        item.setFixedHeight(40)
        layout.addWidget(item)
        self.nav_buttons[name] = item

    def sidebar_section(self, layout, text):
        heading = label(text, "eyebrow")
        heading.setContentsMargins(12, 0, 0, 0)
        heading.setFixedHeight(24)
        layout.addWidget(heading)

    def page(self):
        widget = QWidget()
        widget.setObjectName("page")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)
        self.stack.addWidget(widget)
        return widget, layout

    def build_dashboard(self):
        self.dashboard, layout = self.page()
        top = QHBoxLayout()
        top.addWidget(label("WORKSPACE  /  OVERVIEW", "eyebrow"))
        top.addStretch()
        self.theme_badge = label("", "badge")
        self.theme_badge.setFixedHeight(34)
        self.theme_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.theme_badge)
        output_button = button("Output folder  ↗", lambda: reveal(self.output_root))
        output_button.setFixedHeight(34)
        top.addWidget(output_button)
        layout.addLayout(top)
        heading = QVBoxLayout()
        heading.setSpacing(7)
        self.title = label("Your files. Your next move.", "title")
        heading.addWidget(self.title)
        heading.addWidget(label("One considered workspace for documents, images and everything in between.", "subtitle", True))
        layout.addLayout(heading)

        self.dropzone = DropZone()
        self.dropzone.filesDropped.connect(self.ingest_paths)
        hero = QHBoxLayout(self.dropzone)
        hero.setContentsMargins(22, 20, 22, 20)
        hero.setSpacing(20)
        self.upload_mark = label("")
        self.upload_mark.setFixedSize(48, 48)
        self.upload_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.addWidget(self.upload_mark, 0, Qt.AlignmentFlag.AlignVCenter)
        content = QVBoxLayout()
        content.setSpacing(6)
        content.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.upload_eyebrow = label("START WITH A FILE", "eyebrow")
        self.upload_heading = label("Drop it here. Take it further.", "section", True)
        self.upload_detail = label("PDFs, images or a folder. We'll show you what you can do.", "muted", True)
        content.addWidget(self.upload_eyebrow)
        content.addWidget(self.upload_heading)
        content.addWidget(self.upload_detail)
        actions = QVBoxLayout()
        actions.setSpacing(8)
        actions.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.choose_files_button = button("Choose files  +", self.choose_files, True)
        self.choose_folder_button = button("Choose folder", self.choose_folder)
        for action in (self.choose_files_button, self.choose_folder_button):
            action.setFixedSize(144, 36)
            actions.addWidget(action)
        self.clear_button = button("Clear selection", self.clear_selection)
        self.clear_button.setObjectName("quiet")
        self.clear_button.setFixedSize(144, 28)
        self.clear_button.hide()
        actions.addWidget(self.clear_button)
        hero.addLayout(content, 1)
        hero.addLayout(actions)
        layout.addWidget(self.dropzone)

        section = QHBoxLayout()
        self.tools_heading = label("The right tool, right here.", "section")
        section.addWidget(self.tools_heading)
        section.addStretch()
        self.tool_count = label(f"{len(TOOLS)} TOOLS", "eyebrow")
        section.addWidget(self.tool_count)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search your toolbox…")
        self.search.setFixedHeight(36)
        self.search.setMinimumWidth(190)
        self.search.setMaximumWidth(300)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.populate)
        section.addSpacing(16)
        section.addWidget(self.search)
        layout.addLayout(section)
        self.tools_scroll = QScrollArea()
        self.tools_scroll.setWidgetResizable(True)
        self.tools_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tools_scroll.viewport().installEventFilter(self)
        self.cards = QWidget()
        self.grid = QGridLayout(self.cards)
        self.grid.setContentsMargins(2, 2, 12, 10)
        self.grid.setSpacing(16)
        self.grid.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tools_scroll.setWidget(self.cards)
        layout.addWidget(self.tools_scroll, 1)
        footer = QHBoxLayout()
        footer.addWidget(label("CHOOSE A FILE   /   PICK A TOOL   /   SAVE A COPY", "eyebrow"))
        footer.addStretch()
        footer.addWidget(label("No cloud. No uploads.", "muted"))
        layout.addLayout(footer)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose files", "", "Documents & images (*.pdf *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.gif);;All files (*.*)")
        if paths:
            self.ingest_paths(paths)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose a folder")
        if path:
            self.ingest_paths([path])

    def ingest_paths(self, paths):
        # Preserve merge/image order and avoid passing the same file twice.
        selected = list(dict.fromkeys(str(Path(p).resolve()) for p in paths))
        if not selected or any(not Path(p).exists() for p in selected):
            error(self, "Choose existing files or a folder on this computer.")
            return
        self.selected_paths = selected
        kind = selection_kind(selected)
        first = Path(selected[0])
        heading = first.name if len(selected) == 1 else f"{len(selected)} files, ready for your next move."
        self.upload_heading.setText(self.upload_heading.fontMetrics().elidedText(heading, Qt.TextElideMode.ElideMiddle, max(180, self.dropzone.width()-300)))
        self.upload_heading.setToolTip("\n".join(selected))
        self.upload_eyebrow.setText({"pdf": "PDF WORKSPACE", "images": "IMAGE WORKSPACE", "folder": "FOLDER WORKSPACE"}.get(kind, "REVIEW YOUR SELECTION"))
        if kind == "folder":
            detail = "Find duplicate copies or organize image filenames in this folder."
        elif kind == "unsupported":
            detail = "Choose PDFs together, supported images together, or one folder to see compatible tools."
        else:
            size = sum(Path(p).stat().st_size for p in selected)
            detail = f"{len(selected)} {'PDF' if kind == 'pdf' else 'image'} file(s)  ·  {size / 1024 / 1024:,.2f} MB  ·  Select a tool below to continue."
        self.upload_detail.setText(detail)
        self.clear_button.show()
        self.search.clear()
        self.navigate("All tools")
        self.refresh_brand()

    def clear_selection(self):
        self.selected_paths = []
        self.upload_eyebrow.setText("START WITH A FILE")
        self.upload_heading.setText("Drop it here. Take it further.")
        self.upload_heading.setToolTip("")
        self.upload_detail.setText("PDFs, images or a folder. We'll show you what you can do.")
        self.clear_button.hide()
        self.refresh_brand()
        self.populate()

    def visible_tools(self):
        query = self.search.text().lower().strip()
        relevant = recommended_keys(self.selected_paths) if self.selected_paths else None
        tools = [t for t in TOOLS if (self.category == "All tools" or t.category == self.category or
                (self.category == "Favorites" and t.key in self.favorites)) and
                (relevant is None or t.key in relevant) and query in (t.label + " " + t.description + " " + t.category).lower()]
        if self.selected_paths:
            priority = ["fill_pdf", "resize_pdf", "merge_pdf", "sign_pdf", "organize_pdf", "rotate_pdf", "remove_pages", "remove_duplicates", "find_duplicates"]
            tools.sort(key=lambda tool: priority.index(tool.key) if tool.key in priority else len(priority))
        return tools

    def populate(self):
        while self.grid.count():
            child = self.grid.takeAt(0)
            if child.widget():
                child.widget().hide()
                child.widget().deleteLater()
        self.card_widgets = []
        tools = self.visible_tools()
        self.tools_heading.setText("Made for your selection." if self.selected_paths else "The right tool, right here.")
        self.tool_count.setText(f"{len(tools):02d} {'TOOLS' if len(tools) != 1 else 'TOOL'}")
        for index, tool in enumerate(tools):
            card = ToolCard(tool, tool.key in self.favorites, bool(self.selected_paths), self.open_tool, self.toggle_favorite)
            self.card_widgets.append(card)
            self.grid.addWidget(card, index // self.card_columns, index % self.card_columns)
        self.reflow_cards()
        if not tools:
            message = "No compatible tools for this selection. Choose PDFs, JPG/PNG images, or a folder." if self.selected_paths else "No tools found. Try another search or add some favorites."
            self.grid.addWidget(label(message, "muted", True), 0, 0, 1, 3)

    def eventFilter(self, watched, event):
        if hasattr(self, "tools_scroll") and watched is self.tools_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self.reflow_cards()
        return super().eventFilter(watched, event)

    def reflow_cards(self):
        if not hasattr(self, "grid"):
            return
        width = self.tools_scroll.viewport().width() - 14
        columns = max(1, min(3, (width + 16) // 286))
        if columns != self.card_columns:
            self.card_columns = columns
            for card in self.card_widgets:
                self.grid.removeWidget(card)
            for index, card in enumerate(self.card_widgets):
                self.grid.addWidget(card, index // columns, index % columns)
        for col in range(3):
            self.grid.setColumnStretch(col, 1 if col < columns else 0)

    def toggle_favorite(self, key):
        self.favorites.symmetric_difference_update({key})
        self.settings.setValue("favorites", sorted(self.favorites))
        if self.category == "Favorites":
            position = self.tools_scroll.verticalScrollBar().value()
            self.populate()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.tools_scroll.verticalScrollBar().setValue(position))
        else:
            for card in self.card_widgets:
                if card.tool.key == key:
                    card.set_favorite(key in self.favorites)

    def create_tool_dialog(self, tool):
        if tool.key in ("fill_pdf", "sign_pdf"):
            return PdfWorkspace(self, tool, files=self.selected_paths)
        if tool.key == "remove_duplicates":
            return DuplicateDialog(self, folder=self.selected_paths[0] if selection_kind(self.selected_paths) == "folder" else None)
        if tool.key in ("merge_pdf", "rotate_pdf", "organize_pdf", "remove_pages"):
            return PdfEditor(self, tool, files=self.selected_paths)
        return ToolForm(self, tool, selected=self.selected_paths)

    def open_tool(self, tool):
        dialog = self.create_tool_dialog(tool)
        if isinstance(dialog, PdfWorkspace):
            dialog.showMaximized()
        dialog.exec()
        dialog.deleteLater()

    def build_history(self):
        self.activity_page, layout = self.page()
        layout.addWidget(label("A little history.", "title"))
        layout.addWidget(label("Your last 100 operations, kept on this device.", "subtitle"))
        self.activity = QTableWidget(0, 3)
        self.activity.setHorizontalHeaderLabels(["Tool", "Status", "Time"])
        self.activity.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.activity.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.activity, 1)
        layout.addWidget(button("Clear activity", self.clear_history))
        self.refresh_history()

    def record_job(self, tool, status):
        self.history.insert(0, [tool, status, datetime.now().strftime("%d %b %Y, %H:%M")])
        self.history = self.history[:100]
        self.settings.setValue("history", self.history)
        self.refresh_history()

    def clear_history(self):
        self.history = []
        self.settings.setValue("history", [])
        self.refresh_history()

    def refresh_history(self):
        self.activity.setRowCount(len(self.history))
        for row, values in enumerate(self.history):
            for col, value in enumerate(values):
                self.activity.setItem(row, col, QTableWidgetItem(value))

    def build_settings(self):
        self.settings_page, outer = self.page()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        settings_content = QWidget()
        settings_content.setObjectName("page")
        layout = QVBoxLayout(settings_content)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(18)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll.setWidget(settings_content)
        outer.addWidget(scroll)
        layout.addWidget(label("Make yourself at home.", "title"))
        layout.addWidget(label("A few preferences. A workspace that feels like yours.", "subtitle"))
        card = QFrame()
        card.setObjectName("settingCard")
        content = QVBoxLayout(card)
        content.setContentsMargins(24, 22, 24, 22)
        content.setSpacing(14)
        content.addWidget(label("Appearance", "section"))
        content.addWidget(label("Pure monochrome. Choose your preferred light, or let Windows decide.", "muted", True))
        self.theme_choice = QComboBox()
        for text, value in (("Dark", "dark"), ("Light", "light"), ("Auto · follow Windows", "auto")):
            self.theme_choice.addItem(text, value)
        self.theme_choice.setCurrentIndex(self.theme_choice.findData(self.theme_mode))
        self.theme_choice.setAccessibleName("Application theme")
        self.theme_choice.currentIndexChanged.connect(self.change_theme)
        content.addWidget(self.theme_choice)
        self.theme_description = label("", "muted", True)
        content.addWidget(self.theme_description)
        layout.addWidget(card)
        output = QFrame()
        output.setObjectName("settingCard")
        fields = QVBoxLayout(output)
        fields.setContentsMargins(24, 22, 24, 22)
        fields.setSpacing(12)
        fields.addWidget(label("Files & preferences", "section"))
        fields.addWidget(label("OUTPUT FOLDER", "eyebrow"))
        self.output_label = label(self.output_root, "muted", True)
        fields.addWidget(self.output_label)
        fields.addWidget(button("Change output folder…", self.choose_output))
        fields.addWidget(label("SETTINGS FOLDER", "eyebrow"))
        fields.addWidget(label(str(self.settings.folder), "muted", True))
        fields.addWidget(button("Open settings folder  ↗", lambda: reveal(self.settings.folder)))
        layout.addWidget(output)
        layout.addWidget(label("Rahul's Toolbox  /  3.3.0", "section"))
        layout.addWidget(label(f"{len(TOOLS)} local tools. Created by Rahul Swargam.\nPDF edits save new copies. Signature marks are visual, not certificate-based.\nOpen-source component licenses are included in THIRD_PARTY_NOTICES.md.", "muted", True))
        layout.addStretch()

    def change_theme(self):
        self.theme_mode = self.theme_choice.currentData()
        self.settings.setValue("theme", self.theme_mode)
        self.update_theme()

    def system_theme_changed(self, *args):
        if self.theme_mode == "auto":
            self.update_theme()

    def update_theme(self):
        self.active_theme = system_theme(QApplication.instance()) if self.theme_mode == "auto" else self.theme_mode
        apply_theme(QApplication.instance(), self.active_theme)
        self.refresh_brand()
        self.populate()

    def refresh_brand(self):
        self.brand_mark.setPixmap(sharp_pixmap(brand_icon(96, self.active_theme == "dark"), 48))
        kind = selection_kind(self.selected_paths)
        self.upload_mark.setPixmap(sharp_pixmap(icon({"pdf": "file", "images": "image", "folder": "folder"}.get(kind, "upload"), 96), 48))
        self.theme_badge.setText(f"{'Auto / ' if self.theme_mode == 'auto' else ''}{self.active_theme.capitalize()}")
        self.theme_description.setText(f"Currently using {self.active_theme} appearance." + (" Changes with your Windows app theme." if self.theme_mode == "auto" else " Your preference is saved automatically."))

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_root)
        if path:
            self.output_root = path
            self.settings.setValue("output", path)
            self.output_label.setText(path)

    def navigate(self, name):
        for text, item in self.nav_buttons.items():
            item.setChecked(text == name)
        if name == "Recent activity":
            self.stack.setCurrentWidget(self.activity_page)
        elif name == "Settings":
            self.stack.setCurrentWidget(self.settings_page)
        else:
            self.category = name
            self.title.setText("Your files. Your next move." if name == "All tools" else name)
            self.stack.setCurrentWidget(self.dashboard)
            self.populate()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from .verification import self_test
        sys.exit(self_test(Path(sys.argv[2])))
    app = QApplication(sys.argv)
    app.setApplicationName("Rahul's Toolbox")
    app.setOrganizationName("RahulSwargam")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
