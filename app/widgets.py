from PySide6 import QtWidgets, QtCore, QtGui

from .constants import BREAK_COLOR, GREEN_COLOR, group_color as _group_color
from . import icons as _icons


def _mix_colors(c1: QtGui.QColor, c2: QtGui.QColor, t: float) -> QtGui.QColor:
    t = max(0.0, min(1.0, t))
    return QtGui.QColor(
        int(c1.red()   * (1 - t) + c2.red()   * t),
        int(c1.green() * (1 - t) + c2.green() * t),
        int(c1.blue()  * (1 - t) + c2.blue()  * t),
    )


class PressableNeumorphicButton(QtWidgets.QPushButton):
    """Кнопка з об'ємним neumorphic-стилем та ефектом натискання."""

    def __init__(self, text="", base_color=BREAK_COLOR, parent=None):
        super().__init__(text, parent)
        self._base_color = QtGui.QColor(base_color)
        self._press = 0.0
        self.setCheckable(False)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setStyleSheet("QPushButton { border: none; }")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.isEnabled():
            self._press = 1.0
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = 0.0
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        rect   = self.rect().adjusted(2, 2, -2, -2)
        radius = 16
        squash = 1.0 - 0.06 * self._press
        cx, cy = rect.center().x(), rect.center().y()

        p.save()
        p.translate(cx, cy)
        p.scale(squash, squash)
        p.translate(-cx, -cy)

        enabled = self.isEnabled()
        alpha   = 255 if enabled else 110

        dark = QtGui.QColor(26, 31, 46, alpha)
        top  = _mix_colors(dark, self._base_color, 0.20)
        top.setAlpha(alpha)
        bot  = QtGui.QColor(self._base_color)
        bot.setAlpha(alpha)

        grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bot)

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(rect, radius, radius)

        rim = QtGui.QColor(self._base_color)
        rim.setAlpha(160 if enabled else 70)
        p.setPen(QtGui.QPen(rim, 1.5))
        p.drawRoundedRect(rect, radius, radius)

        hl = QtGui.QColor(255, 255, 255, 28 if enabled else 12)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(hl)
        h_half = rect.height() // 2
        p.drawRoundedRect(rect.adjusted(6, 5, -6, -h_half), radius - 6, radius - 6)

        p.restore()

        if not self.text().strip():
            return

        text_color = QtGui.QColor(255, 255, 255, 230 if enabled else 120)
        p.setPen(QtGui.QColor(0, 0, 0, 60 if enabled else 30))
        p.drawText(rect.translated(0, 1), QtCore.Qt.AlignCenter, self.text())
        p.setPen(text_color)
        p.drawText(rect, QtCore.Qt.AlignCenter, self.text())
        p.end()


class FlatButton(QtWidgets.QAbstractButton):
    """Темна кнопка з іконкою і текстом, мале закруглення."""

    def __init__(self, icon, label, accent=None, parent=None):
        super().__init__(parent)
        self._icon   = icon
        self._label  = label
        self._accent = QtGui.QColor(accent) if accent else QtGui.QColor(GREEN_COLOR)
        self._press  = False
        self._hover  = False
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setAttribute(QtCore.Qt.WA_Hover)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setMinimumHeight(44)

    def sizeHint(self):
        return QtCore.QSize(180, 44)

    def event(self, e):
        if e.type() == QtCore.QEvent.HoverEnter:
            self._hover = True
            self.update()
        elif e.type() == QtCore.QEvent.HoverLeave:
            self._hover = False
            self.update()
        return super().event(e)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.isEnabled():
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

        r       = self.rect().adjusted(2, 2, -2, -2)
        radius  = 7
        enabled = self.isEnabled()
        dim     = 1.0 if enabled else 0.40

        # ── фон ──────────────────────────────────────────────────────────────
        base = QtGui.QColor(32, 36, 50)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(base)
        p.drawRoundedRect(r, radius, radius)

        if self._press or self._hover:
            tint = QtGui.QColor(self._accent)
            tint.setAlphaF((0.22 if self._press else 0.11) * dim)
            p.setBrush(tint)
            p.drawRoundedRect(r, radius, radius)

        if self._hover:
            border = QtGui.QColor(self._accent)
            border.setAlphaF(0.28 * dim)
            p.setPen(QtGui.QPen(border, 1.0))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRoundedRect(r, radius, radius)

        # ── іконка ───────────────────────────────────────────────────────────
        active = self._hover or self._press
        ic = QtGui.QColor(self._accent if active else QtGui.QColor(175, 180, 200))
        ic.setAlphaF(dim)

        cy_f    = r.y() + r.height() / 2.0
        icon_sz = 22
        icon_rf = QtCore.QRectF(r.x() + 12, cy_f - icon_sz / 2, icon_sz, icon_sz)

        if _icons.is_icon(self._icon):
            _icons.draw(p, icon_rf, self._icon, ic)
        else:
            p.setFont(_icons.sf_font(16))
            p.setPen(ic)
            p.drawText(icon_rf.toRect(),
                       QtCore.Qt.AlignVCenter | QtCore.Qt.AlignHCenter,
                       self._icon)

        # ── текст ─────────────────────────────────────────────────────────────
        label_rect = QtCore.QRect(r.x() + 42, r.y(), r.width() - 54, r.height())
        p.setFont(_icons.sf_font(13, QtGui.QFont.Medium))
        txt = QtGui.QColor(255, 255, 255, int((230 if active else 170) * dim))
        p.setPen(txt)
        p.drawText(label_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                   self._label)
        p.end()


class CircleToggle(QtWidgets.QAbstractButton):
    """Круглий чекбокс з анімацією галочки та glow-ефектом."""

    def __init__(self, color: str, initial=False, parent=None):
        super().__init__(parent)
        self._base_color = QtGui.QColor(color)
        self.setCheckable(True)
        self.setChecked(bool(initial))
        self.setFixedSize(30, 30)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._press = 0.0

        self._tick_alpha = 1.0 if self.isChecked() else 0.0
        self._tick_anim  = QtCore.QVariantAnimation(self)
        self._tick_anim.setDuration(160)
        self._tick_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._tick_anim.valueChanged.connect(self._on_tick_anim)

        self._glow_alpha = 1.0 if self.isChecked() else 0.0
        self._glow_anim  = QtCore.QVariantAnimation(self)
        self._glow_anim.setDuration(220)
        self._glow_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._glow_anim.valueChanged.connect(self._on_glow_anim)

        self.toggled.connect(self._on_toggled)
        self.update()

    def _on_tick_anim(self, v):
        self._tick_alpha = float(v)
        self.update()

    def _on_glow_anim(self, v):
        self._glow_alpha = float(v)
        self.update()

    def _on_toggled(self, checked: bool):
        for anim, alpha in ((self._tick_anim, self._tick_alpha),
                            (self._glow_anim, self._glow_alpha)):
            anim.stop()
            anim.setStartValue(alpha)
            anim.setEndValue(1.0 if checked else 0.0)
            anim.start()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = 1.0
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = 0.0
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        rect   = self.rect().adjusted(1, 1, -1, -1)
        cx, cy = self.width() / 2, self.height() / 2
        on     = self.isChecked()
        squash = 1.0 - 0.08 * self._press

        p.save()
        p.translate(cx, cy)
        p.scale(squash, squash)
        p.translate(-cx, -cy)

        if on:
            if self._glow_alpha > 0.001:
                glow = QtGui.QColor(self._base_color)
                glow.setAlphaF(0.28 * self._glow_alpha)
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(glow)
                p.drawEllipse(rect.adjusted(-4, -4, 4, 4))

            top = _mix_colors(QtGui.QColor("#ffffff"), self._base_color, 0.55)
            bot = _mix_colors(self._base_color, QtGui.QColor("#000000"), 0.12)
            top.setAlpha(255)
            bot.setAlpha(255)

            grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bot)

            p.setPen(QtGui.QPen(self._base_color, 2))
            p.setBrush(grad)
            p.drawEllipse(rect)

            hl = QtGui.QColor("#ffffff")
            hl.setAlphaF(0.12 + 0.18 * self._glow_alpha)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(hl)
            p.drawEllipse(rect.adjusted(4, 4, -4, -10))
        else:
            top_c = QtGui.QColor(52, 60, 85, 255)
            bot_c = QtGui.QColor(32, 38, 56, 255)
            grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, top_c)
            grad.setColorAt(1.0, bot_c)
            p.setPen(QtGui.QPen(QtGui.QColor(68, 78, 108), 1.5))
            p.setBrush(grad)
            p.drawEllipse(rect)
            hl = QtGui.QColor(255, 255, 255, 22)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(hl)
            p.drawEllipse(rect.adjusted(3, 3, -5, -10))

        p.restore()

        if on and self._tick_alpha > 0.001:
            a = self._tick_alpha
            tick_shadow = QtGui.QColor("#000000")
            tick_shadow.setAlphaF(a)
            tick_main = QtGui.QColor("#FFFFF0")
            tick_main.setAlphaF(a)
            for color, width in ((tick_shadow, 5.0), (tick_main, 4.0)):
                p.setPen(QtGui.QPen(color, width, QtCore.Qt.SolidLine,
                                    QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                p.drawLine(QtCore.QPointF(9, 17),  QtCore.QPointF(14, 22))
                p.drawLine(QtCore.QPointF(14, 22), QtCore.QPointF(22, 10))
        p.end()


class ModernToggle(QtWidgets.QAbstractButton):
    """Мінімалістичний квадратний чекбокс у стилі Figma/Linear."""

    SIZE = 28

    def __init__(self, color: str, initial=False, parent=None):
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self.setCheckable(True)
        self.setChecked(bool(initial))
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self._fill  = 1.0 if self.isChecked() else 0.0
        self._press = 0.0

        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(130)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._on_toggled)

    def _on_anim(self, v):
        self._fill = float(v)
        self.update()

    def _on_toggled(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._fill)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = 1.0
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = 0.0
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        r      = self.rect().adjusted(2, 2, -2, -2)
        radius = 4
        a      = self._fill
        squash = 1.0 - 0.07 * self._press
        cx, cy = self.width() / 2.0, self.height() / 2.0

        p.save()
        p.translate(cx, cy)
        p.scale(squash, squash)
        p.translate(-cx, -cy)

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 210))
        p.drawRoundedRect(r, radius, radius)

        bg = QtGui.QColor(self._color)
        bg.setAlphaF(a)
        p.setBrush(bg)
        p.drawRoundedRect(r, radius, radius)

        bc = QtGui.QColor(self._color)
        bc.setAlpha(int(110 + 145 * a))
        p.setPen(QtGui.QPen(bc, 1.5))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(r, radius, radius)

        p.restore()

        if a > 0.02:
            tc = QtGui.QColor(255, 255, 255)
            tc.setAlphaF(a)
            pen = QtGui.QPen(tc, 2.2, QtCore.Qt.SolidLine,
                             QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(QtCore.QPointF(cx - 4.8, cy + 0.4),
                       QtCore.QPointF(cx - 1.3, cy + 3.8))
            p.drawLine(QtCore.QPointF(cx - 1.3, cy + 3.8),
                       QtCore.QPointF(cx + 5.3, cy - 4.4))
        p.end()


class ThumbnailActionButton(QtWidgets.QAbstractButton):
    """Small circular overlay button on a thumbnail card (e.g. rotate icon)."""

    def __init__(self, icon_name: str, color: str = "#8E8E93", size: int = 24,
                 bg_alpha: float = 0.62, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._color     = QtGui.QColor(color)
        self._bg_alpha  = bg_alpha
        self._hover     = False
        self._press     = False
        self.setFixedSize(size, size)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setAttribute(QtCore.Qt.WA_Hover)

    def event(self, e):
        if e.type() == QtCore.QEvent.HoverEnter:
            self._hover = True
            self.update()
        elif e.type() == QtCore.QEvent.HoverLeave:
            self._hover = False
            self.update()
        return super().event(e)

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

    def set_color(self, color):
        self._color = QtGui.QColor(color) if color else None
        self.update()

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


class DropGapCell(QtWidgets.QWidget):
    """Повноцінна клітинка-заповнювач в гриді під час drag.
    Займає місце джерела і показує куди впаде картка — сусіди природно розсуваються."""

    def __init__(self, w, h, parent=None, screen=None, drop_idx=None):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self._pulse = 0.5
        self._color = QtGui.QColor("#53A8FF")
        self._thumb_h = h - 60
        self._screen   = screen
        self._drop_idx = drop_idx

        if screen is not None:
            self.setAcceptDrops(True)

        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(900)
        self._anim.setStartValue(0.3)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_anim)
        self._anim.start()

    def _on_anim(self, v):
        self._pulse = float(v)
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w  = float(self.width())
        th = float(self._thumb_h)
        a  = self._pulse
        c  = self._color
        pad = 4.0

        # Фон
        bg = QtGui.QColor(c)
        bg.setAlphaF(0.04 + 0.04 * a)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QtCore.QRectF(pad, pad, w - 2*pad, th - 2*pad), 8, 8)

        # Пунктирна рамка
        bc = QtGui.QColor(c)
        bc.setAlphaF(0.22 + 0.28 * a)
        pen = QtGui.QPen(bc, 1.5, QtCore.Qt.DashLine)
        pen.setDashPattern([5.0, 4.0])
        p.setPen(pen)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(QtCore.QRectF(pad, pad, w - 2*pad, th - 2*pad), 8, 8)

        # Стрілка ↓ по центру
        cx = w / 2.0
        cy = th / 2.0
        sz = 22.0
        ac = QtGui.QColor(c)
        ac.setAlphaF(0.35 + 0.50 * a)
        p.setPen(QtGui.QPen(ac, 2.2, QtCore.Qt.SolidLine,
                            QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        p.drawLine(QtCore.QPointF(cx, cy - sz * 0.5),
                   QtCore.QPointF(cx, cy + sz * 0.5))
        p.drawLine(QtCore.QPointF(cx, cy + sz * 0.5),
                   QtCore.QPointF(cx - sz * 0.38, cy + sz * 0.08))
        p.drawLine(QtCore.QPointF(cx, cy + sz * 0.5),
                   QtCore.QPointF(cx + sz * 0.38, cy + sz * 0.08))
        p.end()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and self._screen is not None:
            self._screen.set_drop_indicator(self._drop_idx)
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and self._screen is not None:
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        if self._screen is not None:
            self._screen.set_drop_indicator(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasText() and self._screen is not None:
            src = int(event.mimeData().text())
            self._screen.set_drop_indicator(None)
            if self._drop_idx is not None:
                self._screen.reorder_pages(src, self._drop_idx)
            event.acceptProposedAction()


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
        # Grab at full opacity before start_drag applies the ghost effect
        pix  = self.grab()
        semi = QtGui.QPixmap(pix.size())
        semi.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(semi)
        painter.setOpacity(0.72)
        painter.drawPixmap(0, 0, pix)
        painter.end()

        self._screen.start_drag(self._visual_idx, self)  # ghosts card in place

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
