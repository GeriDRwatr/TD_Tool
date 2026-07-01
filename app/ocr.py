"""Розпізнавання тексту (OCR) для сканованих PDF без текстового шару.

Використовує системний бінарник tesseract напряму через subprocess (за зразком
_convert_via_libreoffice у word_editor.py) — без додаткових pip-залежностей
(pytesseract/Pillow), консистентно з мінімальним footprint-ом проєкту.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import fitz

_log = logging.getLogger(__name__)

_OCR_DPI = 300
_TEXT_SAMPLE_PAGES = 3
_TEXT_SAMPLE_MIN_CHARS = 20


class OcrError(Exception):
    """Помилка розпізнавання тексту — повідомлення вже придатне для показу користувачу."""


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def available_languages() -> set[str]:
    """Мовні пакети tesseract, встановлені в системі (порожньо, якщо tesseract відсутній)."""
    if not tesseract_available():
        return set()
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True, text=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        _log.warning("Не вдалося отримати список мов tesseract", exc_info=True)
        return set()
    lines = result.stdout.splitlines()
    return {ln.strip() for ln in lines[1:] if ln.strip()}


LANGUAGE_CHOICES: tuple[tuple[str, str], ...] = (
    ("ukr", "Українська"),
    ("eng", "Англійська"),
    ("ukr+eng", "Змішаний текст (укр + англ)"),
)


def pick_language(preferred: str = "ukr") -> str:
    """Обирає мову розпізнавання: `preferred`, якщо вона встановлена, інакше 'eng'.

    Свідомо НЕ комбінує кілька мов автоматично (напр. 'ukr+eng' за замовчуванням)
    — кирилиця та латиниця мають купу однаково намальованих літер (а, о, е, р,
    с, х, у...), і мультимовний режим tesseract регулярно плутає їх навіть у
    чисто одномовному тексті, підставляючи символ не тієї абетки. Змішаний
    режим лишається доступним (LANGUAGE_CHOICES), але як свідомий вибір
    користувача в UI, а не мовчазний дефолт.
    """
    installed = available_languages()
    return preferred if preferred in installed else "eng"


def has_text_layer(doc: fitz.Document, sample_pages: int = _TEXT_SAMPLE_PAGES) -> bool:
    """Евристика: чи документ уже має текстовий шар (тоді OCR, ймовірно, не потрібен)."""
    for i in range(min(sample_pages, doc.page_count)):
        if len(doc.load_page(i).get_text("text").strip()) >= _TEXT_SAMPLE_MIN_CHARS:
            return True
    return False


def _ocr_page_to_pdf_bytes(page: fitz.Page, lang: str, tmp_dir: Path) -> bytes:
    """Рендерить сторінку в PNG і проганяє через tesseract, повертає байти
    single-page PDF (зображення сторінки + невидимий шар розпізнаного тексту).

    Рендер у градаціях сірого — менше кольорового шуму на вході tesseract.
    Свідомо БЕЗ авто-визначення повороту через OSD: на реальних сканах з
    трохи "заяложеним"/розмитим друком OSD плутає навіть просту кирилицю
    (визначав "Arabic" з мізерною впевненістю) і розвертав правильно
    орієнтовані сторінки на 180°, перетворюючи чіткий текст на кашу —
    гірше, ніж узагалі без корекції."""
    zoom = fitz.Matrix(_OCR_DPI / 72, _OCR_DPI / 72)
    png_path = tmp_dir / f"page_{page.number}.png"
    out_base = tmp_dir / f"page_{page.number}_ocr"

    pix = page.get_pixmap(matrix=zoom, colorspace=fitz.csGRAY, alpha=False)
    pix.save(str(png_path))

    try:
        subprocess.run(
            ["tesseract", str(png_path), str(out_base), "-l", lang, "--dpi", str(_OCR_DPI), "pdf"],
            capture_output=True, timeout=120, check=True,
        )
    except FileNotFoundError as e:
        raise OcrError(
            "Бінарник tesseract не знайдено. Встанови його й спробуй знову."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise OcrError(f"Розпізнавання сторінки {page.number + 1} тривало занадто довго.") from e
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", "replace") if e.stderr else str(e)
        raise OcrError(f"tesseract повернув помилку на сторінці {page.number + 1}:\n{stderr}") from e

    out_pdf = out_base.with_suffix(".pdf")
    return out_pdf.read_bytes()


def ocr_document(
    doc: fitz.Document,
    lang: str,
    progress_cb: Callable[[int, int], bool] | None = None,
) -> fitz.Document:
    """Повертає нову копію документа з доданим (невидимим) текстовим шаром на кожній
    сторінці. progress_cb(done, total) викликається після кожної сторінки; якщо
    повертає False — розпізнавання переривається і піднімається OcrError."""
    out_doc = fitz.open()
    with tempfile.TemporaryDirectory(prefix="tdtool_ocr_") as tmp:
        tmp_dir = Path(tmp)
        for i in range(doc.page_count):
            page_pdf_bytes = _ocr_page_to_pdf_bytes(doc.load_page(i), lang, tmp_dir)
            with fitz.open("pdf", page_pdf_bytes) as page_doc:
                out_doc.insert_pdf(page_doc)
            if progress_cb is not None and not progress_cb(i + 1, doc.page_count):
                out_doc.close()
                raise OcrError("Розпізнавання скасовано користувачем.")
    return out_doc
