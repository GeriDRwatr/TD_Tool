from PySide6 import QtCore, QtGui, QtWidgets

from ..theme import THEME_MGR
from ..ui import icons as _icons

_svg_icons = _icons

# ── Mini live preview ──────────────────────────────────────────────────────────

class _MiniPreview(QtWidgets.QWidget):
    """Scaled replica of the app UI that repaints when theme changes."""

    _SW = 130          # sidebar width inside preview
    _SB_H = 22         # status-bar height inside preview

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(256)
        self.setMinimumHeight(360)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                           QtWidgets.QSizePolicy.Expanding)
        self.setStyleSheet("background: transparent;")
        THEME_MGR.add_listener(self.update)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        t = THEME_MGR.get()
        W, H = self.width(), self.height()
        SW, SB = self._SW, self._SB_H

        # ── layers ────────────────────────────────────────────────────────────
        # 1. workspace bg
        p.fillRect(0, 0, W, H, QtGui.QColor(t.bg_main))
        # 2. viewer content area
        content_r = QtCore.QRect(SW + 1, 0, W - SW - 1, H - SB)
        p.fillRect(content_r, QtGui.QColor(t.viewer_bg))
        # 3. sidebar
        p.fillRect(0, 0, SW, H, QtGui.QColor(t.bg_sidebar))
        # 4. status bar
        p.fillRect(SW + 1, H - SB, W - SW - 1, SB, QtGui.QColor(t.bg_sidebar))

        # ── borders ───────────────────────────────────────────────────────────
        p.setPen(QtGui.QPen(QtGui.QColor(t.bg_border), 1))
        p.drawLine(SW, 0, SW, H)
        p.drawLine(SW + 1, H - SB, W, H - SB)

        # ── sidebar header ────────────────────────────────────────────────────
        p.setFont(QtGui.QFont("", 8, QtGui.QFont.DemiBold))
        p.setPen(QtGui.QColor(255, 255, 255, 200))
        p.drawText(QtCore.QRect(7, 0, SW - 7, 34),
                   QtCore.Qt.AlignVCenter, "☰  TDTool")

        p.setPen(QtGui.QPen(QtGui.QColor(t.bg_hover), 1))
        p.drawLine(0, 34, SW, 34)

        # ── nav items ─────────────────────────────────────────────────────────
        nav = [
            ("eye",             "Відкрити PDF",  True),
            ("merge",           "Розділити",      False),
            ("rotate",          "Конвертувати",   False),
            ("compress_layers", "Стиснути PDF",   False),
        ]
        y = 38
        for icon_name, label, active in nav:
            ih = 29
            if active:
                bg = QtGui.QColor(t.nav_active_bg)
                bg.setAlpha(t.nav_active_bg_alpha)
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(bg)
                p.drawRoundedRect(QtCore.QRect(3, y + 1, SW - 6, ih - 2), 5, 5)
            isz = 12
            ic = QtGui.QColor(t.nav_icon_active_color if active
                              else t.nav_icon_inactive_color)
            ic.setAlpha(t.nav_icon_active_alpha if active
                        else t.nav_icon_inactive_alpha)
            icon_rect = QtCore.QRectF(14 - isz/2, y + ih/2 - isz/2, isz, isz)
            if _svg_icons.has_svg(icon_name):
                _svg_icons.draw(p, icon_rect, icon_name, ic)
            else:
                _icons.draw(p, icon_rect, icon_name, ic)
            lc = QtGui.QColor(t.nav_label_active_color if active
                              else t.nav_label_inactive_color)
            lc.setAlpha(t.nav_label_active_alpha if active
                        else t.nav_label_inactive_alpha)
            p.setFont(QtGui.QFont("", 8,
                                  QtGui.QFont.DemiBold if active
                                  else QtGui.QFont.Normal))
            p.setPen(lc)
            p.drawText(QtCore.QRect(27, y, SW - 31, ih),
                       QtCore.Qt.AlignVCenter, label)
            y += ih

        # bottom-nav divider + gear
        p.setPen(QtGui.QPen(QtGui.QColor(t.bg_hover), 1))
        p.drawLine(0, y + 4, SW, y + 4)
        y += 6
        ic = QtGui.QColor(t.nav_icon_inactive_color)
        ic.setAlpha(t.nav_icon_inactive_alpha)
        _svg_icons.draw(p, QtCore.QRectF(14 - 6, y + 15 - 6, 12, 12), "gear", ic)
        lc = QtGui.QColor(t.nav_label_inactive_color)
        lc.setAlpha(t.nav_label_inactive_alpha)
        p.setFont(QtGui.QFont("", 8))
        p.setPen(lc)
        p.drawText(QtCore.QRect(27, y, SW - 31, 30),
                   QtCore.Qt.AlignVCenter, "Налаштування")

        # ── viewer content ────────────────────────────────────────────────────
        # text selection sample
        sel_y = H - SB - 80
        sel_c = QtGui.QColor(t.selection_color)
        sel_c.setAlpha(90)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(sel_c)
        p.drawRect(QtCore.QRect(SW + 8, sel_y, 65, 12))
        p.setPen(QtGui.QColor(255, 255, 255, 50))
        p.setFont(QtGui.QFont("", 7))
        p.drawText(QtCore.QRect(SW + 8, sel_y - 14, 90, 12),
                   QtCore.Qt.AlignVCenter, "Виділення тексту")

        # accent DropZone border
        acc_y = H - SB - 120
        dz_r = QtCore.QRectF(SW + 8, acc_y, 55, 20)
        dz_pen = QtGui.QPen(QtGui.QColor(t.accent), 1.4, QtCore.Qt.DashLine)
        dz_pen.setDashPattern([3, 2])
        p.setPen(dz_pen)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(dz_r, 4, 4)
        p.setPen(QtGui.QColor(t.accent))
        p.setFont(QtGui.QFont("", 7))
        p.drawText(dz_r, QtCore.Qt.AlignCenter, "+ PDF")
        p.setPen(QtGui.QColor(255, 255, 255, 50))
        p.drawText(QtCore.QRect(SW + 8, acc_y - 14, 90, 12),
                   QtCore.Qt.AlignVCenter, "Акцентний колір")

        # group color swatches
        gc_y = H - SB - 36
        colors = [getattr(t, f"group_color_{i}") for i in range(8)]
        avail = W - SW - 14
        sw = (avail - 7 * 2) // 8
        p.setPen(QtGui.QColor(255, 255, 255, 50))
        p.setFont(QtGui.QFont("", 7))
        p.drawText(QtCore.QRect(SW + 6, gc_y - 14, avail, 12),
                   QtCore.Qt.AlignVCenter, "Кольори груп")
        for i, c in enumerate(colors):
            sx = SW + 6 + i * (sw + 2)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(c))
            p.drawRoundedRect(QtCore.QRectF(sx, gc_y, sw, 18), 3, 3)

        # ── status bar ────────────────────────────────────────────────────────
        sy = H - SB
        file_c = QtGui.QColor(255, 255, 255, t.statusbar_file_alpha)
        page_c = QtGui.QColor(255, 255, 255, t.statusbar_page_alpha)
        cur_c  = QtGui.QColor(255, 255, 255, t.statusbar_cursor_alpha)
        p.setFont(QtGui.QFont("", 7))
        p.setPen(file_c)
        p.drawText(QtCore.QRect(SW + 6, sy, 70, SB),
                   QtCore.Qt.AlignVCenter, "document.pdf")
        p.setPen(page_c)
        p.drawText(QtCore.QRect(SW + 78, sy, 28, SB),
                   QtCore.Qt.AlignCenter, "3/9")
        p.setPen(cur_c)
        p.drawText(QtCore.QRect(W - 66, sy, 62, SB),
                   QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                   "x 123  y 456")
        p.end()


# ── Helper widgets ─────────────────────────────────────────────────────────────

class _ColorButton(QtWidgets.QPushButton):
    color_changed = QtCore.Signal(str)

    def __init__(self, hex_color: str, parent=None):
        super().__init__(parent)
        self._hex = hex_color
        self.setFixedSize(108, 26)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._refresh()
        self.clicked.connect(self._pick)

    def set_color(self, hex_color: str):
        if hex_color != self._hex:
            self._hex = hex_color
            self._refresh()

    def get_color(self) -> str:
        return self._hex

    def _refresh(self):
        c = QtGui.QColor(self._hex)
        lum = c.red() * 0.299 + c.green() * 0.587 + c.blue() * 0.114
        fg = "#000" if lum > 140 else "#fff"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._hex}; color: {fg};
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 5px; font-size: 11px;
                font-family: Consolas, monospace; letter-spacing: 0.4px;
            }}
            QPushButton:hover {{ border: 1px solid rgba(255,255,255,0.36); }}
        """)
        self.setText(self._hex)

    def _pick(self):
        dlg = QtWidgets.QColorDialog(QtGui.QColor(self._hex), self)
        dlg.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, False)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._hex = dlg.currentColor().name()
            self._refresh()
            self.color_changed.emit(self._hex)


def _make_slider(mn: int, mx: int, value: int, width: int = 100) -> QtWidgets.QSlider:
    s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
    s.setRange(mn, mx)
    s.setValue(value)
    s.setFixedWidth(width)
    s.setFocusPolicy(QtCore.Qt.NoFocus)
    s.setStyleSheet("""
        QSlider::groove:horizontal {
            background: rgba(255,255,255,0.11); height: 4px; border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: rgba(255,255,255,0.82); width: 12px; height: 12px;
            border-radius: 6px; margin: -4px 0;
        }
        QSlider::handle:horizontal:hover { background: white; }
        QSlider::sub-page:horizontal {
            background: rgba(255,255,255,0.42); border-radius: 2px;
        }
    """)
    return s


# ── Settings screen ────────────────────────────────────────────────────────────

_LABEL_SS  = "color: rgba(255,255,255,0.70); font-size: 13px; background: transparent;"
_SMALL_SS  = "color: rgba(255,255,255,0.35); font-size: 11px; background: transparent;"
_VALW = 32   # width of value label


class ScreenSettings(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._color_btns:  dict[str, _ColorButton]     = {}
        self._sliders:     dict[str, QtWidgets.QSlider] = {}
        self._val_labels:  dict[str, QtWidgets.QLabel]  = {}
        self._save_btn:    QtWidgets.QPushButton | None = None
        self._build_ui()
        THEME_MGR.add_listener(self._sync_from_theme)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # left sticky preview
        preview = _MiniPreview()
        root.addWidget(preview)

        v_div = QtWidgets.QFrame()
        v_div.setFixedWidth(1)
        v_div.setStyleSheet("background: rgba(255,255,255,0.05); border: none;")
        root.addWidget(v_div)

        # right scrollable controls
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                width: 6px; background: transparent; margin: 0; border: none;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.16); border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.30); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QtWidgets.QWidget()
        inner.setStyleSheet("background: transparent;")
        lay = QtWidgets.QVBoxLayout(inner)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(2)

        t = THEME_MGR.get()
        self._build_bg_section(lay, t)
        self._build_nav_section(lay, t)
        self._build_icons_section(lay, t)
        self._build_group_colors_section(lay, t)
        self._build_viewer_section(lay, t)

        lay.addSpacing(20)
        self._buttons(lay)
        lay.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def _build_bg_section(self, lay, t):
        self._section(lay, "ФОН ПРОГРАМИ")
        self._color_row(lay, "bg_main",    "Робоча область",         t.bg_main)
        self._color_row(lay, "bg_sidebar", "Бічна панель / Статус",  t.bg_sidebar)
        self._color_row(lay, "bg_border",  "Межі між панелями",      t.bg_border)
        self._color_row(lay, "bg_hover",   "Роздільники в панелях",  t.bg_hover)
        self._color_row(lay, "accent",     "Акцентний колір",        t.accent)

    def _build_nav_section(self, lay, t):
        lay.addSpacing(12)
        self._section(lay, "ПУНКТИ НАВІГАЦІЇ")
        self._color_alpha_row(lay,
            "nav_active_bg",    "nav_active_bg_alpha",
            "Підсвітка активного пункту",
            t.nav_active_bg, t.nav_active_bg_alpha)
        self._color_alpha_row(lay,
            "nav_hover_bg",     "nav_hover_bg_alpha",
            "Підсвітка при наведенні",
            t.nav_hover_bg, t.nav_hover_bg_alpha)
        self._color_alpha_row(lay,
            "nav_icon_active_color",   "nav_icon_active_alpha",
            "Іконка — активний стан",
            t.nav_icon_active_color, t.nav_icon_active_alpha)
        self._color_alpha_row(lay,
            "nav_icon_inactive_color", "nav_icon_inactive_alpha",
            "Іконка — неактивний стан",
            t.nav_icon_inactive_color, t.nav_icon_inactive_alpha)
        self._color_alpha_row(lay,
            "nav_label_active_color",   "nav_label_active_alpha",
            "Підпис — активний стан",
            t.nav_label_active_color, t.nav_label_active_alpha)
        self._color_alpha_row(lay,
            "nav_label_inactive_color", "nav_label_inactive_alpha",
            "Підпис — неактивний стан",
            t.nav_label_inactive_color, t.nav_label_inactive_alpha)

    def _build_icons_section(self, lay, t):
        lay.addSpacing(12)
        self._section(lay, "ІКОНКИ")
        self._slider_row(lay, "icon_size",   "Розмір іконок",
                         16, 28, t.icon_size, "px", int)
        self._slider_row(lay, "icon_stroke", "Товщина ліній",
                         5, 15, int(t.icon_stroke * 100), "%",
                         lambda v: round(v / 100, 3))

    def _build_group_colors_section(self, lay, t):
        lay.addSpacing(12)
        self._section(lay, "КОЛЬОРИ ГРУП")
        names = ["Зелений", "Синій", "Помаранчевий", "Фіолетовий",
                 "Бірюзовий", "Червоний", "Жовтий", "Індиго"]
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 4, 0, 4)
        for i in range(8):
            key = f"group_color_{i}"
            row_i, col_i = divmod(i, 2)
            cell = QtWidgets.QHBoxLayout()
            cell.setSpacing(6)
            lbl = QtWidgets.QLabel(f"Г{i+1}  {names[i]}")
            lbl.setStyleSheet(_LABEL_SS)
            cell.addWidget(lbl)
            cell.addStretch()
            btn = _ColorButton(getattr(t, key))
            btn.color_changed.connect(lambda c, k=key: THEME_MGR.update(**{k: c}))
            self._color_btns[key] = btn
            cell.addWidget(btn)
            wrap = QtWidgets.QWidget()
            wrap.setStyleSheet("background: transparent;")
            wrap.setLayout(cell)
            grid.addWidget(wrap, row_i, col_i)
        lay.addLayout(grid)

    def _build_viewer_section(self, lay, t):
        lay.addSpacing(12)
        self._section(lay, "ПЕРЕГЛЯДАЧ PDF")
        self._color_row(lay, "viewer_bg",       "Фон під сторінками",     t.viewer_bg)
        self._color_row(lay, "selection_color",  "Виділення тексту",       t.selection_color)
        self._alpha_row(lay, "scrollbar_alpha",  "Смуга прокрутки — alpha",
                        0, 255, t.scrollbar_alpha)
        self._alpha_row(lay, "statusbar_file_alpha",   "Рядок стану — назва файлу",
                        0, 255, t.statusbar_file_alpha)
        self._alpha_row(lay, "statusbar_page_alpha",   "Рядок стану — номер сторінки",
                        0, 255, t.statusbar_page_alpha)
        self._alpha_row(lay, "statusbar_cursor_alpha", "Рядок стану — координати",
                        0, 255, t.statusbar_cursor_alpha)

    # ── row builders ──────────────────────────────────────────────────────────

    def _section(self, lay, title: str):
        lbl = QtWidgets.QLabel(title)
        lbl.setStyleSheet(
            "color: rgba(255,255,255,0.30); font-size: 10px; font-weight: 700;"
            " letter-spacing: 1.4px; background: transparent;"
        )
        lay.addSpacing(4)
        lay.addWidget(lbl)
        div = QtWidgets.QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: rgba(255,255,255,0.06); border: none;")
        lay.addWidget(div)
        lay.addSpacing(4)

    def _wrap_row(self, lay, row_layout):
        w = QtWidgets.QWidget()
        w.setStyleSheet("background: transparent;")
        w.setFixedHeight(36)
        wl = QtWidgets.QHBoxLayout(w)
        wl.setContentsMargins(0, 4, 0, 4)
        wl.addLayout(row_layout)
        lay.addWidget(w)

    def _color_row(self, lay, key: str, label: str, hex_color: str):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet(_LABEL_SS)
        row.addWidget(lbl, 1)
        btn = _ColorButton(hex_color)
        btn.color_changed.connect(lambda c, k=key: THEME_MGR.update(**{k: c}))
        self._color_btns[key] = btn
        row.addWidget(btn)
        self._wrap_row(lay, row)

    def _color_alpha_row(self, lay,
                         key_color: str, key_alpha: str,
                         label: str, hex_color: str, alpha: int):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet(_LABEL_SS)
        row.addWidget(lbl, 1)

        btn = _ColorButton(hex_color)
        btn.color_changed.connect(lambda c, k=key_color: THEME_MGR.update(**{k: c}))
        self._color_btns[key_color] = btn
        row.addWidget(btn)

        row.addSpacing(4)

        alpha_lbl = QtWidgets.QLabel("α")
        alpha_lbl.setStyleSheet(_SMALL_SS)
        alpha_lbl.setFixedWidth(12)
        row.addWidget(alpha_lbl)

        sl = _make_slider(0, 255, alpha, 80)
        def on_alpha(v, k=key_alpha):
            self._val_labels[k].setText(str(v))
            THEME_MGR.update(**{k: v})
        sl.valueChanged.connect(on_alpha)
        self._sliders[key_alpha] = sl
        row.addWidget(sl)

        val = QtWidgets.QLabel(str(alpha))
        val.setFixedWidth(_VALW)
        val.setStyleSheet(_SMALL_SS)
        val.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self._val_labels[key_alpha] = val
        row.addWidget(val)

        self._wrap_row(lay, row)

    def _alpha_row(self, lay, key: str, label: str,
                   mn: int, mx: int, value: int):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet(_LABEL_SS)
        row.addWidget(lbl, 1)

        sl = _make_slider(mn, mx, value, 100)
        def on_v(v, k=key):
            self._val_labels[k].setText(str(v))
            THEME_MGR.update(**{k: v})
        sl.valueChanged.connect(on_v)
        self._sliders[key] = sl
        row.addWidget(sl)

        val = QtWidgets.QLabel(str(value))
        val.setFixedWidth(_VALW)
        val.setStyleSheet(_SMALL_SS)
        val.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self._val_labels[key] = val
        row.addWidget(val)

        self._wrap_row(lay, row)

    def _slider_row(self, lay, key: str, label: str,
                    mn: int, mx: int, initial: int,
                    suffix: str, to_real):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet(_LABEL_SS)
        row.addWidget(lbl, 1)

        sl = _make_slider(mn, mx, initial, 100)
        def on_v(v, k=key, tr=to_real, sf=suffix):
            self._val_labels[k].setText(f"{v}{sf}")
            THEME_MGR.update(**{k: tr(v)})
        sl.valueChanged.connect(on_v)
        self._sliders[key] = sl
        row.addWidget(sl)

        val = QtWidgets.QLabel(f"{initial}{suffix}")
        val.setFixedWidth(_VALW + 6)
        val.setStyleSheet(_SMALL_SS)
        val.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self._val_labels[key] = val
        row.addWidget(val)

        self._wrap_row(lay, row)

    def _buttons(self, lay):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._save_btn = QtWidgets.QPushButton("Зберегти")
        self._save_btn.setFixedHeight(34)
        self._save_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._save_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.10);
                color: rgba(255,255,255,0.85);
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 7px; font-size: 13px; font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.16); }
            QPushButton:pressed { background: rgba(255,255,255,0.06); }
        """)
        self._save_btn.clicked.connect(self._on_save)
        row.addWidget(self._save_btn)

        reset_btn = QtWidgets.QPushButton("Скинути")
        reset_btn.setFixedHeight(34)
        reset_btn.setCursor(QtCore.Qt.PointingHandCursor)
        reset_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        reset_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255,255,255,0.36);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 7px; font-size: 13px; padding: 0 20px;
            }
            QPushButton:hover {
                color: rgba(255,255,255,0.60);
                border: 1px solid rgba(255,255,255,0.18);
            }
        """)
        reset_btn.clicked.connect(THEME_MGR.reset)
        row.addWidget(reset_btn)
        row.addStretch()
        lay.addLayout(row)

    # ── sync from theme (called on any THEME_MGR change) ──────────────────────

    def _on_save(self):
        THEME_MGR.save()
        if self._save_btn:
            self._save_btn.setText("Збережено ✓")
            QtCore.QTimer.singleShot(1600, lambda: (
                self._save_btn.setText("Зберегти") if self._save_btn else None
            ))

    def _sync_from_theme(self):
        t = THEME_MGR.get()

        # colors
        for key, btn in self._color_btns.items():
            btn.set_color(getattr(t, key))

        # sliders + value labels
        for key, sl in self._sliders.items():
            raw = getattr(t, key)
            # icon_stroke is stored as float (e.g. 0.09 → display 9)
            if key == "icon_stroke":
                v = int(raw * 100)
                text = f"{v}%"
            elif key == "icon_size":
                v = int(raw)
                text = f"{v}px"
            else:
                v = int(raw)
                text = str(v)
            sl.blockSignals(True)
            sl.setValue(v)
            sl.blockSignals(False)
            if key in self._val_labels:
                self._val_labels[key].setText(text)
