import os
import fitz
from PySide6 import QtWidgets, QtCore, QtGui
from ..theme import THEME_MGR
from .. import icons as _icons
from ..widgets import _HoverMixin


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

    def __init__(self, page_num: int, page: fitz.Page, scale: float, parent=None):
        super().__init__(parent)
        self._page_num      = page_num
        self._page          = page
        self._scale         = scale
        self._pixmap:       QtGui.QPixmap | None            = None
        self._words:        list[tuple[QtCore.QRectF, str]] = []
        self._sel_start:    QtCore.QPointF | None           = None
        self._sel_end:      QtCore.QPointF | None           = None
        self._highlighted:  list[QtCore.QRectF]             = []
        self._selected_text = ""
        self.setCursor(QtCore.Qt.IBeamCursor)
        self.setMouseTracking(True)
        self._render()

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self):
        mat = fitz.Matrix(self._scale, self._scale)
        pix = self._page.get_pixmap(matrix=mat, alpha=False)
        img = QtGui.QImage(pix.samples, pix.width, pix.height,
                           pix.stride, QtGui.QImage.Format_RGB888)
        self._pixmap = QtGui.QPixmap.fromImage(img)
        self.setFixedSize(self._pixmap.size())
        self._load_words()

    def _load_words(self):
        self._words.clear()
        pr = self._page.rect
        pw = max(pr.width, 1.0)
        ph = max(pr.height, 1.0)
        sw = float(self._pixmap.width())
        sh = float(self._pixmap.height())
        for w in self._page.get_text("words"):
            x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
            self._words.append((
                QtCore.QRectF(x0 / pw * sw, y0 / ph * sh,
                              (x1 - x0) / pw * sw, (y1 - y0) / ph * sh),
                text,
            ))

    def rescale(self, scale: float):
        self._scale         = scale
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
        hits = [(r, t) for r, t in self._words if r.intersects(rb)]
        hits.sort(key=lambda x: (round(x[0].top(), 1), x[0].left()))
        self._highlighted   = [r for r, _ in hits]
        self._selected_text = " ".join(t for _, t in hits)

    # ── cursor → PDF coordinates ───────────────────────────────────────────────

    def _emit_cursor(self, pos: QtCore.QPoint):
        if not self._pixmap:
            return
        pr   = self._page.rect
        pdf_x = pos.x() / float(self._pixmap.width())  * pr.width
        pdf_y = pos.y() / float(self._pixmap.height()) * pr.height
        self.cursor_moved.emit(self._page_num, pdf_x, pdf_y)

    # ── events ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.page_clicked.emit(self)
            self._sel_start     = QtCore.QPointF(event.pos())
            self._sel_end       = self._sel_start
            self._highlighted.clear()
            self._selected_text = ""
            self.update()

    def mouseMoveEvent(self, event):
        self._emit_cursor(event.pos())
        if event.buttons() & QtCore.Qt.LeftButton and self._sel_start is not None:
            self._sel_end = QtCore.QPointF(event.pos())
            self._update_highlight()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._sel_start is not None:
            self._sel_end = QtCore.QPointF(event.pos())
            self._update_highlight()
            if self._selected_text:
                QtWidgets.QApplication.clipboard().setText(self._selected_text)
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
        p.end()


class ScreenViewer(QtWidgets.QWidget):
    """Full-page PDF viewer with text selection, zoom, and clipboard copy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc:          fitz.Document | None = None
        self._path:         str | None           = None
        self._scale:        float                = _DEFAULT_SCALE
        self._pages:        list[PageWidget]     = []
        self._current_page: int                  = 0
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
        self._current_page = 0
        self._lbl_pages.setText(f"1/{self._doc.page_count}")
        self._lbl_cursor.setText("")
        self._scale = self._fit_scale()
        self._render_pages()

    def has_doc(self) -> bool:
        return self._doc is not None

    def close_doc(self):
        """Release the loaded PDF and rendered pages (e.g. before discarding the tab)."""
        self._clear_pages()
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

        root.addWidget(self._scroll, 1)

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
        self._btn_first_page.clicked.connect(lambda: self._scroll_to_page(0))
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
        root.addWidget(sb)
        self.apply_theme()

    # ── theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self):
        t = THEME_MGR.get()

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
        for pw in self._pages:
            pw.deleteLater()
        self._pages.clear()

    def _render_pages(self):
        self._clear_pages()
        if not self._doc:
            return
        for i in range(self._doc.page_count):
            page = self._doc.load_page(i)
            pw   = PageWidget(i, page, self._scale)
            pw.page_clicked.connect(self._on_page_clicked)
            pw.cursor_moved.connect(self._on_cursor_moved)
            pw.cursor_left.connect(self._on_cursor_left)

            shadow = QtWidgets.QGraphicsDropShadowEffect(pw)
            shadow.setBlurRadius(18)
            shadow.setOffset(2, 4)
            shadow.setColor(QtGui.QColor(0, 0, 0, 110))
            pw.setGraphicsEffect(shadow)

            self._vbox.addWidget(pw, alignment=QtCore.Qt.AlignHCenter)
            self._pages.append(pw)

    def _on_page_clicked(self, source: PageWidget):
        for pw in self._pages:
            if pw is not source:
                pw.clear_selection()

    def _scroll_to_page(self, page_num: int):
        if not self._pages or page_num < 0 or page_num >= len(self._pages):
            return
        pw = self._pages[page_num]
        self._scroll.verticalScrollBar().setValue(pw.pos().y())

    # ── current page tracking ─────────────────────────────────────────────────

    def _update_current_page(self):
        if not self._pages or not self._doc:
            return
        vp_mid = (self._scroll.verticalScrollBar().value()
                  + self._scroll.viewport().height() / 2)
        best = 0
        for i, pw in enumerate(self._pages):
            if pw.pos().y() <= vp_mid:
                best = i
            else:
                break
        self._current_page = best
        self._lbl_pages.setText(f"{best + 1}/{self._doc.page_count}")

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
            self._scroll_to_page(0)
        elif key == QtCore.Qt.Key_End:
            self._scroll_to_page(n - 1)
        elif key == QtCore.Qt.Key_PageDown:
            self._scroll_to_page(min(self._current_page + 1, n - 1))
        elif key == QtCore.Qt.Key_PageUp:
            self._scroll_to_page(max(self._current_page - 1, 0))
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


# ── Tabbed viewer (Chrome-style tabs, one per open PDF) ────────────────────────

class PdfViewerTabs(QtWidgets.QWidget):
    """Holds one ScreenViewer per open PDF, switchable via a Chrome-like tab bar."""

    all_closed = QtCore.Signal()   # emitted when the last tab is closed

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        root.addWidget(self._tabs)

        self._add_btn = QtWidgets.QToolButton()
        self._add_btn.setText("+")
        self._add_btn.setToolTip("Відкрити ще один PDF")
        self._add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._add_btn.setAutoRaise(True)
        self._add_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._add_btn.clicked.connect(self._on_add_clicked)
        self._tabs.setCornerWidget(self._add_btn, QtCore.Qt.TopRightCorner)

    # ── public API ────────────────────────────────────────────────────────────

    def add_tab(self, path: str):
        for i in range(self._tabs.count()):
            if self._tabs.widget(i)._path == path:
                self._tabs.setCurrentIndex(i)
                return
        viewer = ScreenViewer()
        viewer.setAcceptDrops(False)   # adding files goes through the "+" button / drop zone
        viewer.load_pdf(path)
        idx = self._tabs.addTab(viewer, os.path.basename(path))
        self._tabs.setTabToolTip(idx, path)
        self._tabs.setCurrentIndex(idx)

    def reset(self):
        while self._tabs.count():
            w = self._tabs.widget(0)
            self._tabs.removeTab(0)
            w.close_doc()
            w.deleteLater()

    def paths(self) -> list[str]:
        return [self._tabs.widget(i)._path for i in range(self._tabs.count())]

    def current_viewer(self) -> ScreenViewer | None:
        return self._tabs.currentWidget()

    def apply_theme(self):
        t = THEME_MGR.get()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {t.bg_main}; }}
            QTabBar {{ background: {t.bg_sidebar}; }}
            QTabBar::tab {{
                background: {t.bg_sidebar};
                color: rgba(255,255,255,0.6);
                padding: 7px 14px;
                border: none;
                border-right: 1px solid {t.bg_border};
            }}
            QTabBar::tab:selected {{
                background: {t.bg_main};
                color: rgba(255,255,255,0.95);
            }}
            QTabBar::tab:hover:!selected {{ background: {t.bg_hover}; }}
        """)
        self._add_btn.setStyleSheet(
            "QToolButton { color: rgba(255,255,255,0.55); background: transparent;"
            " border: none; font-size: 15px; padding: 4px 12px; }"
            " QToolButton:hover { color: white; }"
        )
        for i in range(self._tabs.count()):
            self._tabs.widget(i).apply_theme()

    # ── internals ─────────────────────────────────────────────────────────────

    def _close_tab(self, index: int):
        w = self._tabs.widget(index)
        self._tabs.removeTab(index)
        w.close_doc()
        w.deleteLater()
        if self._tabs.count() == 0:
            self.all_closed.emit()

    def _on_add_clicked(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Відкрити PDF", "", "PDF files (*.pdf)"
        )
        for p in paths:
            self.add_tab(p)
