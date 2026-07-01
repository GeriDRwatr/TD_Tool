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
