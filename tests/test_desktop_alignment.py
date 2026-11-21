from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication
import pytest
from test_desktop_ui import window
from toolboxdesktop.catalog import TOOLS


def settle():
    app = QApplication.instance()
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("mode", ["dark", "light"])
@pytest.mark.parametrize("width,height", [(960, 640), (1280, 680), (1600, 950)])
def test_card_text_and_actions_share_baselines_at_each_window_size(window, mode, width, height):
    window.theme_choice.setCurrentIndex(window.theme_choice.findData(mode))
    window.resize(width, height)
    window.show()
    settle()
    cards = window.card_widgets
    assert len(cards) == len(TOOLS)
    assert len({c.height() for c in cards}) == 1
    assert len({c.title.y() for c in cards}) == 1
    assert len({c.description.y() for c in cards}) == 1
    assert len({c.launch.y() for c in cards}) == 1
    assert all(c.description.alignment() & Qt.AlignmentFlag.AlignTop for c in cards)
    assert window.card_columns == (2 if width == 960 else 3)
    for card in cards:
        assert card.width() >= 270
        assert card.rect().contains(card.launch.geometry())
        assert card.rect().contains(card.category.geometry())
        assert card.description.geometry().bottom() < card.launch.geometry().top()
    assert window.brand_mark.height() == 48
    assert window.brand_mark.width() == 48
    assert {b.height() for b in window.nav_buttons.values()} == {40}
    assert window.choose_files_button.size() == window.choose_folder_button.size()
    assert window.choose_files_button.x() == window.choose_folder_button.x()
    assert window.tools_scroll.horizontalScrollBar().maximum() == 0


def test_final_row_is_fully_visible_at_bottom_and_filtering_reflows(window):
    window.resize(1280, 680)
    window.show()
    settle()
    scroll = window.tools_scroll
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    settle()
    last = window.card_widgets[-1]
    top_left = last.mapTo(scroll.viewport(), last.rect().topLeft())
    bottom_right = last.mapTo(scroll.viewport(), last.rect().bottomRight())
    assert scroll.viewport().rect().contains(top_left)
    assert scroll.viewport().rect().contains(bottom_right)
    window.search.setText("duplicate")
    settle()
    assert len(window.card_widgets) == 2
    assert window.card_widgets[0].y() == window.card_widgets[1].y()
    window.search.clear()
    window.resize(960, 640)
    settle()
    assert window.card_columns == 2
    assert window.card_widgets[2].y() > window.card_widgets[0].y()
