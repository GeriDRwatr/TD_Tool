import os
from collections import defaultdict
import fitz
from PySide6 import QtCore, QtGui


def clear_layout(layout) -> None:
    """Видаляє всі дочірні віджети з layout."""
    if layout is None:
        return
    while layout.count():
        it = layout.takeAt(0)
        w  = it.widget()
        if w is not None:
            w.setAcceptDrops(False)
            w.hide()
            w.deleteLater()


def safe_thumbnail_render(page, matrix) -> QtGui.QPixmap:
    """Рендерить сторінку PDF у QPixmap; повертає fallback-зображення при помилці."""
    fallback = QtGui.QPixmap(160, 220)
    fallback.fill(QtGui.QColor("#d9d9d9"))
    painter = QtGui.QPainter(fallback)
    painter.setPen(QtGui.QColor("#555"))
    painter.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
    painter.drawText(fallback.rect(), QtCore.Qt.AlignCenter, "Помилка рендера")
    painter.end()

    try:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = QtGui.QImage(pix.samples, pix.width, pix.height,
                           pix.stride, QtGui.QImage.Format_RGB888)
        return QtGui.QPixmap.fromImage(img)
    except Exception:
        try:
            pix = page.get_pixmap(matrix=matrix, alpha=True)
            img = QtGui.QImage(pix.samples, pix.width, pix.height,
                               pix.stride, QtGui.QImage.Format_ARGB32)
            return QtGui.QPixmap.fromImage(img)
        except Exception:
            return fallback


def save_page_sequence(doc: fitz.Document, page_indices: list, out_path: str) -> None:
    out = fitz.open()
    for idx in page_indices:
        out.insert_pdf(doc, from_page=idx, to_page=idx)
    out.save(out_path)
    out.close()


def split_pdf(doc: fitz.Document,
              page_order: list,
              page_groups: list,
              pdf_base: str,
              out_dir: str,
              group_names: dict = None) -> int:
    """
    Зберігає кожну групу сторінок як окремий PDF.

    page_groups: індексований actual_i → номер групи (int 1-N) або None
    group_names: {group_num: назва_файлу_без_розширення}
    Повертає кількість створених файлів.
    """
    group_pages: dict[int, list[int]] = defaultdict(list)
    for actual_i in page_order:
        g = page_groups[actual_i]
        if g is not None:
            group_pages[g].append(actual_i)

    created = 0
    for g in sorted(group_pages):
        pages = group_pages[g]
        if not pages:
            continue
        name = (group_names or {}).get(g, "").strip() or f"{pdf_base}_group_{g:02d}"
        if name.lower().endswith(".pdf"):
            name = name[:-4]
        out_path = os.path.join(out_dir, f"{name}.pdf")
        save_page_sequence(doc, pages, out_path)
        created += 1

    return created
