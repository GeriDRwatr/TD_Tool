import fitz
from PySide6 import QtGui, QtWidgets

from app.pdf_utils import clear_layout, safe_thumbnail_render


def _blank_page():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello")
    return doc, page


def test_safe_thumbnail_render_returns_pixmap_for_valid_page():
    doc, page = _blank_page()
    try:
        pixmap = safe_thumbnail_render(page, fitz.Matrix(1, 1))
        assert isinstance(pixmap, QtGui.QPixmap)
        assert not pixmap.isNull()
        assert pixmap.width() > 0
        assert pixmap.height() > 0
    finally:
        doc.close()


def test_safe_thumbnail_render_falls_back_on_error():
    class _BrokenPage:
        def get_pixmap(self, *args, **kwargs):
            raise RuntimeError("boom")

    pixmap = safe_thumbnail_render(_BrokenPage(), fitz.Matrix(1, 1))

    assert isinstance(pixmap, QtGui.QPixmap)
    assert pixmap.width() == 160
    assert pixmap.height() == 220


def test_clear_layout_removes_all_widgets():
    container = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(container)
    for _ in range(3):
        layout.addWidget(QtWidgets.QLabel("x"))
    assert layout.count() == 3

    clear_layout(layout)

    assert layout.count() == 0


def test_clear_layout_handles_none():
    clear_layout(None)   # не повинно кидати виняток
