"""Конвертація docx.Document у HTML для показу в QTextEdit.

Чистий модуль без залежності від Qt — тому легко тестується юніт-тестами.
"""
from __future__ import annotations

import html as _html
import logging

from docx.enum.dml import MSO_COLOR_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING

_log = logging.getLogger(__name__)

_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_ALIGN = {
    WD_ALIGN_PARAGRAPH.LEFT: "left",
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
    None: "justify",
}

_LIST_LEVEL_INDENT_PT = 18
_LIST_BASE_INDENT_PT = 36
_LIST_HANGING_INDENT_PT = -18


def list_type(doc, num_id: int, ilvl: int) -> str:
    """Повертає 'decimal' або 'bullet' для рівня нумерованого списку `numId`/`ilvl`."""
    try:
        numbering_part = doc.part.numbering_part
    except Exception:
        _log.debug("numbering_part недоступний", exc_info=True)
        return "decimal"
    if numbering_part is None:
        return "decimal"
    root = numbering_part._element
    abstract_id = _find_abstract_num_id(root, num_id)
    if abstract_id is None:
        return "decimal"
    fmt = _find_level_num_format(root, abstract_id, ilvl)
    return "decimal" if fmt in (None, "decimal") else "bullet"


def _find_abstract_num_id(root, num_id: int) -> str | None:
    for num_el in root.findall(f"{_NS}num"):
        if num_el.get(f"{_NS}numId") == str(num_id):
            abstract_ref = num_el.find(f"{_NS}abstractNumId")
            return abstract_ref.get(f"{_NS}val") if abstract_ref is not None else None
    return None


def _find_level_num_format(root, abstract_id: str, ilvl: int) -> str | None:
    for abstract_el in root.findall(f"{_NS}abstractNum"):
        if abstract_el.get(f"{_NS}abstractNumId") != abstract_id:
            continue
        for lvl_el in abstract_el.findall(f"{_NS}lvl"):
            if lvl_el.get(f"{_NS}ilvl") == str(ilvl):
                fmt_el = lvl_el.find(f"{_NS}numFmt")
                return fmt_el.get(f"{_NS}val", "decimal") if fmt_el is not None else None
    return None


def _paragraph_indent_pt(pf) -> tuple[int, int]:
    """Лівий та перше-рядковий відступи параграфа в pt (0, якщо не задані)."""
    li_pt = 0
    fi_pt = 0
    if pf.left_indent:
        try:
            li_pt = int(pf.left_indent.pt)
        except Exception:
            _log.debug("left_indent не в pt", exc_info=True)
    if pf.first_line_indent:
        try:
            fi_pt = int(pf.first_line_indent.pt)
        except Exception:
            _log.debug("first_line_indent не в pt", exc_info=True)
    return li_pt, fi_pt


def _line_height_css(pf) -> str:
    if not pf.line_spacing:
        return ""
    if pf.line_spacing_rule not in (WD_LINE_SPACING.MULTIPLE, WD_LINE_SPACING.AT_LEAST, None):
        return ""
    try:
        return f" line-height:{float(pf.line_spacing):.2f};"
    except Exception:
        _log.debug("line_spacing не число", exc_info=True)
        return ""


def _paragraph_num_pr(para):
    """Шукає <w:numPr> параграфа, успадкований від стилю за потреби."""
    p_pr = para._p.pPr
    num_pr = p_pr.find(f"{_NS}numPr") if p_pr is not None else None
    if num_pr is None and para.style and para.style.element is not None:
        style_p_pr = para.style.element.find(f"{_NS}pPr")
        if style_p_pr is not None:
            num_pr = style_p_pr.find(f"{_NS}numPr")
    return num_pr


def _list_prefix(doc, para, li_pt: int, fi_pt: int,
                  list_counters: dict[tuple[int, int], int]) -> tuple[str, int, int]:
    """Повертає (маркер-списку, відкориговані li_pt, fi_pt) для параграфа."""
    num_pr = _paragraph_num_pr(para)
    if num_pr is None:
        return "", li_pt, fi_pt

    ilvl_el = num_pr.find(f"{_NS}ilvl")
    num_id_el = num_pr.find(f"{_NS}numId")
    ilvl = int(ilvl_el.get(f"{_NS}val", "0")) if ilvl_el is not None else 0
    num_id = int(num_id_el.get(f"{_NS}val", "0")) if num_id_el is not None else 0
    if num_id <= 0:
        return "", li_pt, fi_pt

    for key in list(list_counters):
        if key[0] == num_id and key[1] > ilvl:
            list_counters[key] = 0
    key = (num_id, ilvl)
    list_counters[key] = list_counters.get(key, 0) + 1

    is_decimal = list_type(doc, num_id, ilvl) == "decimal"
    prefix = f"{list_counters[key]}.&nbsp;&nbsp;" if is_decimal else "•&nbsp;&nbsp;"
    if li_pt == 0:
        li_pt = _LIST_BASE_INDENT_PT + ilvl * _LIST_LEVEL_INDENT_PT
    if fi_pt == 0:
        fi_pt = _LIST_HANGING_INDENT_PT
    return prefix, li_pt, fi_pt


def _heading_tag(style_name: str) -> str:
    style_lower = style_name.lower()
    if "heading 1" in style_lower:
        return "h1"
    if "heading 2" in style_lower:
        return "h2"
    if "heading 3" in style_lower:
        return "h3"
    return "p"


def _run_to_html(run) -> str:
    text = _html.escape(run.text)
    if not text:
        return ""

    span_css: list[str] = []
    if run.font.name:
        span_css.append(f"font-family:'{run.font.name}'")
    if run.font.size:
        try:
            span_css.append(f"font-size:{run.font.size.pt:.1f}pt")
        except Exception:
            _log.debug("font.size не в pt", exc_info=True)
    try:
        color = run.font.color
        if color.type == MSO_COLOR_TYPE.RGB and color.rgb:
            span_css.append(f"color:#{color.rgb}")
    except Exception:
        _log.debug("font.color недоступний", exc_info=True)

    if span_css:
        text = f'<span style="{"; ".join(span_css)}">{text}</span>'
    if run.bold:
        text = f"<b>{text}</b>"
    if run.italic:
        text = f"<i>{text}</i>"
    if run.underline:
        text = f"<u>{text}</u>"
    if run.font.strike:
        text = f"<s>{text}</s>"
    return text


def _paragraph_to_html(doc, para, list_counters: dict[tuple[int, int], int]) -> str:
    pf = para.paragraph_format
    align = _ALIGN.get(para.alignment, "justify")
    space_before = int(pf.space_before.pt) if pf.space_before else 0
    space_after = int(pf.space_after.pt) if pf.space_after else 6
    li_pt, fi_pt = _paragraph_indent_pt(pf)
    prefix, li_pt, fi_pt = _list_prefix(doc, para, li_pt, fi_pt, list_counters)

    style = (
        f"text-align:{align};"
        f" margin-top:{space_before}pt; margin-bottom:{space_after}pt;"
        f" margin-left:{li_pt}pt; text-indent:{fi_pt}pt;{_line_height_css(pf)}"
    )
    tag = _heading_tag((para.style.name or "") if para.style else "")
    runs_html = [prefix] if prefix else []
    runs_html.extend(_run_to_html(run) for run in para.runs)
    inner = "".join(runs_html) or "&nbsp;"
    return f'<{tag} style="{style}">{inner}</{tag}>'


def docx_to_html(doc) -> str:
    """Конвертує docx.Document у HTML-документ для `QTextEdit.setHtml()`."""
    list_counters: dict[tuple[int, int], int] = {}
    parts = [
        "<html><body style='margin:0; padding:0;"
        " font-family:\"Times New Roman\"; font-size:12pt; color:#111;'>"
    ]
    parts.extend(_paragraph_to_html(doc, para, list_counters) for para in doc.paragraphs)
    parts.append("</body></html>")
    return "\n".join(parts)
