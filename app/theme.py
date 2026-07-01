import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass

_log = logging.getLogger(__name__)

_THEME_FILE = os.path.join(os.path.dirname(__file__), "theme.json")


@dataclass
class Theme:
    # ── Фони ──────────────────────────────────────────────────────────────────
    bg_main:     str = "#21232a"    # робоча область
    bg_sidebar:  str = "#191b21"    # бічні панелі, рядок стану
    bg_border:   str = "#2a3045"    # межі між панелями
    bg_hover:    str = "#252830"    # роздільники всередині панелей
    viewer_bg:   str = "#2c2f3d"    # фон під сторінками PDF

    # ── Акцент ────────────────────────────────────────────────────────────────
    accent:      str = "#6EDE8A"    # DropZone, drag-and-drop

    # ── Стан пунктів навігації (підсвітки — колір + alpha 0-255) ─────────────
    nav_active_bg:            str = "#ffffff"
    nav_active_bg_alpha:      int = 18
    nav_hover_bg:             str = "#ffffff"
    nav_hover_bg_alpha:       int = 10

    # ── Кольори іконок у бічних панелях ──────────────────────────────────────
    nav_icon_active_color:    str = "#ffffff"
    nav_icon_active_alpha:    int = 220
    nav_icon_inactive_color:  str = "#ffffff"
    nav_icon_inactive_alpha:  int = 150

    # ── Кольори підписів у бічних панелях ────────────────────────────────────
    nav_label_active_color:   str = "#ffffff"
    nav_label_active_alpha:   int = 220
    nav_label_inactive_color: str = "#ffffff"
    nav_label_inactive_alpha: int = 170

    # ── Іконки ────────────────────────────────────────────────────────────────
    icon_size:   int   = 20
    icon_stroke: float = 0.09

    # ── Кольори груп (8 кольорів) ─────────────────────────────────────────────
    group_color_0: str = "#6EDE8A"
    group_color_1: str = "#53A8FF"
    group_color_2: str = "#FFBB53"
    group_color_3: str = "#D28BF5"
    group_color_4: str = "#92DFFF"
    group_color_5: str = "#FF7C75"
    group_color_6: str = "#FFE253"
    group_color_7: str = "#8E8CED"

    # ── Рядок стану переглядача (alpha 0-255) ────────────────────────────────
    statusbar_file_alpha:   int = 166   # назва файлу
    statusbar_page_alpha:   int = 115   # "3/9"
    statusbar_cursor_alpha: int = 90    # "x 123  y 456"

    # ── Переглядач PDF ────────────────────────────────────────────────────────
    scrollbar_alpha:  int = 46          # alpha смуги прокрутки
    selection_color:  str = "#50a0ff"   # колір виділення тексту


class ThemeManager:
    def __init__(self):
        self._theme: Theme = Theme()
        self._listeners: list[Callable] = []
        self._load()

    def get(self) -> Theme:
        return self._theme

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self._theme, k):
                setattr(self._theme, k, v)
        self._notify()

    def save(self):
        try:
            with open(_THEME_FILE, "w") as f:
                json.dump(asdict(self._theme), f, indent=2)
        except OSError:
            _log.warning("Не вдалося зберегти тему у %s", _THEME_FILE, exc_info=True)

    def reset(self):
        self._theme = Theme()
        self._notify()

    def add_listener(self, cb: Callable):
        self._listeners.append(cb)

    def _load(self):
        try:
            with open(_THEME_FILE) as f:
                data = json.load(f)
            t = Theme()
            for k, v in data.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            self._theme = t
        except (OSError, json.JSONDecodeError):
            _log.debug("Не вдалося завантажити тему з %s, використано типову", _THEME_FILE,
                       exc_info=True)

    def _notify(self):
        for cb in self._listeners[:]:
            try:
                cb()
            except Exception:
                _log.warning("Слухач зміни теми викинув виняток", exc_info=True)


THEME_MGR = ThemeManager()
