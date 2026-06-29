from PySide6 import QtWidgets, QtCore, QtGui
from .theme import THEME_MGR


class _Sep(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(9)

    def paintEvent(self, _):
        t = THEME_MGR.get()
        p = QtGui.QPainter(self)
        p.setPen(QtGui.QColor(t.bg_border))
        mid = self.height() // 2
        p.drawLine(8, mid, self.width() - 8, mid)
        p.end()


class _Row(QtWidgets.QWidget):
    clicked = QtCore.Signal()
    HEIGHT  = 34

    def __init__(self, label: str, shortcut: str = "", arrow: bool = False,
                 back: bool = False, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self._enabled = enabled
        self._hover   = False
        if enabled:
            self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WA_Hover)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 10, 0)
        lay.setSpacing(0)

        if back:
            color = "rgba(255,255,255,0.50)"
        elif enabled:
            color = "rgba(255,255,255,0.85)"
        else:
            color = "rgba(255,255,255,0.28)"

        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")
        lay.addWidget(lbl)
        lay.addStretch()

        if shortcut:
            sc = QtWidgets.QLabel(shortcut)
            sc.setStyleSheet(
                "color: rgba(255,255,255,0.28); font-size: 12px; background: transparent;"
            )
            lay.addWidget(sc)
            lay.addSpacing(8)

        if arrow:
            arr = QtWidgets.QLabel("›")
            arr.setStyleSheet(
                "color: rgba(255,255,255,0.40); font-size: 18px; background: transparent;"
            )
            lay.addWidget(arr)

    def event(self, e):
        if e.type() == QtCore.QEvent.HoverEnter and self._enabled:
            self._hover = True;  self.update()
        elif e.type() == QtCore.QEvent.HoverLeave:
            self._hover = False; self.update()
        return super().event(e)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton and self._enabled:
            self.clicked.emit()

    def paintEvent(self, _):
        if not self._hover:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 22))
        p.drawRoundedRect(self.rect().adjusted(2, 1, -2, -1), 4, 4)
        p.end()


class ContextDrillMenu(QtWidgets.QFrame):
    """Popup menu that navigates like DrillDownPanel — click to enter, ← to go back.

    Item format:
        ('action', label, callback [, shortcut=''] [, enabled=True])
        ('sep',)
    Folder format passed to add_folder():
        list of the above item tuples
    """

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedWidth(232)

        self._vlay = QtWidgets.QVBoxLayout(self)
        self._vlay.setContentsMargins(5, 5, 5, 5)
        self._vlay.setSpacing(0)

        self._top:     list        = []
        self._current: list        = []
        self._stack:   list[tuple] = []   # (folder_label, parent_items)

    # ── public API ────────────────────────────────────────────────────────────

    def add_folder(self, label: str, items: list):
        self._top.append(('folder', label, items))

    def popup(self, global_pos: QtCore.QPoint):
        self._stack.clear()
        self._current = list(self._top)
        self._render(self._current)
        self.adjustSize()

        screen = QtWidgets.QApplication.screenAt(global_pos)
        geo = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 9999, 9999)
        x = min(global_pos.x(), geo.right()  - self.width()  - 4)
        y = min(global_pos.y(), geo.bottom() - self.height() - 4)
        self.move(x, y)
        self.show()

    # ── navigation ────────────────────────────────────────────────────────────

    def _enter(self, label: str, sub: list):
        self._stack.append((label, self._current))
        self._current = sub
        self._render(sub)

    def _go_back(self):
        if self._stack:
            _, items = self._stack.pop()
            self._current = items
            self._render(items)

    def _trigger(self, fn):
        self.close()
        fn()

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self, items: list):
        while self._vlay.count():
            w = self._vlay.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        t = THEME_MGR.get()
        self.setStyleSheet(
            f"ContextDrillMenu {{ background: {t.bg_sidebar};"
            f" border: 1px solid {t.bg_border}; border-radius: 8px; }}"
        )

        if self._stack:
            back_label, _ = self._stack[-1]
            back = _Row(f"← {back_label}", back=True)
            back.clicked.connect(self._go_back)
            self._vlay.addWidget(back)
            self._vlay.addWidget(_Sep())

        for item in items:
            if item[0] == 'sep':
                self._vlay.addWidget(_Sep())

            elif item[0] == 'folder':
                _, label, sub = item
                row = _Row(label, arrow=True)
                row.clicked.connect(
                    lambda _=False, lbl=label, s=sub: self._enter(lbl, s)
                )
                self._vlay.addWidget(row)

            elif item[0] == 'action':
                label    = item[1]
                callback = item[2]
                shortcut = item[3] if len(item) > 3 else ''
                enabled  = item[4] if len(item) > 4 else True
                row = _Row(label, shortcut=shortcut, enabled=enabled)
                if enabled:
                    row.clicked.connect(
                        lambda _=False, fn=callback: self._trigger(fn)
                    )
                self._vlay.addWidget(row)

        self.adjustSize()

    # ── keyboard ──────────────────────────────────────────────────────────────

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            if self._stack:
                self._go_back()
            else:
                self.close()
        else:
            super().keyPressEvent(e)
