from unittest.mock import patch

import fitz

from app import ocr


def _doc_with_text(text: str) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    return doc


def test_has_text_layer_true_for_document_with_text():
    doc = _doc_with_text("Це достатньо довгий текст для впевненого детекту шару.")
    assert ocr.has_text_layer(doc) is True


def test_has_text_layer_false_for_blank_scanned_page():
    doc = _doc_with_text("")
    assert ocr.has_text_layer(doc) is False


def test_has_text_layer_ignores_pages_beyond_sample():
    doc = fitz.open()
    doc.new_page()   # порожня
    p2 = doc.new_page()
    p2.insert_text((72, 72), "текст лише на другій сторінці, досить довгий")

    assert ocr.has_text_layer(doc, sample_pages=1) is False
    assert ocr.has_text_layer(doc, sample_pages=2) is True


def test_available_languages_empty_when_tesseract_missing():
    with patch.object(ocr, "tesseract_available", return_value=False):
        assert ocr.available_languages() == set()


def test_pick_language_prefers_ukrainian_when_installed():
    with patch.object(ocr, "available_languages", return_value={"eng", "ukr", "osd"}):
        assert ocr.pick_language() == "ukr"


def test_pick_language_falls_back_to_english_when_preference_missing():
    with patch.object(ocr, "available_languages", return_value={"eng", "osd"}):
        assert ocr.pick_language() == "eng"


def test_pick_language_falls_back_when_nothing_installed():
    with patch.object(ocr, "available_languages", return_value=set()):
        assert ocr.pick_language() == "eng"


def test_pick_language_respects_explicit_preference():
    with patch.object(ocr, "available_languages", return_value={"eng", "ukr", "osd"}):
        assert ocr.pick_language(preferred="eng") == "eng"
        assert ocr.pick_language(preferred="ukr+eng") == "eng"  # не встановлено як єдина мова


def test_ocr_document_reports_error_when_tesseract_missing(tmp_path):
    doc = _doc_with_text("")
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        try:
            ocr.ocr_document(doc, "eng")
        except ocr.OcrError as e:
            assert "tesseract" in str(e).lower()
        else:
            raise AssertionError("очікували OcrError")
