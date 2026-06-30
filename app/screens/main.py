import os
import json
from PySide6 import QtWidgets, QtCore, QtGui

from .merge import ScreenMergeMulti
from .viewer import ScreenViewer
from ..word_editor import WordEditor
from ..theme import THEME_MGR
from .. import icons as _icons
from ..widgets import _HoverMixin

SIDEBAR_EXPANDED  = 210
SIDEBAR_COLLAPSED = 62

_SIDEBAR_TOGGLE_BTN_SS = """
    QPushButton {
        border: none;
        background: transparent;
        color: rgba(255,255,255,0.85);
        font-size: 14px;
        font-weight: 600;
        text-align: left;
        padding-left: 18px;
        letter-spacing: 0.3px;
    }
    QPushButton:hover { background: rgba(255,255,255,0.05); }
"""

# ── Sidebar nav button ────────────────────────────────────────────────────────

class NavButton(_HoverMixin, QtWidgets.QAbstractButton):

    def __init__(self, icon_text, label, parent=None):
        super().__init__(parent)
        self._icon      = icon_text
        self._label     = label
        self._active    = False
        self._collapsed = False
        self.setFixedHeight(52)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Fixed)
        self._init_hover()

    def set_active(self, v: bool):
        self._active = v
        self.update()

    def set_collapsed(self, v: bool):
        self._collapsed = v
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect()
        t = THEME_MGR.get()

        if self._active:
            p.setPen(QtCore.Qt.NoPen)
            bg = QtGui.QColor(t.nav_active_bg)
            bg.setAlpha(t.nav_active_bg_alpha)
            p.setBrush(bg)
            p.drawRoundedRect(r.adjusted(4, 2, -4, -2), 8, 8)
        elif self._hover:
            p.setPen(QtCore.Qt.NoPen)
            bg = QtGui.QColor(t.nav_hover_bg)
            bg.setAlpha(t.nav_hover_bg_alpha)
            p.setBrush(bg)
            p.drawRoundedRect(r.adjusted(4, 2, -4, -2), 8, 8)

        icon_color = QtGui.QColor(
            t.nav_icon_active_color if self._active else t.nav_icon_inactive_color
        )
        icon_color.setAlpha(
            t.nav_icon_active_alpha if self._active else t.nav_icon_inactive_alpha
        )
        icon_sz = t.icon_size
        icon_cx = SIDEBAR_COLLAPSED / 2.0
        icon_cy = r.height() / 2.0
        icon_rf = QtCore.QRectF(icon_cx - icon_sz / 2, icon_cy - icon_sz / 2,
                                icon_sz, icon_sz)
        if _icons.is_icon(self._icon):
            _icons.draw(p, icon_rf, self._icon, icon_color)
        else:
            font = _icons.sf_font(18)
            p.setFont(font)
            p.setPen(icon_color)
            p.drawText(QtCore.QRect(0, 0, SIDEBAR_COLLAPSED, r.height()),
                       QtCore.Qt.AlignCenter, self._icon)

        if not self._collapsed:
            label_r = QtCore.QRect(SIDEBAR_COLLAPSED, 0,
                                   r.width() - SIDEBAR_COLLAPSED - 10, r.height())
            font2 = _icons.sf_font(13, QtGui.QFont.DemiBold if self._active
                                   else QtGui.QFont.Normal)
            p.setFont(font2)
            lc = QtGui.QColor(
                t.nav_label_active_color if self._active else t.nav_label_inactive_color
            )
            lc.setAlpha(
                t.nav_label_active_alpha if self._active else t.nav_label_inactive_alpha
            )
            p.setPen(lc)
            p.drawText(label_r,
                       QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft | QtCore.Qt.TextWordWrap,
                       self._label)
        p.end()


# ── Drill-down panel (Windows Explorer folder navigation) ─────────────────────

class _BackHeader(_HoverMixin, QtWidgets.QAbstractButton):
    """Top row of a sub-page: ← arrow + folder title. Click to go back."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self.setFixedHeight(52)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Fixed)
        self._init_hover()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect()
        t = THEME_MGR.get()

        if self._hover:
            p.setPen(QtCore.Qt.NoPen)
            bg = QtGui.QColor(t.nav_hover_bg)
            bg.setAlpha(t.nav_hover_bg_alpha)
            p.setBrush(bg)
            p.drawRoundedRect(r.adjusted(4, 2, -4, -2), 8, 8)

        # ← arrow
        ax  = 20.0
        ay  = r.height() / 2.0
        aw  = 6.0
        ac  = QtGui.QColor(t.nav_label_inactive_color)
        ac.setAlpha(t.nav_label_inactive_alpha)
        arrow_pen = QtGui.QPen(ac, 1.8, QtCore.Qt.SolidLine,
                               QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        p.setPen(arrow_pen)
        p.drawLine(QtCore.QPointF(ax - aw * 0.5, ay),
                   QtCore.QPointF(ax + aw * 0.5, ay))
        p.drawLine(QtCore.QPointF(ax - aw * 0.5, ay),
                   QtCore.QPointF(ax - aw * 0.5 + aw * 0.5, ay - aw * 0.5))
        p.drawLine(QtCore.QPointF(ax - aw * 0.5, ay),
                   QtCore.QPointF(ax - aw * 0.5 + aw * 0.5, ay + aw * 0.5))

        # Title
        title_r = QtCore.QRect(38, 0, r.width() - 46, r.height())
        p.setFont(_icons.sf_font(13, QtGui.QFont.DemiBold))
        tc = QtGui.QColor(t.nav_label_active_color)
        tc.setAlpha(t.nav_label_active_alpha)
        p.setPen(tc)
        p.drawText(title_r, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self._title)
        p.end()


class _SubPageNavButton(_HoverMixin, QtWidgets.QAbstractButton):
    """Full-width nav button inside a sub-page (no icon, indented label)."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self.setFixedHeight(50)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Fixed)
        self._init_hover()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect()
        t = THEME_MGR.get()

        if self._hover:
            p.setPen(QtCore.Qt.NoPen)
            bg = QtGui.QColor(t.nav_hover_bg)
            bg.setAlpha(t.nav_hover_bg_alpha)
            p.setBrush(bg)
            p.drawRoundedRect(r.adjusted(4, 2, -4, -2), 8, 8)

        # Small bullet
        INDENT = 24
        p.setPen(QtCore.Qt.NoPen)
        bullet_c = QtGui.QColor(t.nav_icon_inactive_color)
        bullet_c.setAlpha(t.nav_icon_active_alpha if self._hover
                          else t.nav_icon_inactive_alpha)
        p.setBrush(bullet_c)
        p.drawEllipse(QtCore.QPointF(INDENT, r.height() / 2.0), 2.5, 2.5)

        # Label
        label_r = QtCore.QRect(INDENT + 14, 0, r.width() - INDENT - 22, r.height())
        p.setFont(_icons.sf_font(13))
        lc = QtGui.QColor(t.nav_label_active_color if self._hover
                          else t.nav_label_inactive_color)
        lc.setAlpha(t.nav_label_active_alpha if self._hover
                    else t.nav_label_inactive_alpha)
        p.setPen(lc)
        p.drawText(label_r, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self._label)
        p.end()


class DrillDownPanel(QtWidgets.QWidget):
    """Right-sidebar panel with Windows Explorer-style drill-down navigation.

    Main page lists items; clicking a folder item replaces the view with
    a sub-page showing ← Back header + full sub-item rows.
    """

    def __init__(self, on_folder_open=None, parent=None):
        super().__init__(parent)
        self._on_folder_open = on_folder_open
        self.setStyleSheet("background: transparent;")
        self._nav_buttons: list[NavButton] = []

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        root.addWidget(self._stack)

        # Main page
        self._main_page = QtWidgets.QWidget()
        self._main_page.setStyleSheet("background: transparent;")
        self._main_lay  = QtWidgets.QVBoxLayout(self._main_page)
        self._main_lay.setContentsMargins(0, 0, 0, 0)
        self._main_lay.setSpacing(0)
        self._main_lay.addStretch()
        self._stack.addWidget(self._main_page)

    # ── public API ────────────────────────────────────────────────────────────

    def add_action(self, icon: str, label: str, callback) -> NavButton:
        btn = NavButton(icon, label)
        btn.clicked.connect(callback)
        self._insert_main(btn)
        self._nav_buttons.append(btn)
        return btn

    def add_folder(self, icon: str, label: str,
                   sub_items: list[tuple[str, object]]) -> NavButton:
        """Register a folder item; clicking it pushes the sub-page."""
        sub_page = self._build_sub_page(label, sub_items)
        sub_idx  = self._stack.addWidget(sub_page)

        btn = NavButton(icon, label)
        btn.clicked.connect(lambda: self._push(sub_idx))
        self._insert_main(btn)
        self._nav_buttons.append(btn)
        return btn

    @property
    def nav_buttons(self) -> list[NavButton]:
        return self._nav_buttons

    # ── internals ─────────────────────────────────────────────────────────────

    def _insert_main(self, widget: QtWidgets.QWidget):
        """Insert before the trailing stretch."""
        self._main_lay.insertWidget(self._main_lay.count() - 1, widget)

    def _build_sub_page(self, title: str,
                        sub_items: list[tuple[str, object]]) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        page.setStyleSheet("background: transparent;")
        lay  = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        back = _BackHeader(title)
        back.clicked.connect(lambda: self._push(0))
        lay.addWidget(back)

        div = QtWidgets.QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #252830; border: none;")
        lay.addWidget(div)
        lay.addSpacing(6)

        for lbl, cb in sub_items:
            btn = _SubPageNavButton(lbl)
            btn.clicked.connect(cb)
            lay.addWidget(btn)

        lay.addStretch()
        return page

    def _push(self, idx: int):
        if idx != 0 and self._on_folder_open:
            self._on_folder_open()
        self._stack.setCurrentIndex(idx)

    def reset(self):
        self._stack.setCurrentIndex(0)


# ── Drop zone ─────────────────────────────────────────────────────────────────

class DropZone(QtWidgets.QWidget):

    file_chosen = QtCore.Signal(list)

    def __init__(self, hint_text="Перетягни файл сюди або натисни, щоб вибрати",
                 extensions=None, dialog_filter="Усі файли (*)", parent=None):
        super().__init__(parent)
        self._hint_text     = hint_text
        self._extensions    = tuple(ext.lower() for ext in extensions) if extensions else None
        self._dialog_filter = dialog_filter
        self.setAcceptDrops(True)
        self._hover      = False
        self._press      = False
        self._drag_pulse = 0.0
        self.setCursor(QtCore.Qt.PointingHandCursor)

        self._drag_anim = QtCore.QVariantAnimation(self)
        self._drag_anim.setDuration(1200)
        self._drag_anim.setKeyValueAt(0.0, 0.3)
        self._drag_anim.setKeyValueAt(0.5, 1.0)
        self._drag_anim.setKeyValueAt(1.0, 0.3)
        self._drag_anim.setLoopCount(-1)
        self._drag_anim.valueChanged.connect(self._on_drag_pulse)

    def _on_drag_pulse(self, v):
        self._drag_pulse = float(v)
        self.update()

    def _button_rect(self) -> QtCore.QRectF:
        size = min(min(self.width(), self.height()) * 0.42, 260.0)
        cx   = self.width()  / 2
        cy   = self.height() / 2 - 24
        return QtCore.QRectF(cx - size / 2, cy - size / 2, size, size)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self._button_rect()
        size = rect.width()
        cx   = rect.center().x()
        cy   = rect.center().y()

        accent = THEME_MGR.get().accent
        if self._hover and self._drag_pulse > 0:
            overlay = QtGui.QColor(accent)
            overlay.setAlphaF(0.07 * self._drag_pulse)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(overlay)
            p.drawRect(self.rect())

        if self._hover:
            border_color = QtGui.QColor(accent)
            border_color.setAlphaF(0.5 + 0.5 * self._drag_pulse)
            icon_color   = QtGui.QColor(accent)
            pen_w        = 2.0 + self._drag_pulse * 0.5
        elif self._press:
            border_color = QtGui.QColor(accent)
            icon_color   = QtGui.QColor(accent)
            pen_w        = 2.5
        else:
            border_color = QtGui.QColor(160, 165, 180)
            icon_color   = QtGui.QColor(160, 165, 180)
            pen_w        = 2.0

        if self._press:
            p.save()
            p.translate(cx, cy)
            p.scale(0.96, 0.96)
            p.translate(-cx, -cy)

        pen = QtGui.QPen(border_color, pen_w, QtCore.Qt.DashLine)
        pen.setDashPattern([8, 5])
        p.setPen(pen)
        fill_alpha = 30 if self._press else (10 if self._hover else 4)
        p.setBrush(QtGui.QColor(255, 255, 255, fill_alpha))
        p.drawRoundedRect(rect, 22, 22)

        font = QtGui.QFont()
        font.setPixelSize(int(size * 0.28))
        font.setWeight(QtGui.QFont.Light)
        p.setFont(font)
        p.setPen(icon_color)
        p.drawText(rect, QtCore.Qt.AlignCenter, "+")

        if self._press:
            p.restore()

        text_rect = QtCore.QRectF(cx - 220, cy + size / 2 + 14, 440, 60)
        font2 = QtGui.QFont()
        font2.setPixelSize(13)
        p.setFont(font2)
        if self._hover:
            p.setPen(QtGui.QColor(THEME_MGR.get().accent))
            p.drawText(text_rect, QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter,
                       "Відпусти файл тут")
        else:
            p.setPen(QtGui.QColor(140, 145, 160))
            p.drawText(text_rect, QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter,
                       self._hint_text)
        p.end()

    def mousePressEvent(self, event):
        if (event.button() == QtCore.Qt.LeftButton
                and self._button_rect().contains(QtCore.QPointF(event.pos()))):
            self._press = True
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._press:
            self._press = False
            self.update()
            if self._button_rect().contains(QtCore.QPointF(event.pos())):
                paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                    self, "Виберіть файл(и)", "", self._dialog_filter
                )
                if paths:
                    self.file_chosen.emit(paths)

    def _accepts(self, local_path: str) -> bool:
        if self._extensions is None:
            return True
        lo = local_path.lower()
        return any(lo.endswith(ext) for ext in self._extensions)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(self._accepts(u.toLocalFile()) for u in urls):
                self._hover = True
                self._drag_anim.start()
                self.update()
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._hover = False
        self._drag_anim.stop()
        self._drag_pulse = 0.0
        self.update()

    def dropEvent(self, event):
        self._hover = False
        self._drag_anim.stop()
        self._drag_pulse = 0.0
        self.update()
        paths = [u.toLocalFile() for u in event.mimeData().urls()
                 if self._accepts(u.toLocalFile())]
        if paths:
            self.file_chosen.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


# ── Coming soon placeholder ───────────────────────────────────────────────────

class ComingSoonWidget(QtWidgets.QWidget):

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self._label = label

    def set_label(self, label):
        self._label = label
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        font = QtGui.QFont()
        font.setPixelSize(18)
        p.setFont(font)
        p.setPen(QtGui.QColor(120, 125, 140))
        p.drawText(self.rect(), QtCore.Qt.AlignCenter,
                   f"{self._label}\n\nСкоро буде доступно")
        p.end()


# ── Main screen ───────────────────────────────────────────────────────────────

class ScreenMain(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self._right_collapsed = False
        self._current_format  = "none"    # 'none' | 'pdf' | 'word' | 'unsupported'
        self._current_path    = None
        self._pdf_scenario    = "viewer"  # 'viewer' | 'editor' — meaningful when format == 'pdf'
        self._all_right_btns  = []   # all NavButtons across all right-panel pages
        self._theme_dividers: list[QtWidgets.QFrame] = []

        self.setWindowTitle("TDTool")
        self.resize(1250, 720)
        self.setStyleSheet("background: #21232a;")

        self._build_ui()
        self._right_sidebar.setVisible(False)
        THEME_MGR.add_listener(self._apply_theme)
        self._apply_theme()
        self._load_window_state()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_workspace(), 1)
        root.addWidget(self._make_right_sidebar())

        self._ranim = QtCore.QPropertyAnimation(self._right_sidebar, b"minimumWidth")
        self._ranim.setDuration(220)
        self._ranim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        self._ranim.valueChanged.connect(
            lambda v: self._right_sidebar.setMaximumWidth(int(v))
        )

    def _make_workspace(self):
        self._stack = QtWidgets.QStackedWidget()
        self._stack.setStyleSheet("background: #21232a;")

        # Universal drop zone — accepts any file; format is detected after drop
        self._drop_zone = DropZone()
        self._drop_zone.file_chosen.connect(self._on_file_chosen)
        self._stack.addWidget(self._drop_zone)

        # PDF viewer
        self._viewer = ScreenViewer()
        self._stack.addWidget(self._viewer)

        # Unified PDF editor (merge/split)
        self._merge = ScreenMergeMulti(self._on_new_file)
        self._stack.addWidget(self._merge)

        # Word editor
        self._word_editor = WordEditor()
        self._stack.addWidget(self._word_editor)

        # Generic placeholder for not-yet-supported formats
        self._coming_soon = ComingSoonWidget("")
        self._stack.addWidget(self._coming_soon)

        return self._stack

    def _make_right_sidebar(self):
        self._right_sidebar = QtWidgets.QFrame()
        self._right_sidebar.setObjectName("right_sidebar")
        self._right_sidebar.setFixedWidth(SIDEBAR_EXPANDED)
        self._right_sidebar.setStyleSheet("""
            QFrame#right_sidebar {
                background: #191b21;
                border-left: 1px solid #2a3045;
            }
        """)

        lay = QtWidgets.QVBoxLayout(self._right_sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._right_toggle_btn = QtWidgets.QPushButton("☰   Інструменти")
        self._right_toggle_btn.setFixedHeight(56)
        self._right_toggle_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._right_toggle_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._right_toggle_btn.setStyleSheet(_SIDEBAR_TOGGLE_BTN_SS)
        self._right_toggle_btn.clicked.connect(self._toggle_right_sidebar)
        lay.addWidget(self._right_toggle_btn)

        div = QtWidgets.QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #252830;")
        self._theme_dividers.append(div)
        lay.addWidget(div)
        lay.addSpacing(10)

        # ── context tool stack (format-aware) ──────────────────────────────────
        self._right_tool_stack = QtWidgets.QStackedWidget()
        self._right_tool_stack.setStyleSheet("background: transparent;")

        self._right_tool_stack.addWidget(QtWidgets.QWidget())             # 0: no file loaded
        self._right_tool_stack.addWidget(self._make_pdf_tools())          # 1: pdf
        self._right_tool_stack.addWidget(self._make_word_tools())         # 2: word
        self._right_tool_stack.addWidget(self._make_unsupported_tools())  # 3: unsupported

        lay.addWidget(self._right_tool_stack, 1)

        div2 = QtWidgets.QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet("background: #252830;")
        self._theme_dividers.append(div2)
        lay.addWidget(div2)

        self._help_btn = NavButton("?", "Довідка")
        self._help_btn.clicked.connect(lambda: self._merge._show_help())
        self._all_right_btns.append(self._help_btn)
        lay.addWidget(self._help_btn)
        lay.addSpacing(8)

        return self._right_sidebar

    def _make_tool_page(self, entries: list) -> QtWidgets.QWidget:
        """Build one right-sidebar tool page from [(icon, label, callback), ...]."""
        page = QtWidgets.QWidget()
        page.setStyleSheet("background: transparent;")
        pl = QtWidgets.QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        for icon, label, cb in entries:
            btn = NavButton(icon, label)
            btn.clicked.connect(cb)
            pl.addWidget(btn)
            self._all_right_btns.append(btn)
        pl.addStretch()
        return page

    def _make_pdf_tools(self) -> QtWidgets.QWidget:
        panel = DrillDownPanel()

        self._pdf_view_btn = panel.add_action("eye", "Переглянути", self._on_pdf_view)
        self._pdf_edit_btn = panel.add_folder("merge", "Розділити/Об'єднати PDF", [
            ("Виділити все",       self._merge.select_all),
            ("Очистити виділення", self._merge.clear_selection),
            ("Експортувати PDF",   self._merge.run_merge),
            ("Додати файл",        self._merge._on_add_file),
        ])
        self._pdf_edit_btn.clicked.connect(self._on_pdf_edit)

        print_btn = panel.add_folder("printer", "Друк документа", [
            ("Друкувати...",        self._on_print),
            ("Попередній перегляд", self._on_print_preview),
        ])
        print_btn.clicked.connect(self._on_pdf_view)

        panel.add_action("arrow_left", "Новий файл", self._on_new_file)

        self._all_right_btns.extend(panel.nav_buttons)
        return panel

    def _make_word_tools(self) -> QtWidgets.QWidget:
        return self._make_tool_page([
            ("arrow_left", "Новий файл", self._on_new_file),
        ])

    def _make_unsupported_tools(self) -> QtWidgets.QWidget:
        return self._make_tool_page([
            ("arrow_left", "Новий файл", self._on_new_file),
        ])

    def _on_print(self):
        self._viewer.print_document()

    def _on_print_preview(self):
        self._viewer.print_preview()

    # ── theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        t = THEME_MGR.get()
        self.setStyleSheet(f"background: {t.bg_main};")
        self._right_sidebar.setStyleSheet(f"""
            QFrame#right_sidebar {{
                background: {t.bg_sidebar};
                border-left: 1px solid {t.bg_border};
            }}
        """)
        self._stack.setStyleSheet(f"background: {t.bg_main};")
        for div in self._theme_dividers:
            div.setStyleSheet(f"background: {t.bg_hover};")
        for btn in self._all_right_btns:
            btn.update()
        self._drop_zone.update()
        self._viewer.apply_theme()
        self._word_editor.apply_theme()

    # ── PDF scenario switching ───────────────────────────────────────────────

    def _update_pdf_btn_states(self):
        self._pdf_view_btn.set_active(self._pdf_scenario == "viewer")
        self._pdf_edit_btn.set_active(self._pdf_scenario == "editor")

    def _on_pdf_view(self):
        if self._current_format != "pdf":
            return
        self._pdf_scenario = "viewer"
        if self._viewer._path != self._current_path:
            self._viewer.load_pdf(self._current_path)
        self._stack.setCurrentWidget(self._viewer)
        self._update_pdf_btn_states()

    def _on_pdf_edit(self):
        if self._current_format != "pdf":
            return
        self._pdf_scenario = "editor"
        if self._current_path not in self._merge.files:
            self._merge.add_file(self._current_path)
        self._stack.setCurrentWidget(self._merge)
        self._update_pdf_btn_states()

    # ── public API ────────────────────────────────────────────────────────────

    def open_in_viewer(self, path: str):
        """Open a PDF directly in the viewer (e.g. launched from OS file association)."""
        self._open_pdf(path)

    def _toggle_right_sidebar(self):
        self._right_collapsed = not self._right_collapsed
        target = SIDEBAR_COLLAPSED if self._right_collapsed else SIDEBAR_EXPANDED

        self._ranim.stop()
        self._ranim.setStartValue(self._right_sidebar.width())
        self._ranim.setEndValue(target)
        self._ranim.start()

        self._right_toggle_btn.setText(
            "☰" if self._right_collapsed else "☰   Інструменти"
        )
        for btn in self._all_right_btns:
            btn.set_collapsed(self._right_collapsed)

    # ── file handling ─────────────────────────────────────────────────────────

    def _on_file_chosen(self, paths: list):
        if not paths:
            return
        exts = {os.path.splitext(p)[1].lower() for p in paths}
        if exts == {".pdf"}:
            if len(paths) > 1:
                self._open_pdf_multi(paths)
            else:
                self._open_pdf(paths[0])
        elif exts == {".docx"} and len(paths) == 1:
            self._open_word(paths[0])
        else:
            self._open_unsupported(paths[0])

    def _open_pdf(self, path: str):
        self._current_format = "pdf"
        self._current_path   = path
        self._pdf_scenario   = "viewer"
        self._viewer.load_pdf(path)
        self._stack.setCurrentWidget(self._viewer)
        self._right_tool_stack.setCurrentIndex(1)
        self._right_sidebar.setVisible(True)
        self._update_pdf_btn_states()

    def _open_pdf_multi(self, paths: list):
        self._current_format = "pdf"
        self._current_path   = paths[0]
        self._pdf_scenario   = "editor"
        self._merge.reset()
        for p in paths:
            self._merge.add_file(p)
        self._stack.setCurrentWidget(self._merge)
        self._right_tool_stack.setCurrentIndex(1)
        self._right_sidebar.setVisible(True)
        self._update_pdf_btn_states()

    def _open_word(self, path: str):
        if self._word_editor.has_unsaved_changes():
            res = QtWidgets.QMessageBox.question(
                self, "Незбережені зміни",
                "Поточний документ містить незбережені зміни. Відкрити новий?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if res != QtWidgets.QMessageBox.Yes:
                return
        self._current_format = "word"
        self._current_path   = path
        self._word_editor.open_file(path)
        self._stack.setCurrentWidget(self._word_editor)
        self._right_tool_stack.setCurrentIndex(2)
        self._right_sidebar.setVisible(True)

    def _open_unsupported(self, path: str):
        self._current_format = "unsupported"
        self._current_path   = path
        ext = os.path.splitext(path)[1] or "файл"
        self._coming_soon.set_label(f"Формат {ext}")
        self._stack.setCurrentWidget(self._coming_soon)
        self._right_tool_stack.setCurrentIndex(3)
        self._right_sidebar.setVisible(True)

    def _on_new_file(self):
        if self._current_format == "word" and self._word_editor.has_unsaved_changes():
            res = QtWidgets.QMessageBox.question(
                self, "Незбережені зміни",
                "Поточний документ містить незбережені зміни. Закрити без збереження?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if res != QtWidgets.QMessageBox.Yes:
                return
        self._merge.reset()
        self._current_format = "none"
        self._current_path   = None
        self._stack.setCurrentWidget(self._drop_zone)
        self._right_tool_stack.setCurrentIndex(0)
        self._right_sidebar.setVisible(False)

    # ── window state ──────────────────────────────────────────────────────────

    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _STATE_FILE = os.path.join(_PROJECT_ROOT, "window_state.json")

    def _save_window_state(self):
        try:
            with open(self._STATE_FILE, "w") as f:
                json.dump({"width": self.width(), "height": self.height()}, f)
        except OSError:
            pass

    def _load_window_state(self):
        try:
            with open(self._STATE_FILE) as f:
                s = json.load(f)
            w = max(800, min(int(s["width"]),  3840))
            h = max(500, min(int(s["height"]), 2160))
            self.resize(w, h)
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            pass

    def closeEvent(self, event):
        self._save_window_state()
        super().closeEvent(event)
