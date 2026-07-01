import logging
import math
import os
from collections import OrderedDict, defaultdict, deque

import fitz
from PySide6 import QtCore, QtGui, QtWidgets

from ..constants import MAX_GROUPS, THUMB_SCALE, group_color
from ..pdf_utils import clear_layout, safe_thumbnail_render
from ..ui.widgets import (
    DraggableCard,
    FullBorderPaper,
    GroupButton,
    GroupDeck,
    ThumbnailActionButton,
)

_log = logging.getLogger(__name__)

_A4_ASPECT_RATIO = math.sqrt(2)   # A4: висота/ширина


class ScreenMergeMulti(QtWidgets.QWidget):
    """Уніфікований екран редагування PDF: розділення та об'єднання."""

    def __init__(self, go_back):
        super().__init__()
        self.go_back   = go_back

        self.files:     list[str] = []   # [path, ...]
        self.doc_cache: dict      = {}   # path → fitz.Document

        self.page_list:      list[tuple[str, int]] = []
        self.page_groups:    list[int | None]      = []
        self.page_rotations: list[int]             = []   # degrees: 0, 90, 180, 270
        self.group_names:    dict[int, str]        = {}   # group_num → output filename

        self._active_group = 1
        self._num_groups   = 4
        self._group_btns: list[GroupButton] = []
        self._btn_group = QtWidgets.QButtonGroup(self)
        self._btn_group.setExclusive(True)

        self._rendering    = False
        self._thumb_base_w = 210
        self._drag_src:     int | None = None
        self._drop_idx:     int | None = None
        self._dragged_card             = None   # картка виведена з гриду під час drag
        self._drag_active:  bool       = False  # True між start_drag і end_drag
        self._vi_to_card:   dict       = {}     # vi → DraggableCard, актуально під час drag
        self._pixmap_cache: OrderedDict = OrderedDict()
        self._page_ar_cache: dict      = {}    # (path, actual_i) → float  w/h ratio
        self._undo_stack:   deque      = deque(maxlen=50)

        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self.render_thumbnails)

        self._viewport_debounce = QtCore.QTimer(self)
        self._viewport_debounce.setSingleShot(True)
        self._viewport_debounce.timeout.connect(self.render_thumbnails)

        self._build_ui()

    # ── public API ────────────────────────────────────────────────────────────

    def has_files(self) -> bool:
        return bool(self.files)

    def add_file(self, path: str):
        """Додає PDF за шляхом `path`. Кидає виняток fitz, якщо файл нечитаний —
        стан екрана при цьому лишається незмінним."""
        if path in self.files:
            return
        doc = self.get_doc(path)
        self.files.append(path)

        for i in range(doc.page_count):
            self.page_list.append((path, i))
            self.page_groups.append(None)
            self.page_rotations.append(0)

        self._update_header()
        self._render_timer.start(0)

    def reset(self):
        for doc in self.doc_cache.values():
            try:
                doc.close()
            except Exception:
                _log.debug("Не вдалося закрити документ", exc_info=True)
        self.doc_cache.clear()
        self.files.clear()
        self.page_list.clear()
        self.page_groups.clear()
        self.page_rotations.clear()
        self._active_group = 1
        self.group_names.clear()
        self._drag_src     = None
        self._drop_idx     = None
        self._drag_active  = False
        self._dragged_card = None   # card lives in grid; clear_layout below handles deletion
        self._pixmap_cache.clear()
        self._page_ar_cache.clear()
        self._reset_group_buttons()
        clear_layout(self.thumbs_grid)
        self._update_header()

    def get_doc(self, path: str) -> fitz.Document:
        if path not in self.doc_cache:
            self.doc_cache[path] = fitz.open(path)
        return self.doc_cache[path]

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)

        self.lbl_files = QtWidgets.QLabel("")
        self.lbl_files.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_files.setStyleSheet(
            "font-weight: 600; font-size: 14px; color: rgba(255,255,255,0.85); padding: 8px 0;"
        )
        root.addWidget(self.lbl_files)

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
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
                margin: 0;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.18);
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.38);
            }
            QScrollBar::handle:vertical:pressed {
                background: rgba(255,255,255,0.55);
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical  { background: none; }
        """)
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
        self.scroll.viewport().setAcceptDrops(True)
        self.scroll.viewport().setFocusPolicy(QtCore.Qt.StrongFocus)

        sep = QtWidgets.QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #2a3045;")
        root.addWidget(sep)

        bottom_bar = QtWidgets.QWidget()
        bottom_bar.setStyleSheet("background: transparent;")
        bv = QtWidgets.QVBoxLayout(bottom_bar)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)

        # ── рядок 1: групи ────────────────────────────────────────────────────
        groups_row = QtWidgets.QWidget()
        groups_row.setStyleSheet("background: transparent;")
        gr = QtWidgets.QHBoxLayout(groups_row)
        gr.setContentsMargins(12, 6, 12, 4)
        gr.setSpacing(0)

        gs = QtWidgets.QScrollArea()
        gs.setFixedHeight(54)
        gs.setWidgetResizable(True)
        gs.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        gs.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        gs.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 3px; background: transparent; }
            QScrollBar::handle:horizontal { background: rgba(255,255,255,0.18); border-radius: 1px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)
        self._groups_container = QtWidgets.QWidget()
        self._groups_container.setStyleSheet("background: transparent;")
        self._groups_layout = QtWidgets.QHBoxLayout(self._groups_container)
        self._groups_layout.setSpacing(6)
        self._groups_layout.setContentsMargins(0, 2, 8, 2)

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
                background: transparent; border: 1.5px dashed #333545;
                border-radius: 7px; color: #5c6480; font-size: 18px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(255,255,255,0.05); border-color: #505470; color: #8590b8; }
        """)
        self._add_group_btn.clicked.connect(self._on_add_group)
        self._groups_layout.addWidget(self._add_group_btn)
        self._groups_layout.addStretch()
        gs.setWidget(self._groups_container)
        self._groups_scroll = gs
        gr.addWidget(gs)
        bv.addWidget(groups_row)

        root.addWidget(bottom_bar)

        undo_sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        undo_sc.activated.connect(self.undo)

    def _push_undo(self):
        self._undo_stack.append((
            list(self.page_list),
            list(self.page_groups),
            list(self.page_rotations),
        ))

    def undo(self):
        if not self._undo_stack:
            return
        self.page_list, self.page_groups, self.page_rotations = self._undo_stack.pop()
        self._render_timer.start(0)

    def _show_help(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Довідка — PDF Редактор")
        dlg.setFixedWidth(500)
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        dlg.setStyleSheet("""
            QDialog { background: #1e2029; }
            QLabel  { background: transparent; }
        """)

        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(0)

        def section(title):
            lbl = QtWidgets.QLabel(title)
            lbl.setStyleSheet(
                "font-size: 11px; font-weight: 700; letter-spacing: 1px;"
                " color: rgba(255,255,255,0.35); padding-top: 14px; padding-bottom: 4px;"
            )
            lay.addWidget(lbl)

        def row(icon, text):
            w   = QtWidgets.QWidget()
            w.setStyleSheet("background: transparent;")
            hl  = QtWidgets.QHBoxLayout(w)
            hl.setContentsMargins(0, 2, 0, 2)
            hl.setSpacing(10)
            dot = QtWidgets.QLabel(icon)
            dot.setFixedWidth(18)
            dot.setStyleSheet("font-size: 13px; color: #53A8FF;")
            lbl = QtWidgets.QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.78);")
            hl.addWidget(dot)
            hl.addWidget(lbl, 1)
            lay.addWidget(w)

        title = QtWidgets.QLabel("PDF Редактор")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: white; padding-bottom: 2px;"
        )
        lay.addWidget(title)

        sub = QtWidgets.QLabel(
            "Розподіляй сторінки по групах і експортуй кожну групу як окремий PDF"
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.40);")
        lay.addWidget(sub)

        section("ПОРЯДОК ДІЙ")
        row("1", "Завантаж PDF через стартовий екран або перетягни файли на область мініатюр")
        row("2", "Обери активну групу — натисни на кнопку групи в нижній панелі")
        row("3", "Клікай на сторінки щоб додавати їх до активної групи")
        row("4", "Задай назву файлу — клікни на підпис під колодою карток і введи текст")
        row("5", "Натисни «Експортувати PDF» — кожна група збережеться як окремий файл")

        section("ДОДАТКОВІ МОЖЛИВОСТІ")
        row("⟳", "Перетягування мініатюри — змінює порядок сторінок")
        row("⊞", "Правий клік на мініатюрі — згортає групу в колоду")
        row("▶", "Клік на колоду — розгортає групу")
        row("⊕", "Ctrl + Scroll — масштаб мініатюр (менше ↔ більше)")
        row("⤓", "Перетягування PDF на область мініатюр — додає файл до сесії")
        row("✓", "«Виділити все» призначає всі сторінки до поточної активної групи")

        div = QtWidgets.QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #252830; margin-top: 16px;")
        lay.addWidget(div)

        close_btn = QtWidgets.QPushButton("Зрозуміло")
        close_btn.setFixedHeight(38)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        close_btn.clicked.connect(dlg.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #262c40; border: 1px solid #333545;
                border-radius: 7px; color: rgba(255,255,255,0.75);
                font-size: 13px; margin-top: 12px;
            }
            QPushButton:hover { background: #2e3650; color: white; border-color: #53A8FF; }
            QPushButton:pressed { background: rgba(78,154,241,0.2); }
        """)
        lay.addWidget(close_btn)

        dlg.exec()

    def _update_header(self):
        if not self.files:
            self.lbl_files.setText("")
            return
        names = [os.path.basename(p) for p in self.files]
        if len(names) == 1:
            self.lbl_files.setText(names[0])
        elif len(names) <= 3:
            self.lbl_files.setText("  +  ".join(names))
        else:
            self.lbl_files.setText(f"{names[0]}  +  ...  ({len(names)} файлів)")

    # ── events ────────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport():
            t = event.type()
            if t == QtCore.QEvent.Resize:
                if self.page_list:
                    self._viewport_debounce.start(180)
            elif t == QtCore.QEvent.KeyPress:
                if (event.modifiers() & QtCore.Qt.ControlModifier
                        and event.key() == QtCore.Qt.Key_Z):
                    self.undo()
                    return True
            elif t == QtCore.QEvent.Wheel:
                if event.modifiers() & QtCore.Qt.ControlModifier:
                    self._zoom_thumbs(event.angleDelta().y())
                    return True
            elif t == QtCore.QEvent.DragEnter:
                if event.mimeData().hasUrls() and any(
                    u.toLocalFile().lower().endswith(".pdf")
                    for u in event.mimeData().urls()
                ):
                    event.acceptProposedAction()
                    return True
            elif t == QtCore.QEvent.DragMove:
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    return True
            elif t == QtCore.QEvent.Drop:
                paths = [u.toLocalFile() for u in event.mimeData().urls()
                         if u.toLocalFile().lower().endswith(".pdf")]
                for path in paths:
                    self._add_file_safe(path)
                event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)

    def _zoom_thumbs(self, delta: int):
        if delta > 0:
            self._thumb_base_w = min(self._thumb_base_w + 20, 400)
        else:
            self._thumb_base_w = max(self._thumb_base_w - 20, 80)
        if self.page_list:
            self._render_timer.start(0)

    def closeEvent(self, event):
        for doc in self.doc_cache.values():
            try:
                doc.close()
            except Exception:
                _log.debug("Не вдалося закрити документ", exc_info=True)
        self.doc_cache.clear()
        self._pixmap_cache.clear()
        super().closeEvent(event)

    def set_group_name(self, group_num: int, name: str):
        self.group_names[group_num] = name.strip()

    # ── drag-and-drop state ───────────────────────────────────────────────────

    def start_drag(self, src_idx: int, card_widget):
        self._drag_src     = src_idx
        self._dragged_card = card_widget
        self._drag_active  = True
        # Ghost the card in place — no grid rebuild means no flicker
        eff = QtWidgets.QGraphicsOpacityEffect(card_widget)
        eff.setOpacity(0.22)
        card_widget.setGraphicsEffect(eff)

    def end_drag(self):
        self._drag_active  = False
        self._dragged_card = None   # clear_layout in the upcoming render handles deletion
        self._drag_src     = None
        self._drop_idx     = None
        self._render_timer.start(0)
        self.scroll.viewport().setFocus()

    _PIXMAP_CACHE_MAX = 200

    def _get_pixmap(self, path: str, actual_i: int, mat, rotation: int = 0) -> QtGui.QPixmap:
        key = (path, actual_i, rotation)
        if key in self._pixmap_cache:
            self._pixmap_cache.move_to_end(key)
            return self._pixmap_cache[key]
        render_mat = (
            fitz.Matrix(THUMB_SCALE, THUMB_SCALE).prerotate(rotation) if rotation else mat
        )
        pixmap = safe_thumbnail_render(self.get_doc(path).load_page(actual_i), render_mat)
        self._pixmap_cache[key] = pixmap
        if len(self._pixmap_cache) > self._PIXMAP_CACHE_MAX:
            self._pixmap_cache.popitem(last=False)
        return pixmap

    def _get_page_ar(self, path: str, actual_i: int) -> float:
        """Return native page aspect ratio (width/height) accounting for PDF /Rotate."""
        key = (path, actual_i)
        if key not in self._page_ar_cache:
            rect = self.get_doc(path).load_page(actual_i).rect
            self._page_ar_cache[key] = (rect.width / rect.height) if rect.height > 0 else 1.0
        return self._page_ar_cache[key]

    # ── DraggableCard interface ────────────────────────────────────────────────

    def toggle_page_group(self, visual_i: int):
        if visual_i >= len(self.page_groups) or self._active_group is None:
            return
        self._push_undo()
        cur = self.page_groups[visual_i]
        self.page_groups[visual_i] = None if cur == self._active_group else self._active_group
        self._render_timer.start(0)

    def rotate_page(self, visual_i: int):
        if visual_i >= len(self.page_rotations):
            return
        self._push_undo()
        self.page_rotations[visual_i] = (self.page_rotations[visual_i] + 90) % 360
        path, ai = self.page_list[visual_i]
        for rot in (0, 90, 180, 270):
            self._pixmap_cache.pop((path, ai, rot), None)
        self._render_timer.start(0)

    def delete_page(self, visual_i: int):
        if visual_i >= len(self.page_list):
            return
        self._push_undo()
        path, ai = self.page_list[visual_i]
        self.page_list.pop(visual_i)
        self.page_groups.pop(visual_i)
        self.page_rotations.pop(visual_i)
        for rot in (0, 90, 180, 270):
            self._pixmap_cache.pop((path, ai, rot), None)
        if not any(p == path for p, _ in self.page_list):
            self.files.remove(path)
            self._page_ar_cache = {k: v for k, v in self._page_ar_cache.items() if k[0] != path}
        self._update_header()
        self._render_timer.start(0)

    def set_drop_indicator(self, idx):
        self._drop_idx = idx

    def reorder_pages(self, src_visual: int, dst_visual: int):
        if src_visual >= len(self.page_list) or dst_visual >= len(self.page_list):
            return
        self._push_undo()
        page = self.page_list.pop(src_visual)
        grp  = self.page_groups.pop(src_visual)
        rot  = self.page_rotations.pop(src_visual)
        # insert BEFORE dst_visual; after pop(src), if src < dst the index shifted by -1
        insert_at = dst_visual - 1 if src_visual < dst_visual else dst_visual
        self.page_list.insert(insert_at, page)
        self.page_groups.insert(insert_at, grp)
        self.page_rotations.insert(insert_at, rot)
        # render is triggered by end_drag(), not here — prevents a grid rebuild
        # while drag.exec() is still running its own event loop

    # ── render ────────────────────────────────────────────────────────────────

    def _build_render_items(self):
        group_pages: dict[int, list] = defaultdict(list)
        for vi, (path, ai) in enumerate(self.page_list):
            g = self.page_groups[vi]
            if g is not None:
                group_pages[g].append((vi, path, ai))

        items     = []
        processed = set()

        for vi, (path, ai) in enumerate(self.page_list):
            g   = self.page_groups[vi]
            rot = self.page_rotations[vi]
            if g is None:
                items.append({'type': 'page', 'visual_i': vi, 'path': path, 'actual_i': ai,
                              'group_num': None, 'rotation': rot})
            elif g == self._active_group:
                items.append({'type': 'page', 'visual_i': vi, 'path': path, 'actual_i': ai,
                              'group_num': g, 'rotation': rot})
            elif g not in processed:
                items.append({'type': 'deck', 'group_num': g, 'pages': group_pages[g]})
                processed.add(g)

        return items

    def render_thumbnails(self):
        if self._rendering or not self.page_list:
            return
        self._rendering = True
        try:
            clear_layout(self.thumbs_grid)
            self._vi_to_card = {}

            thumb_w, base_thumb_h, cell_w, columns = self._thumb_grid_geometry()
            mat          = fitz.Matrix(THUMB_SCALE, THUMB_SCALE)
            file_idx_map = {path: idx + 1 for idx, path in enumerate(self.files)}
            items        = self._build_render_items()

            for grid_i, item in enumerate(items):
                row, col = grid_i // columns, grid_i % columns
                if item['type'] == 'page':
                    self._render_page_item(item, row, col, mat, file_idx_map, thumb_w, cell_w)
                elif item['type'] == 'deck':
                    self._add_group_deck(item['group_num'], item['pages'],
                                         row, col, mat, thumb_w, base_thumb_h, cell_w)

            self.thumbs_container.updateGeometry()
            self.thumbs_container.update()
            self.scroll.viewport().update()
        finally:
            self._rendering = False

    def _thumb_grid_geometry(self) -> tuple[int, int, int, int]:
        """Обчислює (thumb_w, base_thumb_h, cell_w, columns) і виставляє відступи гриду
        так, щоб грид був центрований по ширині viewport'а."""
        thumb_w      = self._thumb_base_w
        base_thumb_h = int(thumb_w * _A4_ASPECT_RATIO)   # A4 portrait reference height
        if base_thumb_h > 360:
            base_thumb_h = 360
            thumb_w      = int(base_thumb_h / _A4_ASPECT_RATIO)

        cell_w     = thumb_w + 28
        h_gap      = 14
        viewport_w = self.scroll.viewport().width()
        columns    = max(1, (viewport_w - 20) // (cell_w + h_gap))
        total_w    = columns * cell_w + max(0, columns - 1) * h_gap
        side_pad   = max(10, (viewport_w - total_w) // 2)
        self.thumbs_grid.setContentsMargins(side_pad, 10, side_pad, 10)
        return thumb_w, base_thumb_h, cell_w, columns

    def _render_page_item(self, item: dict, row: int, col: int, mat, file_idx_map: dict,
                           thumb_w: int, cell_w: int) -> None:
        vi, path, ai = item['visual_i'], item['path'], item['actual_i']
        g_num      = item['group_num']
        rot        = item['rotation']
        file_color = group_color((file_idx_map[path] - 1) % 8 + 1)
        g_color    = group_color(g_num) if g_num else None
        pixmap     = self._get_pixmap(path, ai, mat, rot)
        # Effective AR after user rotation: 90/270 → swap w/h
        ar      = self._get_page_ar(path, ai)
        eff_ar  = ar if rot % 180 == 0 else 1.0 / ar
        thumb_h = max(40, min(int(thumb_w / eff_ar), 500))
        self._add_thumb_card(
            vi, ai, file_idx_map[path], row, col, pixmap,
            thumb_w, thumb_h, cell_w, file_color, g_color, g_num, rot
        )

    def _add_group_deck(self, group_num, pages, row, col, mat, thumb_w, thumb_h, cell_w):
        pixmaps  = [self._get_pixmap(path, ai, mat, self.page_rotations[vi])
                    for vi, path, ai in pages]
        def_name = self.group_names.get(group_num, f"merged_{group_num:02d}")
        deck = GroupDeck(group_num, pixmaps, def_name, self, thumb_w, thumb_h, cell_w)
        self.thumbs_grid.addWidget(deck, row, col)

    def _add_thumb_card(self, visual_i, actual_i, file_idx, row, col, pixmap,
                        thumb_w, thumb_h, cell_w,
                        file_color, g_color, group_num, rotation=0):
        card = DraggableCard(visual_i, self)
        card.setFixedSize(cell_w, thumb_h + 60)
        card.setStyleSheet("QFrame{ background: transparent; border-radius: 16px; }")

        vbox = QtWidgets.QVBoxLayout(card)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        paper = self._build_thumb_paper(pixmap, thumb_w, thumb_h, g_color, group_num)
        strip = self._build_thumb_info_strip(actual_i, file_idx, file_color, cell_w, visual_i)

        vbox.addWidget(paper, alignment=QtCore.Qt.AlignHCenter)
        vbox.addWidget(strip, alignment=QtCore.Qt.AlignHCenter)

        self.thumbs_grid.addWidget(card, row, col)
        self._vi_to_card[visual_i] = card

    def _build_thumb_paper(self, pixmap, thumb_w: int, thumb_h: int, g_color, group_num):
        """Аркуш сторінки з тінню та, за наявності групи, кружечком-індикатором групи."""
        paper = FullBorderPaper(thumb_w, thumb_h, g_color, pixmap)

        shadow = QtWidgets.QGraphicsDropShadowEffect(paper)
        shadow.setBlurRadius(20 if group_num is None else 24)
        shadow.setOffset(0, 3)
        shadow.setColor(QtGui.QColor(0, 0, 0, 50 if group_num is None else 70))
        paper.setGraphicsEffect(shadow)

        if group_num is not None and g_color is not None:
            bs  = 42
            ind = GroupButton(group_num, g_color, bg_alpha=140, parent=paper)
            ind.setFixedSize(bs, bs)
            ind.setChecked(False)
            ind.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            ind.move(4, 4)
            ind.raise_()
        return paper

    def _build_thumb_info_strip(self, actual_i: int, file_idx: int, file_color: str,
                                 cell_w: int, visual_i: int) -> QtWidgets.QWidget:
        """Підпис "Ф-N с.M" під сторінкою + кнопки повороту/видалення."""
        fc    = QtGui.QColor(file_color)
        strip = QtWidgets.QWidget()
        strip.setFixedSize(cell_w, 60)
        strip.setStyleSheet("background: transparent;")

        vbox_s = QtWidgets.QVBoxLayout(strip)
        vbox_s.setContentsMargins(0, 4, 0, 4)
        vbox_s.setSpacing(4)

        num = QtWidgets.QLabel(f"Ф-{file_idx} с.{actual_i + 1}")
        num.setAlignment(QtCore.Qt.AlignCenter)
        num.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        num.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.9);"
            f" background: rgba({fc.red()},{fc.green()},{fc.blue()},77);"
            f" border-radius: 4px; padding: 0 6px;"
        )
        vbox_s.addWidget(num, alignment=QtCore.Qt.AlignHCenter)

        btns_row = QtWidgets.QWidget()
        btns_row.setStyleSheet("background: transparent;")
        btns_hl = QtWidgets.QHBoxLayout(btns_row)
        btns_hl.setContentsMargins(0, 0, 0, 0)
        btns_hl.setSpacing(8)

        rot_btn = ThumbnailActionButton("rotate", "#C0C4D6", 28, parent=btns_row)
        rot_btn.clicked.connect(lambda checked=False, vi=visual_i: self.rotate_page(vi))
        btns_hl.addWidget(rot_btn)

        del_btn = ThumbnailActionButton("xmark", "#FF7C75", 28, parent=btns_row)
        del_btn.clicked.connect(lambda checked=False, vi=visual_i: self.delete_page(vi))
        btns_hl.addWidget(del_btn)

        vbox_s.addWidget(btns_row, alignment=QtCore.Qt.AlignHCenter)
        return strip

    # ── run merge ─────────────────────────────────────────────────────────────

    def run_merge(self):
        if not self.page_list:
            QtWidgets.QMessageBox.information(self, "Об'єднання", "Немає вибраних PDF.")
            return

        group_pages = self._group_pages_by_group()
        if not group_pages:
            QtWidgets.QMessageBox.information(
                self, "Об'єднання",
                "Призначте сторінки до груп перед об'єднанням."
            )
            return

        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Виберіть папку для збереження результату", ""
        )
        if not out_dir:
            return

        try:
            used_names: set[str] = set()
            for g in sorted(group_pages):
                self._write_merged_group(g, group_pages[g], out_dir, used_names)
            QtWidgets.QMessageBox.information(
                self, "Готово ✅", f"Готово!\nСтворено файлів: {len(group_pages)}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Помилка", f"Сталася помилка:\n{e}")

    def _group_pages_by_group(self) -> dict[int, list[tuple[str, int, int]]]:
        """(шлях, номер сторінки, поворот) для кожної призначеної групи."""
        group_pages: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
        for vi, (path, actual_i) in enumerate(self.page_list):
            g = self.page_groups[vi]
            if g is not None:
                group_pages[g].append((path, actual_i, self.page_rotations[vi]))
        return group_pages

    def _unique_group_filename(self, group_num: int, used_names: set[str]) -> str:
        base = self.group_names.get(group_num, "").strip() or f"merged_group_{group_num:02d}"
        if base.lower().endswith(".pdf"):
            base = base[:-4]
        name = base
        counter = 2
        while name in used_names:
            name = f"{base}_{counter}"
            counter += 1
        used_names.add(name)
        return name

    def _write_merged_group(self, group_num: int, pages: list[tuple[str, int, int]],
                             out_dir: str, used_names: set[str]) -> None:
        """Збирає сторінки однієї групи в один PDF і зберігає його у out_dir."""
        out_doc = fitz.open()
        try:
            for path, actual_i, rot in pages:
                out_doc.insert_pdf(self.get_doc(path), from_page=actual_i, to_page=actual_i)
                if rot:
                    pg = out_doc[out_doc.page_count - 1]
                    pg.set_rotation((pg.rotation + rot) % 360)
            name = self._unique_group_filename(group_num, used_names)
            out_doc.save(os.path.join(out_dir, f"{name}.pdf"))
        finally:
            out_doc.close()

    # ── group management ──────────────────────────────────────────────────────

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
        self._active_group = self._num_groups
        if self._num_groups >= MAX_GROUPS:
            self._add_group_btn.hide()
        self._render_timer.start(0)
        QtCore.QTimer.singleShot(50, lambda: self._groups_scroll.horizontalScrollBar().setValue(
            self._groups_scroll.horizontalScrollBar().maximum()
        ))

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

    def collapse_page_group(self, visual_i: int):
        if visual_i >= len(self.page_groups):
            return
        g = self.page_groups[visual_i]
        if g is None:
            return
        self._active_group = None
        self._btn_group.setExclusive(False)
        self._group_btns[g - 1].setChecked(False)
        self._btn_group.setExclusive(True)
        self._render_timer.start(0)

    def expand_group(self, group_num: int):
        self._active_group = group_num
        if group_num <= len(self._group_btns):
            self._group_btns[group_num - 1].setChecked(True)
        self._render_timer.start(0)

    def select_all(self):
        g = self._active_group if self._active_group is not None else 1
        self._push_undo()
        self.page_groups = [g] * len(self.page_groups)
        self._render_timer.start(0)

    def clear_selection(self):
        self._push_undo()
        self.page_groups = [None] * len(self.page_groups)
        self._render_timer.start(0)

    def _on_add_file(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Додати PDF-файли", "", "PDF files (*.pdf)"
        )
        for path in paths:
            self._add_file_safe(path)

    def _add_file_safe(self, path: str):
        """add_file(), але з показом помилки замість падіння на нечитному PDF."""
        try:
            self.add_file(path)
        except Exception as e:
            _log.warning("Не вдалося відкрити PDF %s", path, exc_info=True)
            QtWidgets.QMessageBox.warning(
                self, "Помилка відкриття файлу",
                f"Не вдалося відкрити файл:\n{path}\n\n{e}",
            )
