from .theme import THEME_MGR

GREEN_COLOR  = "#6EDE8A"
RED_COLOR    = "#FF7C75"
BREAK_COLOR  = "#92DFFF"
BORDER_COLOR = "#8E8E93"

MAX_GROUPS  = 100
THUMB_SCALE = 0.42


def group_color(num: int) -> str:
    """Return the display color for group number `num` (1-based, cycles)."""
    t = THEME_MGR.get()
    colors = (
        t.group_color_0, t.group_color_1, t.group_color_2, t.group_color_3,
        t.group_color_4, t.group_color_5, t.group_color_6, t.group_color_7,
    )
    return colors[(num - 1) % len(colors)]
