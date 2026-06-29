import os
from PySide6 import QtWidgets, QtCore

from ..constants import BREAK_COLOR, GREEN_COLOR
from ..widgets import PressableNeumorphicButton


class ScreenPick(QtWidgets.QWidget):
    """Перший екран: вибір PDF-файлів для обробки."""

    def __init__(self, app_state: dict, go_next):
        super().__init__()
        self.app_state = app_state
        self.go_next   = go_next

        self.setWindowTitle("PDF Splitter")
        self.resize(720, 420)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 0, 10, 10)
        root.setSpacing(0)

        # ── відступ зверху (динамічний) ───────────────────────────────────────
        self._spacer_top = QtWidgets.QSpacerItem(
            0, 19, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed
        )
        root.addSpacerItem(self._spacer_top)

        # ── рядок кнопок меню ─────────────────────────────────────────────────
        top_row        = QtWidgets.QWidget()
        top_row_layout = QtWidgets.QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(10)

        self.btn_main = PressableNeumorphicButton("Розділити ПЕ-ДЕ-ЕФ", base_color=BREAK_COLOR)
        self.btn_main.setMinimumHeight(60)
        self.btn_main.clicked.connect(self.pick_files)
        top_row_layout.addWidget(self.btn_main, 1)

        self._btn_ph = []
        for _ in range(4):
            ph = PressableNeumorphicButton("", base_color=BREAK_COLOR)
            ph.setEnabled(False)
            ph.setMinimumHeight(60)
            top_row_layout.addWidget(ph, 1)
            self._btn_ph.append(ph)

        root.addWidget(top_row, stretch=0)

        # ── відступ між кнопками і списком (динамічний) ───────────────────────
        self._spacer_mid = QtWidgets.QSpacerItem(
            0, 19, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed
        )
        root.addSpacerItem(self._spacer_mid)

        # ── список файлів ─────────────────────────────────────────────────────
        bottom_panel   = QtWidgets.QWidget()
        bottom_layout  = QtWidgets.QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)

        left_side   = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_side)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.list_widget = QtWidgets.QListWidget()
        left_layout.addWidget(self.list_widget, 1)

        self.status = QtWidgets.QLabel("")
        left_layout.addWidget(self.status, 0)

        bottom_layout.addWidget(left_side, 1)

        empty_right = QtWidgets.QWidget()
        empty_right.setStyleSheet("background: transparent;")
        bottom_layout.addWidget(empty_right, 1)

        root.addWidget(bottom_panel, stretch=1)

        # ── кнопка "Пігнали" на всю ширину ───────────────────────────────────
        btn_signal = PressableNeumorphicButton("Пігнали", base_color=GREEN_COLOR)
        btn_signal.setMinimumHeight(60)
        btn_signal.clicked.connect(self.on_signal)
        root.addWidget(btn_signal, stretch=0)

    # ── events ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        gap = max(10, int(self.height() * 0.025))
        self._spacer_top.changeSize(0, gap,
                                    QtWidgets.QSizePolicy.Minimum,
                                    QtWidgets.QSizePolicy.Fixed)
        self._spacer_mid.changeSize(0, gap,
                                    QtWidgets.QSizePolicy.Minimum,
                                    QtWidgets.QSizePolicy.Fixed)
        self.layout().invalidate()

    # ── slots ─────────────────────────────────────────────────────────────────

    def pick_files(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Виберіть PDF-файл", "", "PDF files (*.pdf)"
        )
        self.list_widget.clear()

        if not file:
            self.app_state["files_fullpaths"] = []
            self.status.setText("Файл не вибрано.")
            return

        self.app_state["files_fullpaths"] = [file]
        self.list_widget.addItem(os.path.basename(file))
        self.status.setText("Файл вибрано.")

    def on_signal(self):
        if not self.app_state.get("files_fullpaths"):
            QtWidgets.QMessageBox.information(self, "Пігнали", "Спочатку обери PDF-файли.")
            return
        self.go_next()
