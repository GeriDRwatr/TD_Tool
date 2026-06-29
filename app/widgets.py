from PySide6 import QtWidgets, QtCore, QtGui

from .constants import group_color as _group_color
from . import icons as _icons


def _mix_colors(c1: QtGui.QColor, c2: QtGui.QColor, t: float) -> QtGui.QColor:
    t = max(0.0, min(1.0, t))
    return QtGui.QColor(
        int(c1.red()   * (1 - t) + c2.red()   * t),
        int(c1.green() * (1 - t) + c2.green() * t),
        int(c1.blue()  * (1 - t) + c2.blue()  * t),
    )


class _HoverMixin:
    """Tracks hover state via WA_Hover events. Call _init_hover() in __init__."""

    _hover: bool

    def _init_hover(self):
        self._hover = False
        self.setAttribute(QtCore.Qt.WA_Hover)  # type: ignore[attr-defined]

    def event(self, e):
        t = e.type()
        if t == QtCore.QEvent.HoverEnter:
            self._hover = True
            self.update()   # type: ignore[attr-defined]
        elif t == QtCore.QEvent.HoverLeave:
            self._hover = False
            self.update()   # type: ignore[attr-defined]
        return super().event(e)  # type: ignore[misc]


class ThumbnailActionButton(_HoverMixin, QtWidgets.QAbstractButton):
    """Small circular overlay button on a thumbnail card (e.g. rotate icon)."""

    def __init__(self, icon_name: str, color: str = "#8E8E93", size: int = 24,
                 bg_alpha: float = 0.62, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._color     = QtGui.QColor(color)
        self._bg_alpha  = bg_alpha
        self._press     = False
        self.setFixedSize(size, size)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._init_hover()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r  = self.rect().adjusted(1, 1, -1, -1)
        cx = self.width()  / 2.0
        cy = self.height() / 2.0

        bg_a = 0.88 if self._press else (0.80 if self._hover else self._bg_alpha)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(14, 16, 24, int(bg_a * 255)))
        p.drawEllipse(r)

        bc = QtGui.QColor(self._color)
        bc.setAlphaF(0.90 if self._hover else 0.60)
        p.setPen(QtGui.QPen(bc, 1.5))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawEllipse(r)

        icon_sz = self.width() * 0.56
        icon_rf = QtCore.QRectF(cx - icon_sz/2, cy - icon_sz/2, icon_sz, icon_sz)
        ic = QtGui.QColor(self._color)
        ic.setAlphaF(1.0)
        _icons.draw(p, icon_rf, self._icon_name, ic)
        p.end()


class GroupDeck(QtWidgets.QWidget):
    """Анімована стопка карток для згорнутої групи.
    При hover карточки розсуваються по діагоналі. Клік → screen.expand_group().
    Під колодою — QLineEdit для кастомної назви вихідного файлу."""

    MAX_SHADOW = 3
    SO         = 5     # base stacking offset px
    TOP_PAD    = 22    # vertical room above top card for upward hover movement

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
        self._color      = _group_color(group_num)
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

        self._x_center    = (cell_w - thumb_w) // 2
        name_y            = TP + thumb_h + self.MAX_SHADOW * SO + 8
        total_h           = name_y + 18 + 6
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

        for i, (r0, r1) in enumerate(zip(self._rest_tx, self._spread_tx)):
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
            p.setBrush(QtCore.Qt.white)
            p.drawRoundedRect(QtCore.QRectF(card_x, card_y, tw, th), 5, 5)

        p.save()
        p.translate(cx, cy)
        p.rotate(-s * 2.0)
        p.translate(-tw / 2.0, -th / 2.0)

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(0, 0, 0, 55))
        p.drawRoundedRect(QtCore.QRectF(1, 4, tw, th), 5, 5)

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtCore.Qt.white)
        p.drawRoundedRect(QtCore.QRectF(0, 0, tw, th), 5, 5)

        if self._pixmap:
            inner = QtCore.QRectF(2, 2, tw - 4, th - 4)
            clip  = QtGui.QPainterPath()
            clip.addRoundedRect(inner, 4.0, 4.0)
            p.save()
            p.setClipPath(clip)
            p.drawPixmap(inner.toAlignedRect(), self._pixmap)
            p.restore()

        pen_out = QtGui.QPen(color, 3.8)
        pen_out.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen_out)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(QtCore.QRectF(0, 0, tw, th), 5, 5)

        echo = QtGui.QColor(color)
        echo.setAlphaF(0.65)
        pen_in = QtGui.QPen(echo, 2.0)
        pen_in.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen_in)
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


class FullBorderPaper(QtWidgets.QWidget):
    """Карточка сторінки: білий фон + мініатюра + кольорова рамка.
    color=None → тонка сіра рамка (непризначена сторінка)."""

    def __init__(self, thumb_w, thumb_h, color=None, pixmap=None, parent=None):
        super().__init__(parent)
        self._color  = QtGui.QColor(color) if color else None
        self._pixmap = pixmap
        self.setFixedSize(thumb_w, thumb_h)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h, r = float(self.width()), float(self.height()), 5.0

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255))
        p.drawRoundedRect(QtCore.QRectF(0, 0, w, h), r, r)

        if self._pixmap:
            inner = QtCore.QRectF(2, 2, w - 4, h - 4)
            clip  = QtGui.QPainterPath()
            clip.addRoundedRect(inner, 4.0, 4.0)
            p.save()
            p.setClipPath(clip)
            iw, ih   = int(inner.width()), int(inner.height())
            scaled   = self._pixmap.scaled(iw, ih, QtCore.Qt.KeepAspectRatio,
                                           QtCore.Qt.SmoothTransformation)
            xo = inner.x() + (iw - scaled.width())  / 2
            yo = inner.y() + (ih - scaled.height()) / 2
            p.drawPixmap(int(xo), int(yo), scaled)
            p.restore()

        if not self._color:
            p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 28), 1.0))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRoundedRect(QtCore.QRectF(0.5, 0.5, w - 1, h - 1), r, r)
            p.end()
            return

        inset = 3.0
        ri    = max(r - inset, 1.5)

        pen_out = QtGui.QPen(self._color, 3.8)
        pen_out.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen_out)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(QtCore.QRectF(0, 0, w, h), r, r)

        echo = QtGui.QColor(self._color)
        echo.setAlphaF(0.65)
        pen_in = QtGui.QPen(echo, 2.0)
        pen_in.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen_in)
        p.drawRoundedRect(QtCore.QRectF(inset, inset, w - 2*inset, h - 2*inset), ri, ri)

        p.end()


class GroupButton(QtWidgets.QAbstractButton):
    """Маленька кнопка вибору активної групи (використовується як вибір і як оверлей)."""

    def __init__(self, num: int, color: str, bg_alpha: int = 255, parent=None):
        super().__init__(parent)
        self._num      = num
        self._color    = QtGui.QColor(color)
        self._bg_alpha = bg_alpha
        self.setCheckable(True)
        self.setFixedSize(38, 38)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(3, 3, -3, -3)

        if self.isChecked():
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(self._color)
            p.drawRoundedRect(r, 7, 7)
            p.setPen(QtGui.QColor(255, 255, 255, 230))
        else:
            bc = QtGui.QColor(self._color)
            bc.setAlpha(160)
            p.setPen(QtGui.QPen(bc, 1.6))
            p.setBrush(QtGui.QColor(30, 32, 42, self._bg_alpha))
            p.drawRoundedRect(r, 7, 7)
            p.setPen(QtGui.QColor(255, 255, 255, 230) if self._bg_alpha < 255
                     else self._color)

        f = QtGui.QFont()
        f.setPixelSize(14)
        f.setWeight(QtGui.QFont.Bold)
        p.setFont(f)
        p.drawText(r, QtCore.Qt.AlignCenter, str(self._num))
        p.end()


class DraggableCard(QtWidgets.QFrame):
    """Картка мініатюри з drag-and-drop та кліком для призначення групи."""

    def __init__(self, visual_idx: int, screen, parent=None):
        super().__init__(parent)
        self._visual_idx = visual_idx
        self._screen     = screen
        self._drag_start = None
        self._did_drag   = False
        self.setAcceptDrops(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start = event.pos()
            self._did_drag   = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_start is not None
                and event.buttons() & QtCore.Qt.LeftButton
                and (event.pos() - self._drag_start).manhattanLength() > 8):
            self._did_drag = True
            self._do_drag(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and not self._did_drag:
            self._screen.toggle_page_group(self._visual_idx)
        elif event.button() == QtCore.Qt.RightButton and not self._did_drag:
            self._screen.collapse_page_group(self._visual_idx)
        self._drag_start = None
        self._did_drag   = False
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        event.accept()

    def _do_drag(self, pos):
        pix  = self.grab()
        semi = QtGui.QPixmap(pix.size())
        semi.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(semi)
        painter.setOpacity(0.72)
        painter.drawPixmap(0, 0, pix)
        painter.end()

        self._screen.start_drag(self._visual_idx, self)

        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setText(str(self._visual_idx))
        drag.setMimeData(mime)
        drag.setPixmap(semi)
        drag.setHotSpot(self._drag_start or pos)
        self._drag_start = None
        drag.exec(QtCore.Qt.MoveAction)

        self._screen.end_drag()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self._screen.set_drop_indicator(self._visual_idx)
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            self._screen.set_drop_indicator(self._visual_idx)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._screen.set_drop_indicator(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasText():
            src = int(event.mimeData().text())
            dst = self._visual_idx
            self._screen.set_drop_indicator(None)
            if src != dst:
                self._screen.reorder_pages(src, dst)
            event.acceptProposedAction()
