"""Unified icon rendering: Lucide SVG first, hand-drawn vector fallback.

Public API
----------
draw(painter, rect, name, color)  -- auto-selects SVG or vector renderer
has_svg(name)                     -- True if a Lucide SVG file is registered
is_icon(name)                     -- True if any renderer handles this name
sf_font(pixel_size, weight=None)  -- system-ui / Segoe UI font helper
"""

import math
import os
import re

from PySide6 import QtCore, QtGui
from PySide6.QtSvg import QSvgRenderer

from ...theme import THEME_MGR

# ── SVG assets ────────────────────────────────────────────────────────────────

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "svg")

_SVG_MAP: dict[str, str] = {
    "sidebar":          "panel-left",
    "info":             "info",
    "zoom_out":         "zoom-out",
    "zoom_in":          "zoom-in",
    "share":            "share",
    "markup":           "pen-line",
    "rotate":           "rotate-cw",
    "a_circle":         "type",
    "search":           "search",
    "arrow_up":         "arrow-up",
    "eye":              "eye",
    "merge":            "combine",
    "printer":          "printer",
    "arrow_left":       "arrow-left",
    "?":                "circle-question-mark",
    "xmark":            "x",
    "compress_layers":  "layers",
    "gear":             "settings-2",
    "checkmark":        "check",
    "plus_circle":      "circle-plus",
    "play":             "play",
    "save":             "save",
    "scissors":         "scissors",
    "chevron_left":     "chevron-left",
    "chevron_right":    "chevron-right",
    "tab_plus":         "plus",
}

_svg_cache: dict[str, str] = {}


def _load_svg(filename: str) -> str:
    if filename not in _svg_cache:
        with open(os.path.join(_ASSETS_DIR, f"{filename}.svg"), encoding="utf-8") as f:
            _svg_cache[filename] = f.read()
    return _svg_cache[filename]


def has_svg(name: str) -> bool:
    return name in _SVG_MAP


def _draw_svg(painter: QtGui.QPainter, rect: QtCore.QRectF,
              name: str, color: QtGui.QColor) -> None:
    text = _load_svg(_SVG_MAP[name])
    hex_col = f"#{color.red():02x}{color.green():02x}{color.blue():02x}"
    text = re.sub(r'stroke="(?:black|currentColor)"', f'stroke="{hex_col}"', text)
    text = re.sub(r'fill="black"', f'fill="{hex_col}"', text)
    alpha = color.alphaF()
    if alpha < 0.999:
        text = text.replace("<svg", f'<svg opacity="{alpha:.4f}"', 1)
    QSvgRenderer(QtCore.QByteArray(text.encode("utf-8"))).render(painter, rect)


# ── Hand-drawn vector icons (fallback) ───────────────────────────────────────

_VECTOR_NAMES = frozenset([
    "scissors", "merge", "rotate", "compress_layers", "gear",
    "plus_circle", "play", "arrow_left", "arrow_up", "checkmark", "xmark", "eye",
    "save", "printer", "sidebar", "search", "info", "share", "markup", "a_circle",
    "zoom_in", "zoom_out",
])

_SF_FAMILY: str | None = None


def sf_family() -> str:
    global _SF_FAMILY
    if _SF_FAMILY is None:
        fams = QtGui.QFontDatabase.families()
        for name in ("SF Pro Display", "SF Pro Text", ".SF NS Display",
                     "Segoe UI Variable Display", "Segoe UI Variable Text",
                     "Segoe UI Variable", "Segoe UI"):
            if name in fams:
                _SF_FAMILY = name
                break
        else:
            _SF_FAMILY = ""
    return _SF_FAMILY


def sf_font(pixel_size: int, weight=None) -> QtGui.QFont:
    fam = sf_family()
    f = QtGui.QFont(fam) if fam else QtGui.QFont()
    f.setPixelSize(pixel_size)
    if weight is not None:
        f.setWeight(weight)
    return f


def is_icon(name: str) -> bool:
    return name in _SVG_MAP or name in _VECTOR_NAMES


def _draw_vector(p: QtGui.QPainter, rect: QtCore.QRectF,
                 name: str, color: QtGui.QColor) -> None:
    p.save()
    p.setRenderHint(QtGui.QPainter.Antialiasing)

    cx = rect.center().x()
    cy = rect.center().y()
    s  = min(rect.width(), rect.height())
    lw = max(1.5, s * THEME_MGR.get().icon_stroke)

    pen = QtGui.QPen(color, lw, QtCore.Qt.SolidLine,
                     QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(QtCore.Qt.NoBrush)

    if name == "scissors":
        r_h = s * 0.092
        h1  = QtCore.QPointF(cx - s*0.22, cy - s*0.14)
        h2  = QtCore.QPointF(cx - s*0.22, cy + s*0.14)
        t1  = QtCore.QPointF(cx + s*0.30, cy - s*0.22)
        t2  = QtCore.QPointF(cx + s*0.30, cy + s*0.22)
        p.drawLine(QtCore.QPointF(h1.x() + r_h * 0.85, h1.y()), t2)
        p.drawLine(QtCore.QPointF(h2.x() + r_h * 0.85, h2.y()), t1)
        p.drawEllipse(h1, r_h, r_h)
        p.drawEllipse(h2, r_h, r_h)

    elif name == "merge":
        lx = cx - s*0.30
        mp = QtCore.QPointF(cx - s*0.03, cy)
        rx = cx + s*0.33
        p.drawLine(QtCore.QPointF(lx, cy - s*0.20), mp)
        p.drawLine(QtCore.QPointF(lx, cy + s*0.20), mp)
        p.drawLine(mp, QtCore.QPointF(rx, cy))
        ah = s * 0.115
        p.drawLine(QtCore.QPointF(rx, cy), QtCore.QPointF(rx - ah, cy - ah * 0.60))
        p.drawLine(QtCore.QPointF(rx, cy), QtCore.QPointF(rx - ah, cy + ah * 0.60))

    elif name == "rotate":
        pw_ = s * 0.22; ph_ = s * 0.27
        rx_ = cx - pw_ - s * 0.07; ry_ = cy - ph_
        p.drawRoundedRect(QtCore.QRectF(rx_, ry_, pw_ * 2, ph_ * 2), 3, 3)
        arc_cx = rx_ + pw_ * 2 + s * 0.035; arc_cy = ry_ - s * 0.02
        ar = s * 0.215
        arc_rect = QtCore.QRectF(arc_cx - ar, arc_cy - ar, ar * 2, ar * 2)
        arc_path = QtGui.QPainterPath()
        arc_path.arcMoveTo(arc_rect, 180); arc_path.arcTo(arc_rect, 180, -260)
        p.drawPath(arc_path)
        ex = arc_cx + ar * math.cos(math.radians(-80))
        ey = arc_cy - ar * math.sin(math.radians(-80))
        ah = s * 0.10
        p.drawLine(QtCore.QPointF(ex, ey), QtCore.QPointF(ex - ah * 0.9, ey - ah * 0.5))
        p.drawLine(QtCore.QPointF(ex, ey), QtCore.QPointF(ex + ah * 0.3, ey - ah))

    elif name == "compress_layers":
        hw  = s * 0.25; gap = s * 0.135
        for dy in (-gap, 0.0, gap):
            p.drawLine(QtCore.QPointF(cx - hw, cy + dy), QtCore.QPointF(cx + hw, cy + dy))
        ax = cx + hw + lw * 2.2; ay0 = cy - gap; ay1 = cy + gap
        p.drawLine(QtCore.QPointF(ax, ay0), QtCore.QPointF(ax, ay1))
        ah = lw * 1.2
        p.drawLine(QtCore.QPointF(ax, ay1), QtCore.QPointF(ax - ah, ay1 - ah))
        p.drawLine(QtCore.QPointF(ax, ay1), QtCore.QPointF(ax + ah, ay1 - ah))

    elif name == "gear":
        r_out = s * 0.285; r_base = r_out * 0.80; r_ring = r_out * 0.60
        r_hub = r_out * 0.31; r_ctr = r_out * 0.16
        teeth = 12; htw = math.pi / teeth * 0.43
        arc_r = QtCore.QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2)
        gear  = QtGui.QPainterPath()
        for i in range(teeth):
            base = 2 * math.pi * i / teeth
            va   = base - math.pi / teeth
            vx, vy = cx + r_base * math.cos(va), cy + r_base * math.sin(va)
            t0, t1 = base - htw, base + htw
            if i == 0: gear.moveTo(vx, vy)
            else:       gear.lineTo(vx, vy)
            gear.lineTo(cx + r_out * math.cos(t0), cy + r_out * math.sin(t0))
            gear.arcTo(arc_r, -math.degrees(t0), -math.degrees(t1 - t0))
        gear.closeSubpath()
        ring_r = QtCore.QRectF(cx - r_ring, cy - r_ring, r_ring * 2, r_ring * 2)
        hub_r  = QtCore.QRectF(cx - r_hub,  cy - r_hub,  r_hub  * 2, r_hub  * 2)
        hw_    = math.radians(38.0); holes = QtGui.QPainterPath()
        for i in range(3):
            a_mid = math.pi / 3 + 2 * math.pi * i / 3
            a0, a1 = a_mid - hw_, a_mid + hw_
            sec = QtGui.QPainterPath()
            sec.moveTo(cx + r_ring * math.cos(a0), cy + r_ring * math.sin(a0))
            sec.arcTo(ring_r, -math.degrees(a0), -math.degrees(a1 - a0))
            sec.lineTo(cx + r_hub * math.cos(a1), cy + r_hub * math.sin(a1))
            sec.arcTo(hub_r, -math.degrees(a1), math.degrees(a1 - a0))
            sec.closeSubpath(); holes = holes.united(sec)
        ctr_hole = QtGui.QPainterPath()
        ctr_hole.addEllipse(QtCore.QPointF(cx, cy), r_ctr, r_ctr)
        holes = holes.united(ctr_hole)
        p.setBrush(color); p.setPen(QtCore.Qt.NoPen)
        p.drawPath(gear.subtracted(holes))

    elif name == "plus_circle":
        r = s * 0.30; hl = r * 0.54
        p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        p.drawLine(QtCore.QPointF(cx - hl, cy), QtCore.QPointF(cx + hl, cy))
        p.drawLine(QtCore.QPointF(cx, cy - hl), QtCore.QPointF(cx, cy + hl))

    elif name == "play":
        r = s * 0.28
        path = QtGui.QPainterPath()
        path.moveTo(cx + r * 0.88, cy)
        path.lineTo(cx - r * 0.45, cy - r * 0.82)
        path.lineTo(cx - r * 0.45, cy + r * 0.82)
        path.closeSubpath()
        p.setBrush(color); p.setPen(QtCore.Qt.NoPen); p.drawPath(path)

    elif name == "arrow_left":
        l = s * 0.28; ah = s * 0.145
        p.drawLine(QtCore.QPointF(cx - l, cy), QtCore.QPointF(cx + l * 0.85, cy))
        p.drawLine(QtCore.QPointF(cx - l, cy), QtCore.QPointF(cx - l + ah, cy - ah))
        p.drawLine(QtCore.QPointF(cx - l, cy), QtCore.QPointF(cx - l + ah, cy + ah))

    elif name == "arrow_up":
        l = s * 0.28; ah = s * 0.145
        p.drawLine(QtCore.QPointF(cx, cy + l), QtCore.QPointF(cx, cy - l * 0.85))
        p.drawLine(QtCore.QPointF(cx, cy - l), QtCore.QPointF(cx - ah, cy - l + ah))
        p.drawLine(QtCore.QPointF(cx, cy - l), QtCore.QPointF(cx + ah, cy - l + ah))

    elif name == "checkmark":
        p.setPen(QtGui.QPen(color, max(1.5, s * 0.095),
                            QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        p.drawLine(QtCore.QPointF(cx - s*0.27, cy + s*0.04), QtCore.QPointF(cx - s*0.05, cy + s*0.26))
        p.drawLine(QtCore.QPointF(cx - s*0.05, cy + s*0.26), QtCore.QPointF(cx + s*0.30, cy - s*0.20))

    elif name == "xmark":
        d = s * 0.23
        p.drawLine(QtCore.QPointF(cx - d, cy - d), QtCore.QPointF(cx + d, cy + d))
        p.drawLine(QtCore.QPointF(cx + d, cy - d), QtCore.QPointF(cx - d, cy + d))

    elif name == "eye":
        ew = s * 0.295; ech = s * 0.19
        path = QtGui.QPainterPath()
        path.moveTo(cx - ew, cy)
        path.cubicTo(cx - ew*0.35, cy - ech, cx + ew*0.35, cy - ech, cx + ew, cy)
        path.cubicTo(cx + ew*0.35, cy + ech, cx - ew*0.35, cy + ech, cx - ew, cy)
        path.closeSubpath(); p.drawPath(path)
        p.setBrush(color); p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(cx, cy), s * 0.092, s * 0.092)

    elif name == "sidebar":
        w = s * 0.62; h = s * 0.50
        rx = cx - w / 2; ry = cy - h / 2
        p.drawRoundedRect(QtCore.QRectF(rx, ry, w, h), 3, 3)
        p.drawLine(QtCore.QPointF(rx + w * 0.34, ry), QtCore.QPointF(rx + w * 0.34, ry + h))

    p.restore()


# ── Unified entry point ───────────────────────────────────────────────────────

def draw(painter: QtGui.QPainter, rect: QtCore.QRectF,
         name: str, color: QtGui.QColor) -> None:
    """Render *name* into *rect* with *color*. SVG renderer is preferred;
    hand-drawn vector is used when no SVG file is registered for *name*."""
    if has_svg(name):
        _draw_svg(painter, rect, name, color)
    elif name in _VECTOR_NAMES:
        _draw_vector(painter, rect, name, color)
