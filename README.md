# TDTool

Десктопний PDF-переглядач та редактор на **PySide6 + PyMuPDF** (Python 3.13).
Кросплатформний: Windows, macOS, Linux.

## Можливості

- Перегляд PDF: неперервний скрол / окрема сторінка / дві сторінки, зум (Ctrl+колесо,
  pinch-жест тачпаду), поворот сторінок, HiDPI/Retina-рендеринг
- Мультивкладковий перегляд декількох PDF одночасно
- Ліва панель мініатюр сторінок і зміст (TOC) документа
- Виділення тексту (слово / рядок / абзац) і пошук по документу
- Розділення та об'єднання PDF (drag-and-drop сторінок і груп сторінок)
- Вбудований редактор .docx з конвертацією в PDF
- Налаштовувана тема оформлення

## Стек

- [PySide6](https://doc.qt.io/qtforpython/) — UI (усе кастомно намальоване, без Qt Designer)
- [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) — рендеринг і робота з PDF
- [python-docx](https://python-docx.readthedocs.io/) — читання/запис .docx

Детальний опис архітектури: [ARCHITECTURE.md](ARCHITECTURE.md).

## Запуск (розробка)

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements_dev.txt
python main.py
```

## Тести та лінтери

```bash
pytest
ruff check .
mypy app
```

## Збірка інсталятора

- Windows: `TDTool.spec` (PyInstaller) + `installer.iss` (Inno Setup)
- Linux: див. `linux/build.sh` (AppImage / .deb / .rpm)
