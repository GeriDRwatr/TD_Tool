import math
from PySide6 import QtCore, QtGui
from .theme import THEME_MGR

_ICON_NAMES = frozenset([
    "scissors", "merge", "rotate", "compress_layers", "gear",
    "plus_circle", "play", "arrow_left", "arrow_up", "checkmark", "xmark", "eye", "save",
    "printer", "sidebar", "search",
    "info", "share", "markup", "a_circle",
])

_SF_FAMILY = None


def sf_family():
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
    return name in _ICON_NAMES


def draw(p: QtGui.QPainter, rect: QtCore.QRectF,
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
        # SF "scissors": two crossing blades with finger-loop handles
        r_h = s * 0.092
        h1  = QtCore.QPointF(cx - s*0.22, cy - s*0.14)
        h2  = QtCore.QPointF(cx - s*0.22, cy + s*0.14)
        t1  = QtCore.QPointF(cx + s*0.30,  cy - s*0.22)
        t2  = QtCore.QPointF(cx + s*0.30,  cy + s*0.22)
        # Blades cross: top handle → bottom tip, bottom handle → top tip
        p.drawLine(QtCore.QPointF(h1.x() + r_h * 0.85, h1.y()), t2)
        p.drawLine(QtCore.QPointF(h2.x() + r_h * 0.85, h2.y()), t1)
        p.drawEllipse(h1, r_h, r_h)
        p.drawEllipse(h2, r_h, r_h)

    elif name == "merge":
        # SF "arrow.triangle.merge": two lines fusing into one arrow
        lx = cx - s*0.30
        mp = QtCore.QPointF(cx - s*0.03, cy)
        rx = cx + s*0.33
        p.drawLine(QtCore.QPointF(lx, cy - s*0.20), mp)
        p.drawLine(QtCore.QPointF(lx, cy + s*0.20), mp)
        p.drawLine(mp, QtCore.QPointF(rx, cy))
        ah = s * 0.115
        p.drawLine(QtCore.QPointF(rx, cy),
                   QtCore.QPointF(rx - ah, cy - ah * 0.60))
        p.drawLine(QtCore.QPointF(rx, cy),
                   QtCore.QPointF(rx - ah, cy + ah * 0.60))

    elif name == "rotate":
        # SF "arrow.clockwise": arc with arrowhead
        r_a = s * 0.265
        arc_rect = QtCore.QRectF(cx - r_a, cy - r_a, r_a * 2, r_a * 2)
        path = QtGui.QPainterPath()
        path.arcMoveTo(arc_rect, 90)
        path.arcTo(arc_rect, 90, -300)
        p.drawPath(path)
        # Arrowhead at arc end (Qt -210° ≡ 150° → screen upper-left)
        ea = math.radians(150)
        ex = cx + r_a * math.cos(ea)
        ey = cy - r_a * math.sin(ea)
        tx =  math.cos(math.radians(60))
        ty = -math.sin(math.radians(60))
        ah = s * 0.115
        p.drawLine(QtCore.QPointF(ex, ey),
                   QtCore.QPointF(ex - tx*ah + ty*ah*0.55, ey - ty*ah - tx*ah*0.55))
        p.drawLine(QtCore.QPointF(ex, ey),
                   QtCore.QPointF(ex - tx*ah - ty*ah*0.55, ey - ty*ah + tx*ah*0.55))

    elif name == "compress_layers":
        # SF "line.3.horizontal.decrease": three bars + side compression arrow
        hw  = s * 0.25
        gap = s * 0.135
        for dy in (-gap, 0.0, gap):
            p.drawLine(QtCore.QPointF(cx - hw, cy + dy),
                       QtCore.QPointF(cx + hw, cy + dy))
        ax  = cx + hw + lw * 2.2
        ay0 = cy - gap
        ay1 = cy + gap
        p.drawLine(QtCore.QPointF(ax, ay0), QtCore.QPointF(ax, ay1))
        ah = lw * 1.2
        p.drawLine(QtCore.QPointF(ax, ay1), QtCore.QPointF(ax - ah, ay1 - ah))
        p.drawLine(QtCore.QPointF(ax, ay1), QtCore.QPointF(ax + ah, ay1 - ah))

    elif name == "gear":
        # macOS System Preferences style: filled gear + 3 radial arm spokes
        r_out  = s * 0.285            # tooth tip radius
        r_base = r_out * 0.80         # tooth root (outer-ring body edge)
        r_ring = r_out * 0.60         # inner arm / outer-ring boundary
        r_hub  = r_out * 0.31         # arm / hub boundary
        r_ctr  = r_out * 0.16         # centre hole
        teeth  = 12
        htw    = math.pi / teeth * 0.43   # half tooth arc width

        # outer gear path (filled solid)
        arc_r = QtCore.QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2)
        gear  = QtGui.QPainterPath()
        for i in range(teeth):
            base = 2 * math.pi * i / teeth
            va   = base - math.pi / teeth
            vx, vy = cx + r_base * math.cos(va), cy + r_base * math.sin(va)
            t0, t1 = base - htw, base + htw
            if i == 0:
                gear.moveTo(vx, vy)
            else:
                gear.lineTo(vx, vy)
            gear.lineTo(cx + r_out * math.cos(t0), cy + r_out * math.sin(t0))
            gear.arcTo(arc_r, -math.degrees(t0), -math.degrees(t1 - t0))
        gear.closeSubpath()

        # 3 window cut-outs between spokes (windows at 60°, 180°, 300°)
        ring_r = QtCore.QRectF(cx - r_ring, cy - r_ring, r_ring * 2, r_ring * 2)
        hub_r  = QtCore.QRectF(cx - r_hub,  cy - r_hub,  r_hub  * 2, r_hub  * 2)
        hw     = math.radians(38.0)
        holes  = QtGui.QPainterPath()
        for i in range(3):
            a_mid  = math.pi / 3 + 2 * math.pi * i / 3
            a0, a1 = a_mid - hw, a_mid + hw
            sec = QtGui.QPainterPath()
            sec.moveTo(cx + r_ring * math.cos(a0), cy + r_ring * math.sin(a0))
            sec.arcTo(ring_r, -math.degrees(a0), -math.degrees(a1 - a0))
            sec.lineTo(cx + r_hub * math.cos(a1), cy + r_hub * math.sin(a1))
            sec.arcTo(hub_r,  -math.degrees(a1),   math.degrees(a1 - a0))
            sec.closeSubpath()
            holes = holes.united(sec)

        ctr_hole = QtGui.QPainterPath()
        ctr_hole.addEllipse(QtCore.QPointF(cx, cy), r_ctr, r_ctr)
        holes = holes.united(ctr_hole)

        p.setBrush(color)
        p.setPen(QtCore.Qt.NoPen)
        p.drawPath(gear.subtracted(holes))

    elif name == "plus_circle":
        # SF "plus.circle": circle with plus sign
        r  = s * 0.30
        hl = r * 0.54
        p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        p.drawLine(QtCore.QPointF(cx - hl, cy), QtCore.QPointF(cx + hl, cy))
        p.drawLine(QtCore.QPointF(cx, cy - hl), QtCore.QPointF(cx, cy + hl))

    elif name == "play":
        # SF "play.fill": solid right-pointing triangle
        r = s * 0.28
        path = QtGui.QPainterPath()
        path.moveTo(cx + r * 0.88,  cy)
        path.lineTo(cx - r * 0.45,  cy - r * 0.82)
        path.lineTo(cx - r * 0.45,  cy + r * 0.82)
        path.closeSubpath()
        p.setBrush(color)
        p.setPen(QtCore.Qt.NoPen)
        p.drawPath(path)

    elif name == "arrow_left":
        # SF "arrow.left": shaft with arrowhead
        l  = s * 0.28
        ah = s * 0.145
        p.drawLine(QtCore.QPointF(cx - l, cy), QtCore.QPointF(cx + l * 0.85, cy))
        p.drawLine(QtCore.QPointF(cx - l, cy), QtCore.QPointF(cx - l + ah, cy - ah))
        p.drawLine(QtCore.QPointF(cx - l, cy), QtCore.QPointF(cx - l + ah, cy + ah))

    elif name == "arrow_up":
        # SF "arrow.up": shaft with arrowhead pointing upward
        l  = s * 0.28
        ah = s * 0.145
        p.drawLine(QtCore.QPointF(cx, cy + l), QtCore.QPointF(cx, cy - l * 0.85))
        p.drawLine(QtCore.QPointF(cx, cy - l), QtCore.QPointF(cx - ah, cy - l + ah))
        p.drawLine(QtCore.QPointF(cx, cy - l), QtCore.QPointF(cx + ah, cy - l + ah))

    elif name == "checkmark":
        # SF "checkmark": clean tick
        pen2 = QtGui.QPen(color, max(1.5, s * 0.095),
                          QtCore.Qt.SolidLine,
                          QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        p.setPen(pen2)
        p.drawLine(QtCore.QPointF(cx - s*0.27, cy + s*0.04),
                   QtCore.QPointF(cx - s*0.05, cy + s*0.26))
        p.drawLine(QtCore.QPointF(cx - s*0.05, cy + s*0.26),
                   QtCore.QPointF(cx + s*0.30,  cy - s*0.20))

    elif name == "xmark":
        # SF "xmark": diagonal cross
        d = s * 0.23
        p.drawLine(QtCore.QPointF(cx - d, cy - d), QtCore.QPointF(cx + d, cy + d))
        p.drawLine(QtCore.QPointF(cx + d, cy - d), QtCore.QPointF(cx - d, cy + d))

    elif name == "save":
        # SF "arrow.down.to.line": down arrow with U-shaped tray
        tray_y  = cy + s * 0.20
        tray_hw = s * 0.26
        tray_h  = s * 0.11
        p.drawLine(QtCore.QPointF(cx - tray_hw, tray_y),
                   QtCore.QPointF(cx - tray_hw, tray_y + tray_h))
        p.drawLine(QtCore.QPointF(cx - tray_hw, tray_y + tray_h),
                   QtCore.QPointF(cx + tray_hw, tray_y + tray_h))
        p.drawLine(QtCore.QPointF(cx + tray_hw, tray_y + tray_h),
                   QtCore.QPointF(cx + tray_hw, tray_y))
        arr_top = cy - s * 0.18
        arr_bot = tray_y - lw * 0.5
        p.drawLine(QtCore.QPointF(cx, arr_top), QtCore.QPointF(cx, arr_bot))
        ah = s * 0.13
        p.drawLine(QtCore.QPointF(cx, arr_bot),
                   QtCore.QPointF(cx - ah, arr_bot - ah))
        p.drawLine(QtCore.QPointF(cx, arr_bot),
                   QtCore.QPointF(cx + ah, arr_bot - ah))

    elif name == "printer":
        # SF "printer": rounded chassis + paper sheet protruding above + output slot
        bw    = s * 0.27
        p_top = cy - s*0.28   # paper top
        p_bot = cy - s*0.06   # paper bottom / printer top
        pr_bot = cy + s*0.20
        pw    = s * 0.18
        # Paper sheet
        p.drawRoundedRect(QtCore.QRectF(cx - pw, p_top, pw * 2, p_bot - p_top), 1.5, 1.5)
        # Printer chassis
        p.drawRoundedRect(QtCore.QRectF(cx - bw, p_bot, bw * 2, pr_bot - p_bot), 3.5, 3.5)
        # Output slot
        slot_y = p_bot + (pr_bot - p_bot) * 0.60
        p.drawLine(QtCore.QPointF(cx - pw * 0.75, slot_y),
                   QtCore.QPointF(cx + pw * 0.75, slot_y))

    elif name == "eye":
        # SF "eye": smooth almond shape with filled pupil
        ew  = s * 0.295
        ech = s * 0.19
        path = QtGui.QPainterPath()
        path.moveTo(cx - ew, cy)
        path.cubicTo(cx - ew * 0.35, cy - ech,
                     cx + ew * 0.35, cy - ech,
                     cx + ew, cy)
        path.cubicTo(cx + ew * 0.35, cy + ech,
                     cx - ew * 0.35, cy + ech,
                     cx - ew, cy)
        path.closeSubpath()
        p.drawPath(path)
        r_p = s * 0.092
        p.setBrush(color)
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(cx, cy), r_p, r_p)

    elif name == "sidebar":
        # SF "sidebar.left": rounded rect outline + vertical divider near the left
        w  = s * 0.62
        h  = s * 0.50
        rx = cx - w / 2
        ry = cy - h / 2
        rect = QtCore.QRectF(rx, ry, w, h)
        p.drawRoundedRect(rect, 3, 3)
        dx = rx + w * 0.34
        p.drawLine(QtCore.QPointF(dx, ry), QtCore.QPointF(dx, ry + h))

    elif name == "search":
        # SF "magnifyingglass": circle + diagonal handle
        r   = s * 0.225
        gcx = cx - s * 0.065
        gcy = cy - s * 0.065
        p.drawEllipse(QtCore.QPointF(gcx, gcy), r, r)
        hx0 = gcx + r * 0.74
        hy0 = gcy + r * 0.74
        hx1 = cx + s * 0.30
        hy1 = cy + s * 0.30
        p.drawLine(QtCore.QPointF(hx0, hy0), QtCore.QPointF(hx1, hy1))

    elif name == "info":
        # SF "info.circle": circle outline + "i" glyph (dot + stem)
        r = s * 0.33
        p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        dot_r = max(1.0, s * 0.042)
        p.setBrush(color)
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(cx, cy - r * 0.36), dot_r, dot_r)
        stem_pen = QtGui.QPen(color, max(1.4, s * 0.075), QtCore.Qt.SolidLine,
                              QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        p.setPen(stem_pen)
        p.drawLine(QtCore.QPointF(cx, cy - r * 0.06),
                   QtCore.QPointF(cx, cy + r * 0.55))

    elif name == "share":
        # SF "square.and.arrow.up": open-top box + upward arrow from center
        bw   = s * 0.26
        top  = cy + s * 0.03
        bot  = cy + s * 0.33
        p.drawLine(QtCore.QPointF(cx - bw, top),  QtCore.QPointF(cx - bw, bot))
        p.drawLine(QtCore.QPointF(cx - bw, bot),  QtCore.QPointF(cx + bw, bot))
        p.drawLine(QtCore.QPointF(cx + bw, bot),  QtCore.QPointF(cx + bw, top))
        ay1 = cy - s * 0.31
        ay0 = top
        p.drawLine(QtCore.QPointF(cx, ay0), QtCore.QPointF(cx, ay1))
        ah = s * 0.12
        p.drawLine(QtCore.QPointF(cx, ay1), QtCore.QPointF(cx - ah, ay1 + ah))
        p.drawLine(QtCore.QPointF(cx, ay1), QtCore.QPointF(cx + ah, ay1 + ah))

    elif name == "markup":
        # SF "pencil": slanted pencil body with pointed tip + flat eraser end
        import math as _m
        angle = _m.radians(45)
        l = s * 0.30
        dx, dy = l * _m.cos(angle), l * _m.sin(angle)
        tip = QtCore.QPointF(cx - dx, cy + dy)
        top = QtCore.QPointF(cx + dx, cy - dy)
        perp_dx, perp_dy = dy * 0.14, dx * 0.14
        p.drawLine(QtCore.QPointF(tip.x() + perp_dx, tip.y() - perp_dy),
                   QtCore.QPointF(top.x() + perp_dx, top.y() - perp_dy))
        p.drawLine(QtCore.QPointF(tip.x() - perp_dx, tip.y() + perp_dy),
                   QtCore.QPointF(top.x() - perp_dx, top.y() + perp_dy))
        p.drawLine(top, QtCore.QPointF(top.x() - perp_dx * 2, top.y() + perp_dy * 2))
        p.drawLine(top, QtCore.QPointF(top.x() + perp_dx * 2, top.y() - perp_dy * 2))
        tip_path = QtGui.QPainterPath()
        tip_path.moveTo(tip)
        tip_path.lineTo(tip.x() + perp_dx, tip.y() - perp_dy)
        tip_path.lineTo(tip.x() - perp_dx, tip.y() + perp_dy)
        tip_path.closeSubpath()
        p.setBrush(color)
        p.setPen(QtCore.Qt.NoPen)
        p.drawPath(tip_path)

    elif name == "a_circle":
        # SF "a.circle": circle outline + capital "A" inside
        r = s * 0.33
        p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        font = QtGui.QFont(_SF_FAMILY or "")
        font.setPixelSize(int(s * 0.38))
        font.setWeight(QtGui.QFont.Medium)
        p.setFont(font)
        p.setPen(color)
        p.drawText(QtCore.QRectF(cx - r, cy - r, r * 2, r * 2),
                   QtCore.Qt.AlignCenter, "A")

    p.restore()
