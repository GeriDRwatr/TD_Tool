import os
import fitz
import math as _math
from PySide6 import QtWidgets, QtCore, QtGui
from ..theme import THEME_MGR
from .. import icons as _icons
from ..widgets import _HoverMixin
from ..pdf_utils import safe_thumbnail_render


class _FirstPageButton(_HoverMixin, QtWidgets.QAbstractButton):
    """Кнопка «на першу сторінку» у статус-барі viewer — малює arrow_up через icons.draw()."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press = False
        self.setFixedSize(20, 20)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setToolTip("Перша сторінка")
        self._init_hover()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._press = True
            self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._press = False
        self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        t = THEME_MGR.get()
        if self._press:
            alpha = 230
        elif self._hover:
            alpha = 190
        else:
            alpha = int(t.statusbar_page_alpha)
        c = QtGui.QColor(t.nav_icon_inactive_color)
        c.setAlpha(alpha)
        _icons.draw(p, self.rect(), "arrow_up", c)
        p.end()

# 100 % zoom: 1 PDF point rendered as 1 screen pixel at 96 DPI
_SCALE_100   = 96.0 / 72.0   # ≈ 1.333
_DEFAULT_SCALE = _SCALE_100 * 1.25


class PageWidget(QtWidgets.QWidget):
    """Renders a single PDF page; handles rubber-band text selection."""

    page_clicked  = QtCore.Signal(object)
    cursor_moved  = QtCore.Signal(int, float, float)   # page_num, pdf_x, pdf_y
    cursor_left   = QtCore.Signal()

    def __init__(self, page_num: int, page: fitz.Page, scale: float,
                 rotation: int = 0, parent=None):
        super().__init__(parent)
        self._page_num      = page_num
        self._page          = page
        self._scale         = scale
        self._pixmap:       QtGui.QPixmap | None                       = None
        self._words:        list[tuple[QtCore.QRectF, str, int, int]] = []
        self._sel_start:    QtCore.QPointF | None           = None
        self._sel_end:      QtCore.QPointF | None           = None
        self._highlighted:  list[QtCore.QRectF]             = []
        self._selected_text = ""
        self._click_count   = 0
        self._click_timer   = QtCore.QElapsedTimer()
        self._last_click_pos = QtCore.QPoint()
        self._search_hits_pdf:       list[tuple[float, float, float, float]] = []
        self._search_current_pdf:    tuple[float, float, float, float] | None = None
        self._search_hits_widget:    list[QtCore.QRectF] = []
        self._search_current_widget: QtCore.QRectF | None = None
        self._logical_w   = 0.0
        self._logical_h   = 0.0
        self._rotation    = rotation % 360
        self._coord_mat   = fitz.Matrix(1, 1)
        self._coord_off_x = 0.0
        self._coord_off_y = 0.0
        self.setCursor(QtCore.Qt.IBeamCursor)
        self.setMouseTracking(True)
        self._render()

    # ── rendering ─────────────────────────────────────────────────────────────

    def _device_pixel_ratio(self) -> float:
        dpr = self.devicePixelRatioF()
        if dpr > 0:
            return dpr
        screen = QtWidgets.QApplication.primaryScreen()
        return screen.devicePixelRatio() if screen else 1.0

    def _render(self):
        dpr        = self._device_pixel_ratio()
        # Logical matrix used for coordinate math (no DPR — stays in logical px space)
        logic_mat  = fitz.Matrix(self._scale, self._scale).prerotate(self._rotation)
        # Render matrix uses DPR multiplier for sharp physical pixels
        render_mat = fitz.Matrix(self._scale * dpr, self._scale * dpr).prerotate(self._rotation)
        pix = self._page.get_pixmap(matrix=render_mat, alpha=False)
        img = QtGui.QImage(pix.samples, pix.width, pix.height,
                           pix.stride, QtGui.QImage.Format_RGB888)
        img.setDevicePixelRatio(dpr)
        self._pixmap = QtGui.QPixmap.fromImage(img)
        logical = self._pixmap.deviceIndependentSize().toSize()
        self._logical_w = float(logical.width())
        self._logical_h = float(logical.height())
        self.setFixedSize(logical)
        # Normalisation offset: prerotate shifts coords into negative space;
        # PyMuPDF's get_pixmap translates back, so we must match it.
        rect_t = self._page.rect * logic_mat
        self._coord_mat   = logic_mat
        self._coord_off_x = -rect_t.x0
        self._coord_off_y = -rect_t.y0
        self._load_words()
        self._recompute_search_widget_rects()

    def _pdf_point_to_widget(self, x: float, y: float) -> QtCore.QPointF:
        pt = fitz.Point(x, y) * self._coord_mat
        return QtCore.QPointF(pt.x + self._coord_off_x, pt.y + self._coord_off_y)

    def _pdf_rect_to_widget(self, rect: tuple[float, float, float, float]) -> QtCore.QRectF:
        x0, y0, x1, y1 = rect
        pts = [self._pdf_point_to_widget(x0, y0), self._pdf_point_to_widget(x1, y0),
               self._pdf_point_to_widget(x1, y1), self._pdf_point_to_widget(x0, y1)]
        xs = [p.x() for p in pts]; ys = [p.y() for p in pts]
        return QtCore.QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def _recompute_search_widget_rects(self):
        self._search_hits_widget = [self._pdf_rect_to_widget(r) for r in self._search_hits_pdf]
        self._search_current_widget = (
            self._pdf_rect_to_widget(self._search_current_pdf)
            if self._search_current_pdf else None
        )

    def set_search_highlights(self, hits_pdf: list[tuple[float, float, float, float]],
                              current_pdf: tuple[float, float, float, float] | None = None):
        self._search_hits_pdf    = hits_pdf
        self._search_current_pdf = current_pdf
        self._recompute_search_widget_rects()
        self.update()

    def _load_words(self):
        self._words.clear()
        for w in self._page.get_text("words"):
            x0, y0, x1, y1, text, block_no, line_no = w[0], w[1], w[2], w[3], w[4], w[5], w[6]
            self._words.append((
                self._pdf_rect_to_widget((x0, y0, x1, y1)),
                text, block_no, line_no,
            ))

    def rescale(self, scale: float):
        self._scale         = scale
        self._sel_start     = None
        self._sel_end       = None
        self._highlighted.clear()
        self._selected_text = ""
        self._render()
        self.update()

    def set_rotation(self, degrees: int):
        self._rotation      = degrees % 360
        self._sel_start     = None
        self._sel_end       = None
        self._highlighted.clear()
        self._selected_text = ""
        self._render()
        self.update()

    # ── selection ─────────────────────────────────────────────────────────────

    def clear_selection(self):
        self._sel_start     = None
        self._sel_end       = None
        self._highlighted.clear()
        self._selected_text = ""
        self.update()

    @property
    def pixmap(self) -> QtGui.QPixmap | None:
        return self._pixmap

    @property
    def selected_text(self) -> str:
        return self._selected_text

    def _update_highlight(self):
        if not (self._sel_start and self._sel_end):
            self._highlighted.clear()
            self._selected_text = ""
            return
        rb   = QtCore.QRectF(self._sel_start, self._sel_end).normalized()
        hits = [(r, t) for r, t, _b, _l in self._words if r.intersects(rb)]
        hits.sort(key=lambda x: (round(x[0].top(), 1), x[0].left()))
        self._highlighted   = [r for r, _ in hits]
        self._selected_text = " ".join(t for _, t in hits)

    def _select_word(self, pos: QtCore.QPointF):
        for rect, text, _b, _l in self._words:
            if rect.contains(pos):
                self._sel_start     = QtCore.QPointF(rect.topLeft())
                self._sel_end       = QtCore.QPointF(rect.bottomRight())
                self._highlighted   = [rect]
                self._selected_text = text
                return
        self.clear_selection()

    def _select_line(self, pos: QtCore.QPointF):
        for rect, _text, block_no, line_no in self._words:
            if rect.contains(pos):
                line = [(r, t) for r, t, b, l in self._words
                        if b == block_no and l == line_no]
                line.sort(key=lambda x: x[0].left())
                self._highlighted   = [r for r, _ in line]
                self._selected_text = " ".join(t for _, t in line)
                xs0 = min(r.left()   for r, _ in line)
                ys0 = min(r.top()    for r, _ in line)
                xs1 = max(r.right()  for r, _ in line)
                ys1 = max(r.bottom() for r, _ in line)
                self._sel_start = QtCore.QPointF(xs0, ys0)
                self._sel_end   = QtCore.QPointF(xs1, ys1)
                return
        self.clear_selection()

    def _select_paragraph(self, pos: QtCore.QPointF):
        for rect, _text, block_no, _line_no in self._words:
            if rect.contains(pos):
                block = [(r, t, l) for r, t, b, l in self._words if b == block_no]
                lines: dict[int, list[tuple[QtCore.QRectF, str]]] = {}
                for r, t, l in block:
                    lines.setdefault(l, []).append((r, t))
                text_lines = []
                highlighted = []
                for line_no in sorted(lines):
                    line = sorted(lines[line_no], key=lambda x: x[0].left())
                    highlighted.extend(r for r, _ in line)
                    text_lines.append(" ".join(t for _, t in line))
                self._highlighted   = highlighted
                self._selected_text = "\n".join(text_lines)
                self._sel_start = QtCore.QPointF(
                    min(r.left() for r in highlighted), min(r.top() for r in highlighted))
                self._sel_end = QtCore.QPointF(
                    max(r.right() for r in highlighted), max(r.bottom() for r in highlighted))
                return
        self.clear_selection()

    def _apply_click_selection(self, count: int, pos: QtCore.QPointF):
        if count >= 4:
            self._select_paragraph(pos)
        elif count == 3:
            self._select_line(pos)
        elif count == 2:
            self._select_word(pos)
        else:
            self._sel_start     = pos
            self._sel_end       = pos
            self._highlighted.clear()
            self._selected_text = ""

    def _register_click(self, pos: QtCore.QPoint) -> int:
        interval   = QtWidgets.QApplication.doubleClickInterval()
        same_spot  = (pos - self._last_click_pos).manhattanLength() <= 4
        if self._click_timer.isValid() and self._click_timer.elapsed() <= interval and same_spot:
            self._click_count += 1
        else:
            self._click_count = 1
        self._click_timer.restart()
        self._last_click_pos = pos
        return self._click_count

    # ── cursor → PDF coordinates ───────────────────────────────────────────────

    def _emit_cursor(self, pos: QtCore.QPoint):
        if not self._pixmap or self._logical_w <= 0 or self._logical_h <= 0:
            return
        inv = ~self._coord_mat
        pdf_pt = fitz.Point(pos.x() - self._coord_off_x,
                            pos.y() - self._coord_off_y) * inv
        self.cursor_moved.emit(self._page_num, float(pdf_pt.x), float(pdf_pt.y))

    # ── events ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.page_clicked.emit(self)
            count = self._register_click(event.pos())
            self._apply_click_selection(count, QtCore.QPointF(event.pos()))
            self.update()

    def mouseMoveEvent(self, event):
        self._emit_cursor(event.pos())
        if (event.buttons() & QtCore.Qt.LeftButton and self._sel_start is not None
                and self._click_count <= 1):
            self._sel_end = QtCore.QPointF(event.pos())
            self._update_highlight()
            self.update()

    def mouseReleaseEvent(self, event):
        if (event.button() == QtCore.Qt.LeftButton and self._sel_start is not None
                and self._click_count <= 1):
            self._sel_end = QtCore.QPointF(event.pos())
            self._update_highlight()
            if self._selected_text:
                QtWidgets.QApplication.clipboard().setText(self._selected_text)
            self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.page_clicked.emit(self)
        count = self._register_click(event.pos())
        self._apply_click_selection(count, QtCore.QPointF(event.pos()))
        self.update()

    def leaveEvent(self, event):
        self.cursor_left.emit()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        if self._highlighted:
            sel_c = QtGui.QColor(THEME_MGR.get().selection_color)
            sel_c.setAlpha(90)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(sel_c)
            for rect in self._highlighted:
                p.drawRect(rect)
        elif self._sel_start and self._sel_end:
            sel_c = QtGui.QColor(THEME_MGR.get().selection_color)
            rb = QtCore.QRectF(self._sel_start, self._sel_end).normalized()
            sel_c.setAlpha(160)
            p.setPen(QtGui.QPen(sel_c, 1.0))
            sel_c.setAlpha(28)
            p.setBrush(sel_c)
            p.drawRect(rb)
        if self._search_hits_widget:
            p.setPen(QtCore.Qt.NoPen)
            hit_c = QtGui.QColor(255, 213, 0, 95)
            p.setBrush(hit_c)
            for rect in self._search_hits_widget:
                p.drawRect(rect)
        if self._search_current_widget is not None:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 140, 0, 220), 1.6))
            p.setBrush(QtGui.QColor(255, 160, 0, 110))
            p.drawRect(self._search_current_widget)
        p.end()


# ── Toolbar button (icon or text glyph) ─────────────────────────────────────────

class _ToolbarButton(_HoverMixin, QtWidgets.QAbstractButton):
    """Flat square button for the viewer's top toolbar — draws a vector icon
    (icons.draw) or a short text glyph ('−' / '+'). Right-click emits
    right_clicked instead of the normal press/click handling."""

    right_clicked = QtCore.Signal()

    def __init__(self, content: str, is_icon: bool = True, chevron: bool = False, parent=None):
        super().__init__(parent)
        self._content = content
        self._is_icon = is_icon
        self._chevron = chevron
        self.setFixedSize(46 if chevron else 32, 32)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._init_hover()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.right_clicked.emit()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        t = THEME_MGR.get()
        r = self.rect()

        enabled = self.isEnabled()
        if self._hover and enabled:
            bg = QtGui.QColor(t.nav_hover_bg)
            bg.setAlpha(t.nav_hover_bg_alpha)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 7, 7)

        color = QtGui.QColor(t.nav_icon_inactive_color)
        if not enabled:
            color.setAlpha(int(t.nav_icon_inactive_alpha * 0.35))
        else:
            color.setAlpha(t.nav_icon_active_alpha if self._hover else t.nav_icon_inactive_alpha)
        icon_cx = (r.center().x() - 6) if self._chevron else r.center().x()
        if self._is_icon:
            sz = t.icon_size
            icon_r = QtCore.QRectF(icon_cx - sz / 2, r.center().y() - sz / 2, sz, sz)
            _icons.draw(p, icon_r, self._content, color)
        else:
            p.setFont(_icons.sf_font(17, QtGui.QFont.DemiBold))
            p.setPen(color)
            p.drawText(QtCore.QRect(0, 0, r.width() - (12 if self._chevron else 0), r.height()),
                       QtCore.Qt.AlignCenter, self._content)

        if self._chevron:
            chx = r.right() - 12
            chy = r.center().y()
            cw  = 3.2
            pen = QtGui.QPen(color, 1.4, QtCore.Qt.SolidLine,
                             QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(QtCore.QPointF(chx - cw, chy - cw * 0.6), QtCore.QPointF(chx, chy + cw * 0.6))
            p.drawLine(QtCore.QPointF(chx, chy + cw * 0.6), QtCore.QPointF(chx + cw, chy - cw * 0.6))
        p.end()


# ── Search box (toolbar) ────────────────────────────────────────────────────────

class _SearchField(QtWidgets.QLineEdit):
    """QLineEdit that distinguishes Enter (next match) from Shift+Enter (previous)."""

    next_requested = QtCore.Signal()
    prev_requested = QtCore.Signal()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                self.prev_requested.emit()
            else:
                self.next_requested.emit()
            return
        if event.key() == QtCore.Qt.Key_Escape and self.text():
            self.clear()
            return
        super().keyPressEvent(event)


class _SearchBox(QtWidgets.QWidget):
    """Rounded search field with a magnifying-glass icon, for the top toolbar."""

    text_changed   = QtCore.Signal(str)
    next_requested = QtCore.Signal()
    prev_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchBox")
        self.setFixedSize(190, 28)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(9, 0, 9, 0)
        lay.setSpacing(6)

        self._icon_lbl = QtWidgets.QLabel()
        self._icon_lbl.setFixedSize(14, 14)
        lay.addWidget(self._icon_lbl)

        self._field = _SearchField()
        self._field.setPlaceholderText("Пошук")
        self._field.setFrame(False)
        self._field.textChanged.connect(self.text_changed.emit)
        self._field.next_requested.connect(self.next_requested.emit)
        self._field.prev_requested.connect(self.prev_requested.emit)
        lay.addWidget(self._field, 1)

    def clear(self):
        self._field.blockSignals(True)
        self._field.clear()
        self._field.blockSignals(False)

    def apply_theme(self):
        t = THEME_MGR.get()

        pm = QtGui.QPixmap(14, 14)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        color = QtGui.QColor(t.nav_icon_inactive_color)
        color.setAlpha(t.nav_icon_inactive_alpha)
        _icons.draw(p, QtCore.QRectF(0, 0, 14, 14), "search", color)
        p.end()
        self._icon_lbl.setPixmap(pm)

        self.setStyleSheet(f"""
            QWidget#SearchBox {{
                background: rgba(255,255,255,0.07);
                border-radius: 8px;
            }}
        """)
        self._field.setStyleSheet(
            "QLineEdit { background: transparent; border: none;"
            " color: rgba(255,255,255,0.85); font-size: 12px; }"
        )


# ── Page thumbnail (left navigation strip) ──────────────────────────────────────

_THUMB_PANEL_WIDTH = 168
_THUMB_TARGET_W    = 120


class _ThumbnailItem(QtWidgets.QWidget):
    """Single clickable page thumbnail; highlights when it's the active page."""

    clicked = QtCore.Signal(int)
    _PAD    = 8

    def __init__(self, page_num: int, pixmap: QtGui.QPixmap, parent=None):
        super().__init__(parent)
        self._page_num = page_num
        self._pixmap    = pixmap
        self._active    = False
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedSize(pixmap.width() + self._PAD * 2,
                          pixmap.height() + self._PAD * 2 + 18)

    def set_active(self, v: bool):
        if self._active != v:
            self._active = v
            self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self._page_num)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        t  = THEME_MGR.get()
        px = self._PAD
        py = self._PAD

        if self._active:
            accent = QtGui.QColor(t.accent)
            p.setPen(QtGui.QPen(accent, 2))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRoundedRect(QtCore.QRectF(px - 3, py - 3,
                              self._pixmap.width() + 6, self._pixmap.height() + 6), 4, 4)
        p.drawPixmap(px, py, self._pixmap)

        num_r = QtCore.QRect(0, py + self._pixmap.height() + 4, self.width(), 16)
        p.setFont(_icons.sf_font(11))
        nc = QtGui.QColor(t.nav_label_active_color if self._active else t.nav_label_inactive_color)
        nc.setAlpha(t.nav_label_active_alpha if self._active else t.nav_label_inactive_alpha)
        p.setPen(nc)
        p.drawText(num_r, QtCore.Qt.AlignCenter, str(self._page_num + 1))
        p.end()


class _ThumbnailPanel(QtWidgets.QScrollArea):
    """Left navigation strip with page thumbnails (Acrobat/Preview-style)."""

    page_selected = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFixedWidth(_THUMB_PANEL_WIDTH)

        self._container = QtWidgets.QWidget()
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 10, 0, 10)
        self._vbox.setSpacing(10)
        self._vbox.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
        self.setWidget(self._container)

        self._items:   list[_ThumbnailItem] = []
        self._current = -1

    def load_doc(self, doc: fitz.Document):
        self.clear()
        if not doc:
            return
        pr    = doc.load_page(0).rect
        scale = max(0.05, min(0.5, _THUMB_TARGET_W / max(pr.width, 1.0)))
        mat   = fitz.Matrix(scale, scale)
        for i in range(doc.page_count):
            pix  = safe_thumbnail_render(doc.load_page(i), mat)
            item = _ThumbnailItem(i, pix)
            item.clicked.connect(self.page_selected.emit)
            self._vbox.addWidget(item, alignment=QtCore.Qt.AlignHCenter)
            self._items.append(item)

    def clear(self):
        for it in self._items:
            it.deleteLater()
        self._items.clear()
        self._current = -1

    def set_current(self, idx: int):
        if idx == self._current:
            return
        if 0 <= self._current < len(self._items):
            self._items[self._current].set_active(False)
        if 0 <= idx < len(self._items):
            self._items[idx].set_active(True)
            self.ensureWidgetVisible(self._items[idx], 0, 60)
        self._current = idx

    def apply_theme(self):
        t  = THEME_MGR.get()
        ha = min(1.0, t.scrollbar_alpha / 255)
        self.setStyleSheet(f"""
            QScrollArea {{ background: {t.bg_sidebar}; border: none;
                          border-right: 1px solid {t.bg_border}; }}
            QScrollBar:vertical {{ width: 6px; background: transparent; border: none; margin: 0; }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,{ha:.3f}); border-radius: 3px; min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)
        self._container.setStyleSheet(f"background: {t.bg_sidebar};")
        for it in self._items:
            it.update()


# ── Table of contents (left navigation strip) ───────────────────────────────────

class _TocPanel(QtWidgets.QTreeWidget):
    """Left navigation panel showing the PDF's table of contents (outline)."""

    page_selected = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(_THUMB_PANEL_WIDTH)
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setUniformRowHeights(True)
        self.itemClicked.connect(self._on_item_clicked)

    def load_doc(self, doc: fitz.Document | None):
        self.clear()
        if not doc:
            return
        toc = doc.get_toc(simple=True)
        if not toc:
            placeholder = QtWidgets.QTreeWidgetItem(["Зміст відсутній"])
            placeholder.setFlags(QtCore.Qt.NoItemFlags)
            self.addTopLevelItem(placeholder)
            return
        stack: list[QtWidgets.QTreeWidgetItem] = []
        for level, title, page in toc:
            item = QtWidgets.QTreeWidgetItem([title])
            item.setData(0, QtCore.Qt.UserRole, max(0, page - 1))
            while len(stack) >= max(level, 1):
                stack.pop()
            if stack:
                stack[-1].addChild(item)
            else:
                self.addTopLevelItem(item)
            stack.append(item)
        self.expandAll()

    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _col: int):
        page = item.data(0, QtCore.Qt.UserRole)
        if page is not None:
            self.page_selected.emit(page)

    def apply_theme(self):
        t = THEME_MGR.get()
        self.setStyleSheet(f"""
            QTreeWidget {{
                background: {t.bg_sidebar}; border: none;
                border-right: 1px solid {t.bg_border};
                color: rgba(255,255,255,0.78);
                font-size: 12px;
                outline: none;
            }}
            QTreeWidget::item {{ padding: 5px 4px; }}
            QTreeWidget::item:selected {{ background: rgba(255,255,255,0.08); }}
            QTreeWidget::branch {{ background: transparent; }}
        """)


class ScreenViewer(QtWidgets.QWidget):
    """Full-page PDF viewer with text selection, zoom, and clipboard copy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc:          fitz.Document | None = None
        self._path:         str | None           = None
        self._scale:        float                = _DEFAULT_SCALE
        self._pages:        list[PageWidget]     = []
        self._current_page: int                  = 0
        self._side_mode:    str                  = "thumbnails"   # 'thumbnails' | 'toc'
        self._page_mode:    str                  = "continuous"   # 'continuous' | 'single' | 'two'
        self._view_rotation: int                 = 0              # 0 / 90 / 180 / 270
        self._search_query:       str = ""
        self._search_results:     list[tuple[int, tuple[float, float, float, float]]] = []
        self._search_current_idx: int = -1
        self.setAcceptDrops(True)
        self._build_ui()

    # ── public API ────────────────────────────────────────────────────────────

    def load_pdf(self, path: str):
        self._clear_pages()
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
        self._path = path
        self._doc  = fitz.open(path)
        self._lbl_file.setText(os.path.basename(path))
        self._side_header_lbl.setText(os.path.basename(path))
        self._current_page = 0
        self._lbl_pages.setText(f"1/{self._doc.page_count}")
        self._lbl_cursor.setText("")
        self._scale = self._fit_scale()
        self._view_rotation = 0
        self._render_pages()
        self._thumb_panel.load_doc(self._doc)
        self._thumb_panel.set_current(0)
        self._toc_panel.load_doc(self._doc)
        self._clear_search()
        self._search_box.clear()
        self._update_zoom_label()

    def has_doc(self) -> bool:
        return self._doc is not None

    def close_doc(self):
        """Release the loaded PDF and rendered pages (e.g. before discarding the tab)."""
        self._clear_pages()
        self._thumb_panel.clear()
        self._toc_panel.clear()
        self._clear_search()
        self._search_box.clear()
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None
        self._path = None

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── body: sidebar (header + thumbnails/TOC) + document column ──────────
        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        # ── left: sidebar (its own header, no toolbar buttons) ──────────────────
        self._side_panel = QtWidgets.QWidget()
        self._side_panel.setFixedWidth(_THUMB_PANEL_WIDTH)
        self._side_panel.setVisible(False)
        side_col = QtWidgets.QVBoxLayout(self._side_panel)
        side_col.setContentsMargins(0, 0, 0, 0)
        side_col.setSpacing(0)

        self._side_header = QtWidgets.QWidget()
        self._side_header.setFixedHeight(44)
        shl = QtWidgets.QVBoxLayout(self._side_header)
        shl.setContentsMargins(14, 0, 14, 0)
        self._side_header_lbl = QtWidgets.QLabel("Відкрийте PDF для перегляду")
        self._side_header_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.65); font-size: 12px; font-weight: 600;"
            " background: transparent; border: none;"
        )
        shl.addWidget(self._side_header_lbl, 0, QtCore.Qt.AlignVCenter)
        side_col.addWidget(self._side_header)

        self._thumb_panel = _ThumbnailPanel()
        self._thumb_panel.page_selected.connect(self._go_to_page)

        self._toc_panel = _TocPanel()
        self._toc_panel.page_selected.connect(self._go_to_page)

        self._side_stack = QtWidgets.QStackedWidget()
        self._side_stack.addWidget(self._thumb_panel)
        self._side_stack.addWidget(self._toc_panel)
        side_col.addWidget(self._side_stack, 1)

        body.addWidget(self._side_panel)

        # ── right: document toolbar + scroll area + status bar ──────────────────
        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        body.addLayout(right, 1)

        # ── document toolbar (sits above the work area, not the sidebar) ────────
        self._toolbar = QtWidgets.QWidget()
        self._toolbar.setFixedHeight(44)
        tbl = QtWidgets.QHBoxLayout(self._toolbar)
        tbl.setContentsMargins(10, 0, 10, 0)
        tbl.setSpacing(2)

        self._thumb_toggle_btn = _ToolbarButton("sidebar", chevron=True)
        self._thumb_toggle_btn.setToolTip(
            "Мініатюри сторінок\nПКМ — меню перегляду"
        )
        self._thumb_toggle_btn.clicked.connect(self._toggle_thumbnails)
        self._thumb_toggle_btn.right_clicked.connect(self._show_sidebar_menu)
        tbl.addWidget(self._thumb_toggle_btn)

        tbl.addStretch(1)

        info_btn = _ToolbarButton("info")
        info_btn.setToolTip("Властивості документа")
        info_btn.clicked.connect(self._show_info_dialog)
        tbl.addWidget(info_btn)

        tbl.addSpacing(4)

        zoom_out_btn = _ToolbarButton("−", is_icon=False)
        zoom_out_btn.setToolTip("Зменшити")
        zoom_out_btn.clicked.connect(self._zoom_out)
        tbl.addWidget(zoom_out_btn)

        self._lbl_zoom = QtWidgets.QLabel("100%")
        self._lbl_zoom.setFixedWidth(48)
        self._lbl_zoom.setAlignment(QtCore.Qt.AlignCenter)
        tbl.addWidget(self._lbl_zoom)

        zoom_in_btn = _ToolbarButton("+", is_icon=False)
        zoom_in_btn.setToolTip("Збільшити")
        zoom_in_btn.clicked.connect(self._zoom_in)
        tbl.addWidget(zoom_in_btn)

        tbl.addSpacing(4)

        share_btn = _ToolbarButton("share")
        share_btn.setToolTip("Поділитися (скоро)")
        share_btn.setEnabled(False)
        tbl.addWidget(share_btn)

        tbl.addSpacing(2)

        markup_btn = _ToolbarButton("markup", chevron=True)
        markup_btn.setToolTip("Маркування (скоро)")
        markup_btn.setEnabled(False)
        tbl.addWidget(markup_btn)

        _sep = QtWidgets.QFrame()
        _sep.setFrameShape(QtWidgets.QFrame.VLine)
        _sep.setFixedWidth(1)
        _sep.setFixedHeight(20)
        _sep.setStyleSheet("background: rgba(255,255,255,0.14); border: none;")
        tbl.addSpacing(4)
        tbl.addWidget(_sep)
        tbl.addSpacing(4)

        rotate_btn = _ToolbarButton("rotate")
        rotate_btn.setToolTip("Повернути сторінки на 90°")
        rotate_btn.clicked.connect(self._rotate_view)
        tbl.addWidget(rotate_btn)

        atext_btn = _ToolbarButton("a_circle")
        atext_btn.setToolTip("Текстові анотації (скоро)")
        atext_btn.setEnabled(False)
        tbl.addWidget(atext_btn)

        tbl.addSpacing(10)

        self._search_box = _SearchBox()
        self._search_box.text_changed.connect(self._run_search)
        self._search_box.next_requested.connect(self._search_next)
        self._search_box.prev_requested.connect(self._search_prev)
        tbl.addWidget(self._search_box)

        self._toolbar_buttons = [
            self._thumb_toggle_btn, info_btn,
            zoom_out_btn, zoom_in_btn,
            share_btn, markup_btn, rotate_btn, atext_btn,
        ]
        right.addWidget(self._toolbar)

        self._toolbar_divider = QtWidgets.QFrame()
        self._toolbar_divider.setFixedHeight(1)
        right.addWidget(self._toolbar_divider)

        # ── scroll area ───────────────────────────────────────────────────────
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)

        self._container = QtWidgets.QWidget()
        self._container.setStyleSheet("background: #2c2f3d;")
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setContentsMargins(20, 20, 20, 20)
        self._vbox.setSpacing(16)
        self._vbox.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self._scroll.setWidget(self._container)
        self._scroll.viewport().installEventFilter(self)
        self._scroll.verticalScrollBar().valueChanged.connect(self._update_current_page)

        right.addWidget(self._scroll, 1)

        # ── status bar (bottom) ───────────────────────────────────────────────
        sb = QtWidgets.QWidget()
        sb.setFixedHeight(28)
        sb.setStyleSheet(
            "QWidget { background: #191b21; border-top: 1px solid #2a3045; }"
        )
        sbl = QtWidgets.QHBoxLayout(sb)
        sbl.setContentsMargins(14, 0, 14, 0)
        sbl.setSpacing(0)

        self._lbl_file = QtWidgets.QLabel("Відкрийте PDF для перегляду")
        self._lbl_file.setStyleSheet(
            "color: rgba(255,255,255,0.65); font-size: 12px;"
            " background: transparent; border: none;"
        )
        sbl.addWidget(self._lbl_file, 1)

        _sep1 = QtWidgets.QFrame()
        _sep1.setFrameShape(QtWidgets.QFrame.VLine)
        _sep1.setStyleSheet("color: rgba(255,255,255,0.12); background: transparent; border: none;")
        _sep1.setFixedWidth(1)
        sbl.addSpacing(12)
        sbl.addWidget(_sep1)
        sbl.addSpacing(12)

        self._btn_first_page = _FirstPageButton()
        self._btn_first_page.clicked.connect(lambda: self._go_to_page(0))
        sbl.addWidget(self._btn_first_page)
        sbl.addSpacing(6)

        self._lbl_pages = QtWidgets.QLabel("")
        self._lbl_pages.setStyleSheet(
            "color: rgba(255,255,255,0.45); font-size: 12px;"
            " background: transparent; border: none;"
        )
        self._lbl_pages.setFixedWidth(52)
        self._lbl_pages.setAlignment(QtCore.Qt.AlignCenter)
        sbl.addWidget(self._lbl_pages)

        _sep2 = QtWidgets.QFrame()
        _sep2.setFrameShape(QtWidgets.QFrame.VLine)
        _sep2.setStyleSheet("color: rgba(255,255,255,0.12); background: transparent; border: none;")
        _sep2.setFixedWidth(1)
        sbl.addSpacing(12)
        sbl.addWidget(_sep2)
        sbl.addSpacing(12)

        self._lbl_cursor = QtWidgets.QLabel("")
        self._lbl_cursor.setStyleSheet(
            "color: rgba(255,255,255,0.35); font-size: 11px;"
            " background: transparent; border: none;"
        )
        self._lbl_cursor.setFixedWidth(130)
        self._lbl_cursor.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        sbl.addWidget(self._lbl_cursor)

        self._status_bar = sb
        right.addWidget(sb)
        self.apply_theme()

    def _toggle_thumbnails(self):
        """Left-click on the sidebar toggle button: show thumbnails, or hide
        the panel if thumbnails are already showing."""
        if self._side_panel.isVisible() and self._side_mode == "thumbnails":
            self._side_panel.setVisible(False)
        else:
            self._show_side_panel("thumbnails")

    def _show_side_panel(self, mode: str):
        self._side_mode = mode
        self._side_stack.setCurrentIndex(0 if mode == "thumbnails" else 1)
        self._side_panel.setVisible(True)

    def _set_page_mode(self, mode: str):
        if self._page_mode == mode:
            return
        self._page_mode = mode
        self._rebuild_page_layout()
        self._go_to_page(self._current_page)

    def _show_sidebar_menu(self):
        """Right-click on the sidebar toggle button: Acrobat/Preview-style
        view menu (sidebar content + page layout mode)."""
        t = THEME_MGR.get()
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {t.bg_sidebar};
                border: 1px solid {t.bg_border};
                padding: 6px 0px;
            }}
            QMenu::item {{
                padding: 6px 30px 6px 18px;
                color: rgba(255,255,255,0.85);
                font-size: 13px;
            }}
            QMenu::item:selected {{ background: rgba(255,255,255,0.08); }}
            QMenu::item:disabled {{ color: rgba(255,255,255,0.32); }}
            QMenu::separator {{
                height: 1px; background: {t.bg_border}; margin: 6px 10px;
            }}
            QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}
        """)

        side_visible = self._side_panel.isVisible()

        act_thumbs = menu.addAction("Мініатюри")
        act_thumbs.setCheckable(True)
        act_thumbs.setChecked(side_visible and self._side_mode == "thumbnails")
        act_thumbs.triggered.connect(lambda: self._show_side_panel("thumbnails"))

        act_toc = menu.addAction("Зміст")
        act_toc.setCheckable(True)
        act_toc.setChecked(side_visible and self._side_mode == "toc")
        act_toc.triggered.connect(lambda: self._show_side_panel("toc"))

        for label in ("Виділення та нотатки", "Закладки", "Індексний аркуш"):
            menu.addAction(label).setEnabled(False)

        menu.addSeparator()

        act_cont = menu.addAction("Неперервне прокручування")
        act_cont.setCheckable(True)
        act_cont.setChecked(self._page_mode == "continuous")
        act_cont.triggered.connect(lambda: self._set_page_mode("continuous"))

        act_single = menu.addAction("Окрема сторінка")
        act_single.setCheckable(True)
        act_single.setChecked(self._page_mode == "single")
        act_single.triggered.connect(lambda: self._set_page_mode("single"))

        act_two = menu.addAction("Дві сторінки")
        act_two.setCheckable(True)
        act_two.setChecked(self._page_mode == "two")
        act_two.triggered.connect(lambda: self._set_page_mode("two"))

        menu.exec(self._thumb_toggle_btn.mapToGlobal(
            QtCore.QPoint(0, self._thumb_toggle_btn.height())))

    # ── theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self):
        t = THEME_MGR.get()

        # sidebar header (file name above thumbnails/TOC)
        self._side_header.setStyleSheet(
            f"background: {t.bg_sidebar}; border-bottom: 1px solid {t.bg_border};"
        )
        self._side_header_lbl.setStyleSheet(
            f"color: rgba(255,255,255,{t.statusbar_file_alpha / 255:.3f});"
            " font-size: 12px; font-weight: 600;"
            " background: transparent; border: none;"
        )

        # top toolbar background + border
        self._toolbar.setStyleSheet(f"background: {t.bg_sidebar};")
        self._toolbar_divider.setStyleSheet(f"background: {t.bg_border};")
        self._lbl_zoom.setStyleSheet(
            f"color: rgba(255,255,255,{t.statusbar_page_alpha / 255:.3f}); font-size: 12px;"
            " background: transparent; border: none;"
        )
        for btn in self._toolbar_buttons:
            btn.update()
        self._thumb_panel.apply_theme()
        self._toc_panel.apply_theme()
        self._search_box.apply_theme()

        # status bar background + border
        self._status_bar.setStyleSheet(
            f"QWidget {{ background: {t.bg_sidebar};"
            f" border-top: 1px solid {t.bg_border}; }}"
        )

        # status bar label colors
        fa = t.statusbar_file_alpha / 255
        pa = t.statusbar_page_alpha / 255
        ca = t.statusbar_cursor_alpha / 255
        self._lbl_file.setStyleSheet(
            f"color: rgba(255,255,255,{fa:.3f}); font-size: 12px;"
            " background: transparent; border: none;"
        )
        self._lbl_pages.setStyleSheet(
            f"color: rgba(255,255,255,{pa:.3f}); font-size: 12px;"
            " background: transparent; border: none;"
        )
        self._lbl_cursor.setStyleSheet(
            f"color: rgba(255,255,255,{ca:.3f}); font-size: 11px;"
            " background: transparent; border: none;"
        )

        # viewer scroll area + page container
        ha = min(1.0, t.scrollbar_alpha / 255)
        ha2 = min(1.0, ha * 2.1)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {t.viewer_bg}; border: none; }}
            QScrollBar:vertical {{
                width: 8px; background: transparent; border: none; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,{ha:.3f});
                border-radius: 4px; min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255,255,255,{ha2:.3f});
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            QScrollBar:horizontal {{
                height: 8px; background: transparent; border: none; margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(255,255,255,{ha:.3f});
                border-radius: 4px; min-width: 28px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: rgba(255,255,255,{ha2:.3f});
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        """)
        self._container.setStyleSheet(f"background: {t.viewer_bg};")

        # trigger repaint on pages (for selection color change)
        for pw in self._pages:
            pw.update()

    # ── pages ─────────────────────────────────────────────────────────────────

    def _clear_pages(self):
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._pages.clear()

    def _render_pages(self):
        self._clear_pages()
        if not self._doc:
            return
        for i in range(self._doc.page_count):
            page = self._doc.load_page(i)
            pw   = PageWidget(i, page, self._scale, rotation=self._view_rotation)
            pw.page_clicked.connect(self._on_page_clicked)
            pw.cursor_moved.connect(self._on_cursor_moved)
            pw.cursor_left.connect(self._on_cursor_left)

            shadow = QtWidgets.QGraphicsDropShadowEffect(pw)
            shadow.setBlurRadius(18)
            shadow.setOffset(2, 4)
            shadow.setColor(QtGui.QColor(0, 0, 0, 110))
            pw.setGraphicsEffect(shadow)

            self._pages.append(pw)

        self._rebuild_page_layout()

    def _on_page_clicked(self, source: PageWidget):
        for pw in self._pages:
            if pw is not source:
                pw.clear_selection()

    # ── page layout modes (continuous / single / two-up) ───────────────────────

    def _rebuild_page_layout(self):
        """Re-arrange the existing PageWidgets in self._vbox according to
        self._page_mode, without destroying/recreating them."""
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                if w not in self._pages:
                    w.deleteLater()

        if self._page_mode == "two":
            i = 0
            while i < len(self._pages):
                row = QtWidgets.QWidget()
                row_lay = QtWidgets.QHBoxLayout(row)
                row_lay.setContentsMargins(0, 0, 0, 0)
                row_lay.setSpacing(16)
                row_lay.addWidget(self._pages[i])
                if i + 1 < len(self._pages):
                    row_lay.addWidget(self._pages[i + 1])
                self._vbox.addWidget(row, alignment=QtCore.Qt.AlignHCenter)
                i += 2
        else:
            for pw in self._pages:
                self._vbox.addWidget(pw, alignment=QtCore.Qt.AlignHCenter)

        self._apply_page_visibility()
        self._vbox.activate()

    def _apply_page_visibility(self):
        if self._page_mode == "single":
            for i, pw in enumerate(self._pages):
                pw.setVisible(i == self._current_page)
        else:
            for pw in self._pages:
                pw.setVisible(True)

    def _scroll_anchor(self, page_num: int) -> QtWidgets.QWidget:
        """Widget whose .pos().y() should be used to scroll to page_num —
        the page itself, or its row wrapper in two-up mode."""
        pw     = self._pages[page_num]
        parent = pw.parentWidget()
        return pw if parent is self._container else parent

    def _go_to_page(self, page_num: int):
        if not self._pages or page_num < 0 or page_num >= len(self._pages):
            return
        self._current_page = page_num
        if self._page_mode == "single":
            self._apply_page_visibility()
            if self._doc:
                self._lbl_pages.setText(f"{page_num + 1}/{self._doc.page_count}")
            self._thumb_panel.set_current(page_num)
        else:
            anchor = self._scroll_anchor(page_num)
            self._scroll.verticalScrollBar().setValue(anchor.pos().y())

    # ── current page tracking ─────────────────────────────────────────────────

    def _update_current_page(self):
        if not self._pages or not self._doc or self._page_mode == "single":
            return
        vp_mid = (self._scroll.verticalScrollBar().value()
                  + self._scroll.viewport().height() / 2)
        best = 0
        last_anchor = None
        for i in range(len(self._pages)):
            anchor = self._scroll_anchor(i)
            if anchor is last_anchor:
                continue            # same row (two-up mode) — already counted
            last_anchor = anchor
            if anchor.pos().y() <= vp_mid:
                best = i
            else:
                break
        self._current_page = best
        self._lbl_pages.setText(f"{best + 1}/{self._doc.page_count}")
        self._thumb_panel.set_current(best)

    # ── cursor coordinates ────────────────────────────────────────────────────

    def _on_cursor_moved(self, page_num: int, pdf_x: float, pdf_y: float):
        self._lbl_cursor.setText(f"x {pdf_x:.1f}  y {pdf_y:.1f} pt")

    def _on_cursor_left(self):
        self._lbl_cursor.setText("")

    # ── zoom ──────────────────────────────────────────────────────────────────

    def _fit_scale(self) -> float:
        vw = self._scroll.viewport().width()
        if vw < 100:
            vw = 900
        if not self._doc:
            return _DEFAULT_SCALE
        pdf_w = max(self._doc.load_page(0).rect.width, 1.0)
        return max(0.2, (vw - 56) / pdf_w)

    def _zoom_in(self):
        self._apply_scale(self._scale * 1.25)

    def _zoom_out(self):
        self._apply_scale(self._scale / 1.25)

    def _zoom_fit(self):
        self._apply_scale(self._fit_scale())

    def _apply_scale(self, new_scale: float):
        new_scale = max(0.15, min(new_scale, 10.0))
        if abs(new_scale - self._scale) < 0.001:
            return
        self._scale = new_scale
        for pw in self._pages:
            pw.rescale(new_scale)
        self._update_zoom_label()

    def _update_zoom_label(self):
        self._lbl_zoom.setText(f"{round(self._scale / _SCALE_100 * 100)}%")

    # ── view rotation ─────────────────────────────────────────────────────────

    def _rotate_view(self):
        self._view_rotation = (self._view_rotation + 90) % 360
        for pw in self._pages:
            pw.set_rotation(self._view_rotation)
        self._rebuild_page_layout()

    # ── document info dialog ──────────────────────────────────────────────────

    def _show_info_dialog(self):
        if not self._doc:
            return
        t = THEME_MGR.get()
        meta = self._doc.metadata or {}
        size_bytes = os.path.getsize(self._path) if self._path and os.path.isfile(self._path) else 0
        if size_bytes >= 1_048_576:
            size_str = f"{size_bytes / 1_048_576:.1f} МБ"
        elif size_bytes >= 1024:
            size_str = f"{size_bytes / 1024:.0f} КБ"
        else:
            size_str = f"{size_bytes} Б"

        def _m(key):
            v = meta.get(key, "")
            return v.strip() if v else "—"

        rows = [
            ("Файл",          os.path.basename(self._path) if self._path else "—"),
            ("Сторінок",      str(self._doc.page_count)),
            ("Розмір",        size_str),
            ("Формат",        _m("format")),
            ("Заголовок",     _m("title")),
            ("Автор",         _m("author")),
            ("Тема",          _m("subject")),
            ("Творець",       _m("creator")),
            ("Продюсер",      _m("producer")),
            ("Дата створення",_m("creationDate")[:16].replace("D:", "") if meta.get("creationDate") else "—"),
        ]

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Властивості документа")
        dlg.setFixedWidth(440)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {t.bg_main}; }}
            QLabel  {{ color: rgba(255,255,255,0.85); font-size: 12px;
                       background: transparent; border: none; }}
        """)

        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(0)

        form = QtWidgets.QWidget()
        form.setStyleSheet("background: transparent;")
        fl = QtWidgets.QFormLayout(form)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setVerticalSpacing(8)
        fl.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        for label, value in rows:
            lbl_l = QtWidgets.QLabel(label + ":")
            lbl_l.setStyleSheet("color: rgba(255,255,255,0.45); font-size: 11px;"
                                " background: transparent; border: none;")
            lbl_v = QtWidgets.QLabel(value)
            lbl_v.setWordWrap(True)
            fl.addRow(lbl_l, lbl_v)

        lay.addWidget(form)
        lay.addSpacing(14)

        close_btn = QtWidgets.QPushButton("Закрити")
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.85);
                border: none; border-radius: 8px; font-size: 12px;
            }}
            QPushButton:hover  {{ background: rgba(255,255,255,0.14); }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.06); }}
        """)
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)

        dlg.exec()

    # ── text search ───────────────────────────────────────────────────────────

    @staticmethod
    def _search_page_ci(page: fitz.Page, query: str) -> list:
        """page.search_for() is case-sensitive for non-ASCII (e.g. Cyrillic)
        text, so query a few case variants and merge/dedupe the hits."""
        seen: set[tuple[float, float, float, float]] = set()
        results = []
        for variant in {query, query.lower(), query.upper(), query.capitalize()}:
            for r in page.search_for(variant):
                key = (round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1))
                if key not in seen:
                    seen.add(key)
                    results.append(r)
        return results

    def _run_search(self, query: str):
        self._search_query = query.strip()
        self._search_results = []
        if self._doc and self._search_query:
            for i in range(self._doc.page_count):
                page = self._doc.load_page(i)
                for r in self._search_page_ci(page, self._search_query):
                    self._search_results.append((i, (r.x0, r.y0, r.x1, r.y1)))
        self._search_current_idx = 0 if self._search_results else -1
        self._apply_search_highlights()
        if self._search_results:
            self._go_to_search_result(0, scroll=True)

    def _apply_search_highlights(self):
        by_page: dict[int, list[tuple[float, float, float, float]]] = {}
        for pi, rect in self._search_results:
            by_page.setdefault(pi, []).append(rect)
        cur_page, cur_rect = -1, None
        if 0 <= self._search_current_idx < len(self._search_results):
            cur_page, cur_rect = self._search_results[self._search_current_idx]
        for i, pw in enumerate(self._pages):
            pw.set_search_highlights(by_page.get(i, []),
                                     cur_rect if i == cur_page else None)

    def _go_to_search_result(self, idx: int, scroll: bool = True):
        if not self._search_results:
            return
        self._search_current_idx = idx % len(self._search_results)
        self._apply_search_highlights()
        if scroll:
            page_num, _rect = self._search_results[self._search_current_idx]
            self._go_to_page(page_num)

    def _search_next(self):
        if self._search_results:
            self._go_to_search_result(self._search_current_idx + 1)

    def _search_prev(self):
        if self._search_results:
            self._go_to_search_result(self._search_current_idx - 1)

    def _clear_search(self):
        self._search_query       = ""
        self._search_results     = []
        self._search_current_idx = -1
        for pw in self._pages:
            pw.set_search_highlights([], None)

    # ── print ─────────────────────────────────────────────────────────────────

    def print_document(self):
        if not self._doc:
            return
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._do_print(printer)

    def print_preview(self):
        if not self._doc:
            return
        from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        printer = QPrinter(QPrinter.HighResolution)
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self._do_print)
        preview.exec()

    def _do_print(self, printer):
        from PySide6.QtPrintSupport import QPrinter
        painter = QtGui.QPainter()
        if not painter.begin(printer):
            return
        page_rect = printer.pageRect(QPrinter.DevicePixel).toRect()
        for i, pw in enumerate(self._pages):
            if i > 0:
                printer.newPage()
            if pw.pixmap:
                scaled = pw.pixmap.scaled(
                    page_rect.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
                x = (page_rect.width()  - scaled.width())  // 2
                y = (page_rect.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
        painter.end()

    # ── events ────────────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
                u.toLocalFile().lower().endswith(".pdf")
                for u in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.toLocalFile().lower().endswith(".pdf")]
        if paths:
            self.load_pdf(paths[0])
            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_nav_key(self, key: int) -> bool:
        n = len(self._pages)
        if key == QtCore.Qt.Key_Home:
            self._go_to_page(0)
        elif key == QtCore.Qt.Key_End:
            self._go_to_page(n - 1)
        elif key == QtCore.Qt.Key_PageDown:
            self._go_to_page(min(self._current_page + 1, n - 1))
        elif key == QtCore.Qt.Key_PageUp:
            self._go_to_page(max(self._current_page - 1, 0))
        else:
            return False
        return True

    def eventFilter(self, obj, event):
        if obj is self._scroll.viewport():
            t = event.type()
            if t == QtCore.QEvent.Wheel and event.modifiers() & QtCore.Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    self._zoom_in()
                else:
                    self._zoom_out()
                return True
            elif t == QtCore.QEvent.NativeGesture:
                if event.gestureType() == QtCore.Qt.ZoomNativeGesture:
                    self._apply_scale(self._scale * (1.0 + event.value()))
                    return True
            elif t == QtCore.QEvent.KeyPress:
                if self._handle_nav_key(event.key()):
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        key = event.key()
        if event.modifiers() & QtCore.Qt.ControlModifier:
            if key == QtCore.Qt.Key_C:
                for pw in self._pages:
                    if pw.selected_text:
                        QtWidgets.QApplication.clipboard().setText(pw.selected_text)
                        break
            elif key == QtCore.Qt.Key_A:
                if self._doc:
                    parts = [
                        self._doc.load_page(i).get_text("text")
                        for i in range(self._doc.page_count)
                    ]
                    QtWidgets.QApplication.clipboard().setText("\n".join(parts))
        elif not self._handle_nav_key(key):
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._doc and not self._pages:
            self._scale = self._fit_scale()
            self._render_pages()


# ── Tabbed viewer (browser-style tabs, one per open PDF) ───────────────────────

def _blend(c1: QtGui.QColor, c2: QtGui.QColor, t: float) -> QtGui.QColor:
    t = max(0.0, min(1.0, t))
    return QtGui.QColor(
        int(c1.red()   + (c2.red()   - c1.red())   * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue()  + (c2.blue()  - c1.blue())  * t),
    )


class _FileTabBar(QtWidgets.QTabBar):
    """Fully custom-painted tab bar — bypasses the native Windows style entirely
    (it ignores most QSS on QTabBar), matching the rest of the app's
    custom-painted widgets (NavButton, DropZone, ...).
    """

    _TAB_H      = 34
    _PREF_W     = 200   # natural width while there's room
    _MIN_W      = 64    # floor width once tabs must squeeze to fit
    _PLUS_W     = 30
    _RADIUS     = 8
    _PAD_L      = 12
    _CLOSE_SZ   = 14
    _CLOSE_GAP  = 8
    _PAD_R      = 10
    _SWAP_OVERLAP = 0.60   # swap as soon as the dragged tab has covered this much of a neighbor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setMovable(False)   # we drive dragging ourselves for the overlap slide effect
        self.setCursor(QtCore.Qt.PointingHandCursor)
        # native styles reserve a few px of margin around tabs beyond tabSizeHint,
        # which left a thin bar_bg sliver below the tab shapes — pin the bar's own
        # height so there's nothing left uncovered between tabs and the content below
        self.setFixedHeight(self._TAB_H)
        self._hover_progress: dict[int, float] = {}
        self._hovered_index = -1
        self._close_rects: dict[int, QtCore.QRect] = {}
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick)
        self.tabMoved.connect(self._keep_plus_last)

        self._drag_idx = -1
        self._drag_offset = 0.0
        self._press_x = 0.0

    # ── sizing ────────────────────────────────────────────────────────────────

    def _real_count(self) -> int:
        return sum(1 for i in range(self.count()) if self.tabData(i) != "plus")

    def tabSizeHint(self, index):
        if self.tabData(index) == "plus":
            return QtCore.QSize(self._PLUS_W, self._TAB_H)
        n = self._real_count()
        available = max(0, self.width() - self._PLUS_W)
        even_w = available / n if n else self._PREF_W
        w = max(self._MIN_W, min(self._PREF_W, even_w))
        return QtCore.QSize(int(w), self._TAB_H)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # tab widths are a function of bar width (shrink-to-fit) — force relayout
        self.updateGeometry()
        self.update()

    # ── keep the "+" tab pinned to the end when reordering ───────────────────

    def _keep_plus_last(self, *_):
        for i in range(self.count() - 1):
            if self.tabData(i) == "plus":
                self.moveTab(i, self.count() - 1)
                break

    # ── hover tracking / animation ───────────────────────────────────────────

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        idx = self.tabAt(pos)
        if idx != self._hovered_index:
            self._hovered_index = idx
            self._anim_timer.start()

        if self._drag_idx != -1:
            self._drag_offset = pos.x() - self._press_x
            self._maybe_swap()
            self._clamp_drag_offset()
            self.update()
            return
        super().mouseMoveEvent(event)

    def _clamp_drag_offset(self):
        rect = self.tabRect(self._drag_idx)
        left_bound = 0
        right_bound = self.width() - self._PLUS_W
        min_offset = left_bound - rect.x()
        max_offset = right_bound - rect.right()
        self._drag_offset = max(min_offset, min(max_offset, self._drag_offset))

    def leaveEvent(self, event):
        self._hovered_index = -1
        self._anim_timer.start()
        super().leaveEvent(event)

    def _tick(self):
        settled = True
        for i in range(self.count()):
            target = 1.0 if i == self._hovered_index else 0.0
            cur = self._hover_progress.get(i, 0.0)
            if abs(cur - target) > 0.01:
                cur += (target - cur) * 0.35
                self._hover_progress[i] = cur
                settled = False
            elif cur != target:
                self._hover_progress[i] = target
        self.update()
        if settled:
            self._anim_timer.stop()

    # ── mouse press / release (close-button hit test + custom drag-reorder) ──

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            idx = self.tabAt(event.pos())
            rect = self._close_rects.get(idx)
            if rect and rect.contains(event.pos()) and self.tabData(idx) != "plus":
                self.tabCloseRequested.emit(idx)
                return
            if idx != -1 and self.tabData(idx) != "plus":
                self.setCurrentIndex(idx)
                self._drag_idx = idx
                self._press_x = event.position().toPoint().x()
                self._drag_offset = 0.0
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_idx != -1:
            self._drag_idx = -1
            self._drag_offset = 0.0
            self.update()
            return
        super().mouseReleaseEvent(event)

    def _tab_draw_rect(self, index: int) -> QtCore.QRect:
        rect = self.tabRect(index)
        if index == self._drag_idx and self._drag_offset:
            rect = rect.translated(int(self._drag_offset), 0)
        return rect

    def _maybe_swap(self):
        # _drag_offset is recomputed every move from (mouse_x - _press_x). After a swap the
        # dragged tab's nominal slot jumps by the neighbor's width, so _press_x must absorb
        # that jump too — otherwise next frame's offset is computed against a stale reference
        # and the tab "teleports", cascading swaps all the way to one end of the bar.
        cur = self._drag_idx
        rect = self.tabRect(cur)
        w = rect.width()
        visual_left = rect.x() + self._drag_offset

        if cur > 0 and self.tabData(cur - 1) != "plus":
            left_rect = self.tabRect(cur - 1)
            overlap = left_rect.right() - visual_left   # how far we've crossed into the left neighbor
            if overlap > w * self._SWAP_OVERLAP:
                shift = rect.x() - left_rect.x()
                self.moveTab(cur, cur - 1)
                self._drag_idx = cur - 1
                self._drag_offset += shift
                self._press_x -= shift
                return

        n_real = self._real_count()
        if cur < n_real - 1:
            right_rect = self.tabRect(cur + 1)
            overlap = (visual_left + w) - right_rect.x()   # how far we've crossed into the right neighbor
            if overlap > w * self._SWAP_OVERLAP:
                shift = right_rect.x() - rect.x()
                self.moveTab(cur, cur + 1)
                self._drag_idx = cur + 1
                self._drag_offset -= shift
                self._press_x += shift
                return

    # ── painting ──────────────────────────────────────────────────────────────

    @staticmethod
    def _rounded_top_path(rect: QtCore.QRect, radius: int) -> QtGui.QPainterPath:
        r = QtCore.QRectF(rect)
        path = QtGui.QPainterPath()
        path.moveTo(r.left(), r.bottom())
        path.lineTo(r.left(), r.top() + radius)
        path.quadTo(r.left(), r.top(), r.left() + radius, r.top())
        path.lineTo(r.right() - radius, r.top())
        path.quadTo(r.right(), r.top(), r.right(), r.top() + radius)
        path.lineTo(r.right(), r.bottom())
        path.closeSubpath()
        return path

    def _paint_tab_content(self, p: QtGui.QPainter, i: int, rect: QtCore.QRect,
                            selected: bool, hover: float) -> None:
        if self.tabData(i) == "plus":
            alpha = 0.55 + 0.35 * hover
            p.setPen(QtGui.QColor(255, 255, 255, int(255 * alpha)))
            font = self.font()
            font.setPixelSize(15)
            font.setWeight(QtGui.QFont.DemiBold)
            p.setFont(font)
            p.drawText(rect, QtCore.Qt.AlignCenter, "+")
            return

        close_rect = QtCore.QRect(
            rect.right() - self._PAD_R - self._CLOSE_SZ,
            rect.center().y() - self._CLOSE_SZ // 2,
            self._CLOSE_SZ, self._CLOSE_SZ,
        )
        self._close_rects[i] = close_rect

        text_rect = QtCore.QRect(
            rect.left() + self._PAD_L, rect.top(),
            close_rect.left() - self._CLOSE_GAP - (rect.left() + self._PAD_L),
            rect.height(),
        )
        text_alpha = 0.95 if selected else (0.80 + 0.15 * hover)
        p.setPen(QtGui.QColor(255, 255, 255, int(255 * text_alpha)))
        font = self.font()
        font.setWeight(QtGui.QFont.DemiBold if selected else QtGui.QFont.Normal)
        p.setFont(font)
        fm = QtGui.QFontMetrics(font)
        elided = fm.elidedText(self.tabText(i), QtCore.Qt.ElideRight, max(0, text_rect.width()))
        p.drawText(text_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, elided)

        close_alpha = 0.85 if selected else (0.55 + 0.30 * hover)
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, int(255 * close_alpha)), 1.4)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        m = 4
        cr = close_rect.adjusted(m, m, -m, -m)
        p.drawLine(cr.topLeft(), cr.bottomRight())
        p.drawLine(cr.topRight(), cr.bottomLeft())

    def paintEvent(self, event):
        t = THEME_MGR.get()
        # bar/inactive sit a step above bg_sidebar but clearly below viewer_bg, so the active
        # tab (flat viewer_bg — the actual color behind the page thumbnails) reads as the
        # highlighted one and flows seamlessly into the document area beneath it
        bar_bg = QtGui.QColor(t.bg_sidebar).lighter(115)
        active_bg = QtGui.QColor(t.viewer_bg)
        inactive_bg = bar_bg
        hover_bg = QtGui.QColor(t.bg_sidebar).lighter(140)

        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.fillRect(self.rect(), bar_bg)

        selected_idx = self.currentIndex()
        self._close_rects.clear()

        # layers 1+2: every non-selected tab — background, then its own text/close — fully
        # under the selected tab so nothing of theirs can show through it
        for i in range(self.count()):
            if i == selected_idx:
                continue
            rect = self._tab_draw_rect(i)
            if not rect.isValid():
                continue
            hover = self._hover_progress.get(i, 0.0)
            p.fillPath(self._rounded_top_path(rect, self._RADIUS), _blend(inactive_bg, hover_bg, hover))
            self._paint_tab_content(p, i, rect, False, hover)

        # layers 3+4: the selected (possibly dragged) tab, painted as one opaque unit on top
        # of everything else — background bleeds into neighbors by one radius so its rounded
        # corners overlap theirs (otherwise the two curves leave a notch of bar_bg showing
        # through at the seam), and while dragging this rect is already offset, so the tab
        # visually slides and fully covers whatever neighbor it overlaps (no see-through text)
        if 0 <= selected_idx < self.count():
            rect = self._tab_draw_rect(selected_idx)
            if rect.isValid():
                hover = self._hover_progress.get(selected_idx, 0.0)
                bleed = rect.adjusted(-self._RADIUS, 0, self._RADIUS, 0)
                p.fillPath(self._rounded_top_path(bleed, self._RADIUS), active_bg)
                self._paint_tab_content(p, selected_idx, rect, True, hover)
        p.end()


class PdfViewerTabs(QtWidgets.QWidget):
    """Holds one ScreenViewer per open PDF, switchable via a browser-style tab bar.

    The "+" control is a real, permanent last tab (no close button) rather than
    a corner widget, so it sits flush against the last document tab instead of
    floating at the far edge of the bar. The tab bar is custom-painted (see
    _FileTabBar) since the native Windows style largely ignores QSS on QTabBar.
    """

    all_closed = QtCore.Signal()   # emitted when the last document tab is closed

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setTabBar(_FileTabBar())
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(False)   # close glyph is custom-painted/hit-tested
        # movability is set on the bar itself (_FileTabBar.__init__) — don't override it here
        self._tabs.tabBar().tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_current_changed)
        root.addWidget(self._tabs)

        self._add_plus_tab()

    # ── public API ────────────────────────────────────────────────────────────

    def add_tab(self, path: str):
        for i in range(self._plus_index()):
            if self._tabs.widget(i)._path == path:
                self._tabs.setCurrentIndex(i)
                return
        viewer = ScreenViewer()
        viewer.setAcceptDrops(False)   # adding files goes through the "+" tab / drop zone
        viewer.load_pdf(path)
        idx = self._tabs.insertTab(self._plus_index(), viewer, os.path.basename(path))
        self._tabs.setTabToolTip(idx, path)
        self._tabs.setCurrentIndex(idx)

    def reset(self):
        while self._tabs.count() > 1:   # keep the trailing "+" tab
            w = self._tabs.widget(0)
            self._tabs.removeTab(0)
            w.close_doc()
            w.deleteLater()

    def paths(self) -> list[str]:
        return [self._tabs.widget(i)._path for i in range(self._plus_index())]

    def current_viewer(self) -> ScreenViewer | None:
        w = self._tabs.currentWidget()
        return w if isinstance(w, ScreenViewer) else None

    def apply_theme(self):
        t = THEME_MGR.get()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {t.viewer_bg}; top: -1px; }}
            QTabBar QToolButton {{
                background: {t.bg_hover};
                border: none;
                border-radius: 5px;
                min-width: 28px;
                min-height: 28px;
                margin: 2px 3px;
            }}
            QTabBar QToolButton:hover {{ background: {t.bg_border}; }}
            QTabBar QToolButton:pressed {{ background: {t.accent}; }}
            QTabBar QToolButton::left-arrow {{ image: none; border-right: 6px solid white; border-top: 5px solid transparent; border-bottom: 5px solid transparent; width: 0; height: 0; }}
            QTabBar QToolButton::right-arrow {{ image: none; border-left: 6px solid white; border-top: 5px solid transparent; border-bottom: 5px solid transparent; width: 0; height: 0; }}
        """)
        self._tabs.tabBar().update()
        for i in range(self._plus_index()):
            self._tabs.widget(i).apply_theme()

    # ── internals ─────────────────────────────────────────────────────────────

    def _plus_index(self) -> int:
        return self._tabs.count() - 1

    def _add_plus_tab(self):
        idx = self._tabs.addTab(QtWidgets.QWidget(), "+")
        self._tabs.setTabToolTip(idx, "Відкрити ще один PDF")
        self._tabs.tabBar().setTabData(idx, "plus")

    def _close_tab(self, index: int):
        if index == self._plus_index():
            return
        w = self._tabs.widget(index)
        self._tabs.removeTab(index)
        w.close_doc()
        w.deleteLater()
        if self._tabs.count() == 1:   # only the "+" tab is left
            self.all_closed.emit()

    def _on_current_changed(self, index: int):
        if index != self._plus_index() or self._tabs.count() <= 1:
            return
        self._tabs.blockSignals(True)
        self._tabs.setCurrentIndex(index - 1)
        self._tabs.blockSignals(False)
        self._on_add_clicked()

    def _on_add_clicked(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Відкрити PDF", "", "PDF files (*.pdf)"
        )
        for p in paths:
            self.add_tab(p)
