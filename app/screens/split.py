import os
from collections import defaultdict
import fitz
from PySide6 import QtWidgets, QtCore, QtGui

from ..constants import GREEN_COLOR, MAX_GROUPS, THUMB_SCALE, group_color
from ..widgets import FlatButton, FullBorderPaper, GroupButton, DraggableCard
from ..pdf_utils import clear_layout, safe_thumbnail_render, split_pdf


class GroupDeck(QtWidgets.QWidget):
    """Складена колода карток. Малюється через paintEvent без дочірніх QFrame,
    тому ефект розсування не обрізається межами віджета."""

    MAX_SHADOW = 3
    SO         = 5    # base stacking offset px
    TOP_PAD    = 22   # vertical room above top card for upward hover movement

    def __init__(self, group_num, pixmaps, default_name, screen,
                 thumb_w, thumb_h, cell_w, parent=None):
        super().__init__(parent)
        self._group_num  = group_num
        self._screen     = screen
        self._thumb_w    = thumb_w
        self._thumb_h    = thumb_h
        self._pixmap     = pixmaps[-1] if pixmaps else None
        self._page_count = len(pixmaps)
        self._spread     = 0.0
        self._color      = group_color(group_num)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        n_shadow = min(max(len(pixmaps) - 1, 0), self.MAX_SHADOW)
        SO, TP   = self.SO, self.TOP_PAD

        self._rest_tx = [
            ((n_shadow - i) * float(SO), (n_shadow - i) * float(SO))
            for i in range(n_shadow)
        ]
        _D   = 10.0
        _lag = [0.75, 0.45, 0.10]
        self._spread_tx = [
            (
                (n_shadow - i) * SO + _D * (1.0 - _lag[(n_shadow - i) - 1]),
                (n_shadow - i) * SO + _D * (1.0 - _lag[(n_shadow - i) - 1]),
            )
            for i in range(n_shadow)
        ]

        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)

        self._x_center = (cell_w - thumb_w) // 2

        name_y  = TP + thumb_h + self.MAX_SHADOW * SO + 8
        total_h = name_y + 18 + 6
        self._card_area_h = TP + thumb_h + 12
        self.setFixedSize(cell_w, total_h)
        self.setAttribute(QtCore.Qt.WA_Hover)

        color = self._color
        self._name_edit = QtWidgets.QLineEdit(default_name, self)
        self._name_edit.setFixedSize(thumb_w, 18)
        self._name_edit.move(self._x_center, name_y)
        self._name_edit.setAlignment(QtCore.Qt.AlignCenter)
        self._name_edit.setPlaceholderText("назва файлу")
        self._name_edit.setCursorPosition(0)
        self._name_edit.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                color: rgba(255,255,255,0.38);
                font-size: 10px;
                padding: 0 2px;
                selection-background-color: {color};
            }}
            QLineEdit:hover {{
                color: rgba(255,255,255,0.68);
                border-color: rgba(255,255,255,0.22);
                background: rgba(255,255,255,0.05);
            }}
            QLineEdit:focus {{
                background: #21232c;
                border-color: {color};
                color: rgba(255,255,255,0.9);
            }}
        """)
        self._name_edit.editingFinished.connect(
            lambda: screen.set_group_name(group_num, self._name_edit.text())
        )

    def _on_anim_value(self, v):
        self._spread = float(v)
        self.update()

    def event(self, e):
        if e.type() == QtCore.QEvent.HoverEnter:
            self._anim.stop()
            self._anim.setStartValue(self._spread)
            self._anim.setEndValue(1.0)
            self._anim.start()
        elif e.type() == QtCore.QEvent.HoverLeave:
            self._anim.stop()
            self._anim.setStartValue(self._spread)
            self._anim.setEndValue(0.0)
            self._anim.start()
        return super().event(e)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        s      = self._spread
        tw, th = self._thumb_w, self._thumb_h
        color  = QtGui.QColor(self._color)

        cx = self._x_center + tw / 2.0 - s * 10.0
        cy = self.TOP_PAD   + th / 2.0 - s * 10.0

        for i in range(len(self._rest_tx)):
            r0, r1 = self._rest_tx[i], self._spread_tx[i]
            dx = r0[0] + (r1[0] - r0[0]) * s
            dy = r0[1] + (r1[1] - r0[1]) * s
            card_x = cx + dx - tw / 2.0
            card_y = cy + dy - th / 2.0

            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(0, 0, 0, 20))
            p.drawRoundedRect(QtCore.QRectF(card_x + 2, card_y + 4, tw, th), 5, 5)

            bc = QtGui.QColor(color)
            bc.setAlpha(100 + i * 40)
            p.setPen(QtGui.QPen(bc, 2.15))
            p.setBrush(QtGui.QColor(0xff, 0xff, 0xff))
            p.drawRoundedRect(QtCore.QRectF(card_x, card_y, tw, th), 5, 5)

        p.save()
        p.translate(cx, cy)
        p.rotate(-s * 2.0)
        p.translate(-tw / 2.0, -th / 2.0)

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(0, 0, 0, 55))
        p.drawRoundedRect(QtCore.QRectF(1, 4, tw, th), 5, 5)

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(0xff, 0xff, 0xff))
        p.drawRoundedRect(QtCore.QRectF(0, 0, tw, th), 5, 5)

        if self._pixmap:
            inner = QtCore.QRectF(2, 2, tw - 4, th - 4)
            clip  = QtGui.QPainterPath()
            clip.addRoundedRect(inner, 4.0, 4.0)
            p.save()
            p.setClipPath(clip)
            p.drawPixmap(inner.toAlignedRect(), self._pixmap)
            p.restore()

        p.setPen(QtGui.QPen(color, 3.8))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(QtCore.QRectF(0, 0, tw, th), 5, 5)

        echo = QtGui.QColor(color)
        echo.setAlphaF(0.65)
        p.setPen(QtGui.QPen(echo, 2.0))
        p.drawRoundedRect(QtCore.QRectF(3, 3, tw - 6, th - 6), 2, 2)

        _bs = 42
        _bx = (tw - _bs) / 2.0
        _by = (th - _bs) / 2.0
        _br = QtCore.QRectF(_bx + 3, _by + 3, _bs - 6, _bs - 6)
        _bc = QtGui.QColor(color)
        _bc.setAlpha(160)
        p.setPen(QtGui.QPen(_bc, 1.6))
        p.setBrush(QtGui.QColor(30, 32, 42, 140))
        p.drawRoundedRect(_br, 7, 7)
        bf = QtGui.QFont()
        bf.setPixelSize(14)
        bf.setWeight(QtGui.QFont.Bold)
        p.setFont(bf)
        p.setPen(QtGui.QColor(255, 255, 255, 230))
        p.drawText(_br, QtCore.Qt.AlignCenter, str(self._group_num))

        cf = QtGui.QFont()
        cf.setPixelSize(10)
        cf.setWeight(QtGui.QFont.DemiBold)
        p.setFont(cf)
        p.setPen(QtGui.QColor(0, 0, 0, 130))
        p.drawText(
            QtCore.QRectF(0, th - 20, tw, 16),
            QtCore.Qt.AlignCenter,
            f"{self._page_count} стор."
        )

        p.restore()
        p.end()

    def mousePressEvent(self, event):
        if (event.button() == QtCore.Qt.LeftButton
                and event.pos().y() <= self._card_area_h):
            self._screen.expand_group(self._group_num)
        super().mousePressEvent(event)


class ScreenSplitMulti(QtWidgets.QWidget):
    """Другий екран: розмітка сторінок та запуск розділення PDF."""

    def __init__(self, app_state: dict, go_back):
        super().__init__()
        self.app_state = app_state
        self.go_back   = go_back

        self.doc_cache        = {}
        self.page_count_cache = {}

        self.page_groups_map = {}   # path → [None|group_num, ...] by actual_i
        self.group_names_map = {}   # path → {group_num: str}
        self.page_order      = {}

        self._active_group = 1
        self._num_groups   = 4
        self._group_btns: list[GroupButton] = []
        self._btn_group    = QtWidgets.QButtonGroup(self)
        self._btn_group.setExclusive(True)

        self.current_pdf_path = None
        self._rendering       = False
        self._thumb_base_w    = 210

        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self.render_thumbnails)

        self._viewport_debounce = QtCore.QTimer(self)
        self._viewport_debounce.setSingleShot(True)
        self._viewport_debounce.timeout.connect(self.render_thumbnails)

        self.setWindowTitle("Розділення PDF")
        self.resize(1250, 720)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)

        self.lbl_filename = QtWidgets.QLabel("")
        self.lbl_filename.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_filename.setStyleSheet(
            "font-weight: 600; font-size: 14px; color: rgba(255,255,255,0.85); padding: 8px 0;"
        )
        root.addWidget(self.lbl_filename)

        hint = QtWidgets.QLabel(
            "Обери активну групу внизу → клікни сторінки щоб додати до неї"
            " — кожна група збережеться як окремий PDF"
        )
        hint.setAlignment(QtCore.Qt.AlignCenter)
        hint.setStyleSheet(
            "font-size: 11px; color: rgba(255,255,255,0.38); padding: 0 12px 6px;"
        )
        root.addWidget(hint)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        root.addWidget(self.scroll, 1)

        self.thumbs_container = QtWidgets.QWidget()
        self.scroll.setWidget(self.thumbs_container)

        self.thumbs_grid = QtWidgets.QGridLayout()
        self.thumbs_grid.setContentsMargins(10, 10, 10, 10)
        self.thumbs_grid.setHorizontalSpacing(14)
        self.thumbs_grid.setVerticalSpacing(80)
        self.thumbs_grid.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.thumbs_container.setLayout(self.thumbs_grid)

        self.scroll.viewport().installEventFilter(self)

        sep = QtWidgets.QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #2a3045;")
        root.addWidget(sep)

        bottom_bar = QtWidgets.QWidget()
        bottom_bar.setStyleSheet("background: #1c1e25;")
        bottom_layout = QtWidgets.QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(8)

        groups_scroll = QtWidgets.QScrollArea()
        groups_scroll.setFixedHeight(54)
        groups_scroll.setWidgetResizable(True)
        groups_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        groups_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        groups_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 3px; background: #191c22; }
            QScrollBar::handle:horizontal { background: #333545; border-radius: 1px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)
        self._groups_container = QtWidgets.QWidget()
        self._groups_container.setStyleSheet("background: transparent;")
        self._groups_layout = QtWidgets.QHBoxLayout(self._groups_container)
        self._groups_layout.setSpacing(6)
        self._groups_layout.setContentsMargins(0, 4, 8, 4)

        for i in range(1, self._num_groups + 1):
            self._add_group_button(i)
        self._group_btns[0].setChecked(True)

        self._add_group_btn = QtWidgets.QPushButton("+")
        self._add_group_btn.setFixedSize(38, 38)
        self._add_group_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._add_group_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._add_group_btn.setToolTip("Додати групу")
        self._add_group_btn.setStyleSheet("""
            QPushButton {
                background: #21232c; border: 1.5px dashed #333545;
                border-radius: 7px; color: #5c6480; font-size: 18px; font-weight: bold;
            }
            QPushButton:hover { background: #272a34; border-color: #505470; color: #8590b8; }
        """)
        self._add_group_btn.clicked.connect(self._on_add_group)
        self._groups_layout.addWidget(self._add_group_btn)
        self._groups_layout.addStretch()
        groups_scroll.setWidget(self._groups_container)
        self._groups_scroll = groups_scroll

        bottom_layout.addWidget(groups_scroll, 1)

        sep_v = QtWidgets.QFrame()
        sep_v.setFixedSize(1, 38)
        sep_v.setStyleSheet("background: #252830;")
        bottom_layout.addWidget(sep_v)

        self.btn_run = FlatButton("play", "Поїхали", GREEN_COLOR)
        self.btn_run.clicked.connect(self.run_split)
        bottom_layout.addWidget(self.btn_run)

        self.btn_back = FlatButton("arrow_left", "Новий файл", "#6272a4")
        self.btn_back.clicked.connect(self.go_back)
        bottom_layout.addWidget(self.btn_back)

        root.addWidget(bottom_bar)

    # ── events ────────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport():
            if event.type() == QtCore.QEvent.Resize:
                if self.current_pdf_path:
                    self._viewport_debounce.start(180)
            elif event.type() == QtCore.QEvent.Wheel:
                if event.modifiers() & QtCore.Qt.ControlModifier:
                    self._zoom_thumbs(event.angleDelta().y())
                    return True
        return super().eventFilter(obj, event)

    def _zoom_thumbs(self, delta: int):
        if delta > 0:
            self._thumb_base_w = min(self._thumb_base_w + 20, 400)
        else:
            self._thumb_base_w = max(self._thumb_base_w - 20, 80)
        if self.current_pdf_path:
            self._render_timer.start(0)

    def closeEvent(self, event):
        for doc in self.doc_cache.values():
            try:
                doc.close()
            except Exception:
                pass
        self.doc_cache.clear()
        super().closeEvent(event)

    # ── документи ────────────────────────────────────────────────────────────

    def update_info(self):
        files = self.app_state.get("files_fullpaths", [])
        if not files:
            self.current_pdf_path = None
            self.lbl_filename.setText("")
            return
        self._reset_all()
        self.current_pdf_path = files[0]
        self.lbl_filename.setText(os.path.basename(self.current_pdf_path))

    def _reset_all(self):
        for doc in self.doc_cache.values():
            try:
                doc.close()
            except Exception:
                pass
        self.doc_cache.clear()
        self.page_count_cache.clear()
        self.page_groups_map.clear()
        self.group_names_map.clear()
        self.page_order.clear()
        self._active_group = 1
        self._reset_group_buttons()

    def reset(self):
        self._reset_all()
        clear_layout(self.thumbs_grid)
        self.current_pdf_path = None
        self.lbl_filename.setText("")

    def _reset_group_buttons(self):
        for btn in self._group_btns:
            self._btn_group.removeButton(btn)
            self._groups_layout.removeWidget(btn)
            btn.deleteLater()
        self._group_btns.clear()
        self._add_group_btn.show()
        self._num_groups = 4
        for i in range(1, self._num_groups + 1):
            self._add_group_button(i)
        self._group_btns[0].setChecked(True)

    def get_doc(self, path: str) -> fitz.Document:
        if path in self.doc_cache:
            return self.doc_cache[path]
        doc = fitz.open(path)
        self.doc_cache[path]        = doc
        self.page_count_cache[path] = doc.page_count
        pc = doc.page_count
        self.page_groups_map.setdefault(path, [None] * pc)
        self.group_names_map.setdefault(path, {})
        return doc

    def ensure_maps_for_pdf(self, path: str, page_count: int):
        if path not in self.page_groups_map or len(self.page_groups_map[path]) != page_count:
            self.page_groups_map[path] = [None] * page_count
        self.group_names_map.setdefault(path, {})
        if path not in self.page_order or len(self.page_order[path]) != page_count:
            self.page_order[path] = list(range(page_count))

    # ── slots ─────────────────────────────────────────────────────────────────

    def run_split(self):
        files = self.app_state.get("files_fullpaths", [])
        if not files:
            QtWidgets.QMessageBox.information(self, "Розділення", "Немає вибраних PDF.")
            return

        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Виберіть папку для збереження результату", ""
        )
        if not out_dir:
            return
        self.app_state["output_dir"] = out_dir

        try:
            total_created = 0
            for path in files:
                doc = self.get_doc(path)
                pc  = self.page_count_cache[path]
                self.ensure_maps_for_pdf(path, pc)

                order       = self.page_order.get(path, list(range(pc)))
                pg_map      = self.page_groups_map[path]
                group_names = self.group_names_map.get(path, {})
                pdf_base    = os.path.splitext(os.path.basename(path))[0]
                total_created += split_pdf(doc, order, pg_map, pdf_base, out_dir, group_names)

            QtWidgets.QMessageBox.information(
                self, "Готово ✅", f"Готово!\nСтворено файлів: {total_created}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Помилка", f"Сталася помилка:\n{e}")
            raise

    # ── рендер мініатюр ───────────────────────────────────────────────────────

    def render_thumbnails(self):
        if self._rendering or not self.current_pdf_path:
            return
        self._rendering = True
        try:
            path = self.current_pdf_path
            doc  = self.get_doc(path)
            pc   = self.page_count_cache[path]
            self.ensure_maps_for_pdf(path, pc)

            pg_map = self.page_groups_map[path]
            order  = self.page_order[path]

            clear_layout(self.thumbs_grid)

            ratio_w_h = 1.0 / 1.41421356237
            thumb_w   = self._thumb_base_w
            thumb_h   = int(thumb_w / ratio_w_h)
            if thumb_h > 360:
                thumb_h = 360
                thumb_w = int(thumb_h * ratio_w_h)

            cell_w     = thumb_w + 28
            h_gap      = 14
            viewport_w = self.scroll.viewport().width()
            columns    = max(1, (viewport_w - 20) // (cell_w + h_gap))
            total_w    = columns * cell_w + max(0, columns - 1) * h_gap
            side_pad   = max(10, (viewport_w - total_w) // 2)
            self.thumbs_grid.setContentsMargins(side_pad, 10, side_pad, 10)

            mat   = fitz.Matrix(THUMB_SCALE, THUMB_SCALE)
            items = self._build_render_items(pg_map, order, pc)

            for grid_i, item in enumerate(items):
                row = grid_i // columns
                col = grid_i % columns
                if item['type'] == 'page':
                    self._add_thumb_card(
                        item['visual_i'], item['actual_i'], row, col,
                        doc.load_page(item['actual_i']), mat,
                        thumb_w, thumb_h, cell_w,
                        item['group_num']
                    )
                else:
                    self._add_group_deck(
                        item['group_num'], item['pages'], row, col,
                        doc, mat, thumb_w, thumb_h, cell_w, path
                    )

            self.thumbs_container.updateGeometry()
            self.thumbs_container.update()
            self.scroll.viewport().update()
        finally:
            self._rendering = False

    def reorder_pages(self, src_visual: int, dst_visual: int):
        path = self.current_pdf_path
        if path not in self.page_order:
            return
        order = self.page_order[path]
        item  = order.pop(src_visual)
        order.insert(dst_visual, item)
        self._render_timer.start(0)

    def set_drop_indicator(self, idx):
        for i in range(self.thumbs_grid.count()):
            item = self.thumbs_grid.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), DraggableCard):
                w = item.widget()
                if w._visual_idx == idx:
                    w.setStyleSheet(
                        "QFrame{ background: rgba(60,179,113,0.18); "
                        "border-radius: 16px; border: 2px solid #3CB371; }"
                    )
                else:
                    w.setStyleSheet(
                        "QFrame{ background: transparent; border-radius: 16px; }"
                    )

    def _add_thumb_card(self, visual_i, actual_i, row, col,
                        page, mat, thumb_w, thumb_h, cell_w,
                        group_num):
        pixmap = safe_thumbnail_render(page, mat)

        card = DraggableCard(visual_i, self)
        card.setFixedSize(cell_w, thumb_h + 44)
        card.setStyleSheet("QFrame{ background: transparent; border-radius: 16px; }")

        vbox = QtWidgets.QVBoxLayout(card)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        paper_color = group_color(group_num) if group_num is not None else None
        paper       = FullBorderPaper(thumb_w, thumb_h, paper_color, pixmap)

        shadow = QtWidgets.QGraphicsDropShadowEffect(paper)
        shadow.setBlurRadius(20 if group_num is None else 24)
        shadow.setOffset(0, 3)
        shadow.setColor(QtGui.QColor(0, 0, 0, 50 if group_num is None else 70))
        paper.setGraphicsEffect(shadow)

        if group_num is not None:
            _btn_size = 42
            indicator = GroupButton(
                group_num, group_color(group_num),
                bg_alpha=140, parent=paper,
            )
            indicator.setFixedSize(_btn_size, _btn_size)
            indicator.setChecked(False)
            indicator.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            indicator.move((thumb_w - _btn_size) // 2, (thumb_h - _btn_size) // 2)

        num = QtWidgets.QLabel(str(actual_i + 1))
        num.setAlignment(QtCore.Qt.AlignCenter)
        num.setFixedHeight(28)
        num.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        num.setStyleSheet("font-weight: 900; color: rgba(255,255,255,0.7);")

        vbox.addWidget(paper, alignment=QtCore.Qt.AlignHCenter)
        vbox.addWidget(num,   alignment=QtCore.Qt.AlignHCenter)

        self.thumbs_grid.addWidget(card, row, col)

    # ── group management ──────────────────────────────────────────────────────

    def _build_render_items(self, pg_map, order, page_count):
        group_pages_list = defaultdict(list)
        for vi, ai in enumerate(order):
            g = pg_map[ai]
            if g is not None:
                group_pages_list[g].append((vi, ai))

        items     = []
        processed = set()
        for vi, ai in enumerate(order):
            g = pg_map[ai]
            if g is None:
                items.append({'type': 'page', 'visual_i': vi, 'actual_i': ai, 'group_num': None})
            elif g == self._active_group:
                items.append({'type': 'page', 'visual_i': vi, 'actual_i': ai, 'group_num': g})
            elif g not in processed:
                items.append({'type': 'deck', 'group_num': g, 'pages': group_pages_list[g]})
                processed.add(g)
        return items

    def _add_group_deck(self, group_num, pages, row, col, doc, mat, thumb_w, thumb_h, cell_w, path):
        pixmaps  = [safe_thumbnail_render(doc.load_page(ai), mat) for _, ai in pages]
        pdf_base = os.path.splitext(os.path.basename(path))[0]
        names    = self.group_names_map.get(path, {})
        def_name = names.get(group_num, f"{pdf_base}_group_{group_num:02d}")
        deck = GroupDeck(group_num, pixmaps, def_name, self, thumb_w, thumb_h, cell_w)
        self.thumbs_grid.addWidget(deck, row, col)

    def _add_group_button(self, num: int):
        btn = GroupButton(num, group_color(num))
        btn.clicked.connect(lambda _, n=num: self._handle_group_click(n))
        self._btn_group.addButton(btn)
        self._groups_layout.insertWidget(num - 1, btn)
        self._group_btns.append(btn)

    def _handle_group_click(self, num: int):
        if self._active_group == num:
            self._active_group = None
            self._btn_group.setExclusive(False)
            self._group_btns[num - 1].setChecked(False)
            self._btn_group.setExclusive(True)
        else:
            self._active_group = num
        self._render_timer.start(0)

    def _on_add_group(self):
        if self._num_groups >= MAX_GROUPS:
            return
        self._num_groups += 1
        self._add_group_button(self._num_groups)
        self._group_btns[-1].setChecked(True)
        if self._num_groups >= MAX_GROUPS:
            self._add_group_btn.hide()
        QtCore.QTimer.singleShot(50, lambda: self._groups_scroll.horizontalScrollBar().setValue(
            self._groups_scroll.horizontalScrollBar().maximum()
        ))

    def expand_group(self, group_num: int):
        self._active_group = group_num
        if group_num <= len(self._group_btns):
            self._group_btns[group_num - 1].setChecked(True)
        self._render_timer.start(0)

    def set_group_name(self, group_num: int, name: str):
        path = self.current_pdf_path
        if path:
            self.group_names_map.setdefault(path, {})[group_num] = name.strip()

    def toggle_page_group(self, visual_i: int):
        path = self.current_pdf_path
        if not path:
            return
        order = self.page_order.get(path, [])
        if visual_i >= len(order):
            return
        actual_i = order[visual_i]
        pg = self.page_groups_map[path]
        pg[actual_i] = None if pg[actual_i] == self._active_group else self._active_group
        self._render_timer.start(0)
