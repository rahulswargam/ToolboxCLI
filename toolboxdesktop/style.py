"""A monochrome design system shared by the dashboard and every dialog."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

PALETTES = {
    "dark": dict(bg="#111111", surface="#181818", raised="#222222", hover="#292929", border="#363636", text="#f4f4f4", muted="#aaaaaa", inverse="#111111", primary="#f4f4f4"),
    "light": dict(bg="#f6f6f6", surface="#ffffff", raised="#eeeeee", hover="#e8e8e8", border="#d5d5d5", text="#161616", muted="#616161", inverse="#ffffff", primary="#161616"),
}


def system_theme(app):
    scheme = app.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return "dark"
    if scheme == Qt.ColorScheme.Light:
        return "light"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return "light" if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else "dark"
    except (ImportError, OSError):
        return "light"


def stylesheet(mode):
    p = PALETTES[mode]
    css = """
* { font-family: 'Segoe UI'; font-size: 13px; }
QWidget { color: TEXT; }
QMainWindow, QDialog, QWidget#page { background: BG; }
QFrame#sidebar { background: SURFACE; border-right: 1px solid BORDER; }
QLabel#brand { font-size: 21px; font-weight: 700; letter-spacing: -0.6px; }
QLabel#eyebrow { color: MUTED; font-size: 10px; font-weight: 600; letter-spacing: 1.6px; }
QLabel#title { font-size: 33px; font-weight: 650; letter-spacing: -1.1px; }
QLabel#subtitle { color: MUTED; font-size: 13px; }
QLabel#section { font-size: 18px; font-weight: 600; letter-spacing: -0.3px; }
QLabel#muted { color: MUTED; }
QLabel#badge { background: RAISED; color: MUTED; border: 1px solid BORDER; border-radius: 12px; padding: 5px 11px; font-size: 11px; }
QFrame#dropzone { background: SURFACE; border: 1px dashed BORDER; border-radius: 16px; }
QFrame#dropzone[dragging="true"] { background: RAISED; border: 2px solid TEXT; }
QFrame#card, QFrame#settingCard { background: SURFACE; border: 1px solid BORDER; border-radius: 12px; }
QFrame#card:hover { border-color: MUTED; background: HOVER; }
QFrame#card:focus { border-color: TEXT; }
QLabel#cardTitle { font-size: 15px; font-weight: 600; }
QLabel#cardDescription { color: MUTED; }
QPushButton#favorite { background: transparent; border: none; padding: 0; font-size: 20px; color: MUTED; }
QPushButton#favorite:hover { background: RAISED; color: TEXT; }
QPushButton#cardAction { background: transparent; border: none; padding: 0; color: TEXT; text-align: right; }
QPushButton#cardAction:hover { text-decoration: underline; }
QPushButton { background: SURFACE; color: TEXT; border: 1px solid BORDER; border-radius: 7px; padding: 9px 14px; }
QPushButton:hover { background: HOVER; border-color: MUTED; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 1px solid TEXT; }
QPushButton:disabled { color: MUTED; background: RAISED; border-color: BORDER; }
QPushButton#primary { color: INVERSE; background: PRIMARY; border: 1px solid PRIMARY; font-weight: 600; }
QPushButton#primary:hover { background: MUTED; border-color: MUTED; }
QPushButton#nav { text-align: left; background: transparent; border: none; padding: 12px; color: MUTED; }
QPushButton#nav:hover { background: RAISED; color: TEXT; }
QPushButton#nav:checked { background: RAISED; color: TEXT; font-weight: 600; }
QPushButton#quiet { background: transparent; border: none; padding: 5px 8px; color: MUTED; }
QPushButton#quiet:hover { background: RAISED; color: TEXT; }
QLineEdit, QComboBox, QSpinBox, QListWidget, QTableWidget, QTextEdit {
 background: SURFACE; color: TEXT; border: 1px solid BORDER; border-radius: 7px; padding: 9px; selection-background-color: PRIMARY; selection-color: INVERSE;
}
QComboBox QAbstractItemView { background: SURFACE; color: TEXT; selection-background-color: PRIMARY; selection-color: INVERSE; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: BG; }
QScrollBar:vertical { background: BG; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: BORDER; min-height: 40px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { border: none; border-radius: 4px; background: RAISED; height: 9px; text-align: center; }
QProgressBar::chunk { background: TEXT; border-radius: 4px; }
QHeaderView::section { background: RAISED; color: TEXT; padding: 10px; border: none; }
QTableWidget { gridline-color: BORDER; }
QCheckBox { spacing: 9px; }
QListWidget::item { padding: 10px; border-radius: 5px; }
QListWidget::item:selected { background: PRIMARY; color: INVERSE; }
QToolTip { background: PRIMARY; color: INVERSE; border: none; padding: 7px; }
QGraphicsView { border: 1px solid BORDER; border-radius: 7px; }
QToolBar { background: transparent; border: none; spacing: 6px; }
QToolBar QToolButton { background: SURFACE; color: TEXT; border: 1px solid BORDER; border-radius: 6px; padding: 7px 11px; }
QToolBar QToolButton:hover { background: HOVER; border-color: MUTED; }
QToolBar QToolButton:disabled { color: MUTED; background: RAISED; }
"""
    for key, value in p.items():
        css = css.replace(key.upper(), value)
    return css


def apply_theme(app, mode):
    p = PALETTES[mode]
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, p["bg"]), (QPalette.ColorRole.WindowText, p["text"]),
                        (QPalette.ColorRole.Base, p["surface"]), (QPalette.ColorRole.AlternateBase, p["raised"]),
                        (QPalette.ColorRole.Text, p["text"]), (QPalette.ColorRole.Button, p["surface"]),
                        (QPalette.ColorRole.ButtonText, p["text"]), (QPalette.ColorRole.Highlight, p["primary"]),
                        (QPalette.ColorRole.HighlightedText, p["inverse"]), (QPalette.ColorRole.ToolTipBase, p["primary"]),
                        (QPalette.ColorRole.ToolTipText, p["inverse"]), (QPalette.ColorRole.PlaceholderText, p["muted"]),
                        (QPalette.ColorRole.Link, p["text"])):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet(mode))


STYLE = stylesheet("dark")
