# PdfPickerApp — Architecture Reference

Stack: **PySide6 + PyMuPDF (fitz)**. All UI custom-painted (paintEvent). No Qt Designer / .ui files.

---

## Files

| File | Key class(es) / purpose |
|---|---|
| `main.py` | `QApplication` → `ScreenMain`; handles CLI PDF arg |
| `theme.py` | `Theme` dataclass · `ThemeManager` · `THEME_MGR` singleton |
| `constants.py` | `group_color(n)` reads THEME_MGR; fixed color constants |
| `icons.py` | `draw(p,rect,name,color)` · `sf_font(px,w)` — stroke from THEME_MGR |
| `pdf_utils.py` | `clear_layout` · `safe_thumbnail_render` |
| `widgets.py` | All reusable thumbnail/card widgets (see Widgets section) |
| `screen_main.py` | `ScreenMain` · `DropZone` · `NavButton` · `DrillDownPanel` |
| `screen_merge.py` | `ScreenMergeMulti` — split/merge editor |
| `screen_viewer.py` | `ScreenViewer` · `PageWidget` — PDF viewer + status bar |
| `screen_settings.py` | `ScreenSettings` · `_MiniPreview` — live theme editor |
| `word_editor.py` | `WordEditor` — embedded .docx editor (workspace screen) |
| `win_register.py` | `register_as_pdf_viewer()` — Windows HKCU registry; no-op elsewhere |
| `theme.json` | Saved theme overrides (created on first save) |
| `window_state.json` | Saved window size |

### Linux packaging (`linux/`)

| File | Purpose |
|---|---|
| `linux/build.sh` | PyInstaller → AppImage / .deb / .rpm |
| `linux/PdfPickerApp_linux.spec` | PyInstaller spec (excludes winreg/pywin32) |
| `linux/AppRun` | AppImage entry; sets `LD_LIBRARY_PATH`, `QT_QPA_PLATFORM_PLUGIN_PATH` |
| `linux/pdfpickerapp.desktop` | XDG desktop; registers `application/pdf` MIME |

---

## Screen Layout (screen_main.py)

```
ScreenMain (QWidget)
│
├── _sidebar  QFrame  (left, 210px expanded / 62px collapsed)
│   ├── _toggle_btn "☰  PdfPickerApp"         → _toggle_sidebar()
│   ├── _left_panel  DrillDownPanel(on_folder_open=_expand_sidebar)
│   │   ├── NavButton "PDF"  [folder]          → push sub-page + _expand_sidebar()
│   │   │   sub-page:
│   │   │   ├── ← PDF  (_BackHeader)
│   │   │   ├── • Відкрити PDF                → _select("viewer")
│   │   │   ├── • Розділити/Об'єднати PDF     → _select("editor")
│   │   │   ├── • Конвертувати                → _select("convert")
│   │   │   └── • Стиснути PDF                → _select("compress")
│   │   └── NavButton "Word"  [folder]         → push sub-page + _expand_sidebar()
│   │       clicked also → _select("word")     ← updates workspace/right-panel immediately
│   │       sub-page:
│   │       ├── ← Word  (_BackHeader)
│   │       └── • Відкрити Word               → _on_open_word()
│   ├── [divider]
│   └── NavButton "?"  "Довідка"              → _merge._show_help()
│
├── _stack  QStackedWidget  (workspace)
│   ├── _drop_zone          DropZone(pdf)          editor entry
│   ├── _merge              ScreenMergeMulti
│   ├── _viewer             ScreenViewer
│   ├── _viewer_drop_zone   DropZone(pdf)          viewer entry
│   ├── _word_editor        WordEditor
│   ├── _word_drop_zone     DropZone(docx)         word entry
│   └── ComingSoonWidget × 2  (convert, compress)
│
└── _right_sidebar  QFrame  (right, 210px / 62px collapsed)
    ├── _right_toggle_btn "☰  Інструменти"
    └── _right_tool_stack  QStackedWidget
        ├── [0] editor tools    (checkmark/xmark/save/plus_circle/arrow_left NavButtons)
        ├── [1] viewer tools    DrillDownPanel — "Відкрити PDF" + "Друк документа" folder
        └── [2] empty QWidget   (word, convert, compress, settings)
```

### _select(key)

```python
_PDF_KEYS = {"viewer", "editor", "convert", "compress"}

"editor"   → right[0]; show _merge or _drop_zone
"viewer"   → right[1]; show _viewer or _viewer_drop_zone
"word"     → right[2]; show _word_editor (has_file()) or _word_drop_zone
other key  → right[2]; show ComingSoonWidget

nav_btns["__pdf__"].set_active(key in _PDF_KEYS)
nav_btns["__word__"].set_active(key == "word")
```

### Sidebar collapse

```python
_expand_sidebar()           # called by DrillDownPanel.on_folder_open
  if _collapsed: _toggle_sidebar()

_toggle_sidebar()
  animate minimumWidth: 210 ↔ 62  (220ms InOutCubic)
  if collapsing: _left_panel.reset()   # back to main page
```

### DropZone (parameterizable)

```python
DropZone(
    hint_text   = "Перетягни PDF сюди або натисни, щоб вибрати",
    extensions  = (".pdf",),
    dialog_filter = "PDF files (*.pdf)",
)
# Word drop zone uses: hint_text="Відкрити Word\nПеретягни .docx...", extensions=(".docx",)
# _accepts(path) checks any(path.lower().endswith(ext) for ext in extensions)
```

### NavButton (custom-painted)

```
paintEvent reads THEME_MGR.get() every frame:
  active bg:   nav_active_bg  + nav_active_bg_alpha
  hover bg:    nav_hover_bg   + nav_hover_bg_alpha
  icon color:  nav_icon_active/inactive_color + alpha   (icon_size px)
  label color: nav_label_active/inactive_color + alpha
  icons.draw() — stroke = icon_stroke × rect_min
```

### DrillDownPanel

Used for BOTH left sidebar navigation and right viewer tools.

```python
DrillDownPanel(on_folder_open=None)
  add_folder(icon, label, [(label, cb), ...]) → NavButton
    # _push(sub_idx) is called on btn.clicked
    # _push calls on_folder_open() when idx != 0
  add_action(icon, label, cb) → NavButton
  reset()   → _push(0)  # back to main page

_push(idx):
  if idx != 0 and on_folder_open: on_folder_open()
  stack.setCurrentIndex(idx)
```

---

## Word Editor (word_editor.py)

```
WordEditor (QWidget)           # workspace screen, not a dialog
├── _toolbar  QWidget (46px)
│   ├── _btn_open / _btn_save / _btn_print / _btn_pdf
│   └── _lbl_title  "filename.docx"
└── _editor  QTextEdit (rich text, accepts drops disabled)
    rootFrame: background=#ffffff, margin=20, padding=54  ← white page on gray canvas
```

### State

```python
_path: str | None    # None until first file opened
_modified: bool      # only set True when _path is not None (avoids false positive from _apply_page_format)
```

### Appearance

```python
apply_theme():
  QTextEdit stylesheet: background:#c8c8c8 (gray canvas) + QScrollBar dark styling
  _apply_page_format()     # called here AND after every setHtml()

_apply_page_format():
  QTextFrameFormat: background=#ffffff, margin=20pt, padding=54pt
  → white page centered on gray canvas; must be re-applied after setHtml()
```

### Load pipeline

```python
_load(path):
  DocxDocument(path) → _docx_to_html(doc) → editor.setHtml(html)
  _apply_page_format()   # setHtml() resets rootFrame → must reapply
  editor.moveCursor(Start)
  _path = path; _modified = False
```

### docx → HTML conversion (_docx_to_html)

Fully manual conversion via python-docx XML — no mammoth dependency.

```
Per paragraph:
  alignment   para.alignment → text-align (justify/left/right/center)
  spacing     space_before/after → margin-top/bottom (pt)
  line-height pf.line_spacing (MULTIPLE rule)
  indent      pf.left_indent + first_line_indent → margin-left + text-indent (pt)
  tag         "heading N" style → h1/h2/h3, else p

List detection (two-level lookup):
  1. para._p.pPr → numPr element   (direct paragraph override)
  2. para.style.element → pPr → numPr   (inherited from style, e.g. "List Number")
  numId + ilvl → counter tracking per (numId, ilvl) key
  _list_type(doc, numId, ilvl):
    doc.part.numbering_part → abstractNum → lvl → numFmt
    "decimal" → "N.  " prefix;  else → "•  " prefix
    margin-left=36+ilvl*18pt, text-indent=-18pt (hanging indent)

Per run:
  font-family  run.font.name
  font-size    run.font.size.pt
  color        run.font.color (MSO_COLOR_TYPE.RGB only)
  bold/italic/underline/strike  → <b>/<i>/<u>/<s> tags
```

### Save

```python
_save_to(path):
  Iterates QTextDocument blocks → python-docx paragraphs
  heading level → add_heading(); else add_paragraph()
  alignment, font name/size, color, bold/italic/underline per fragment
```

### PDF export

```python
# Cascading fallback — platform-agnostic:
1. libreoffice --headless --convert-to pdf   (if installed)
2. docx2pdf.convert(src, out)               (if installed; uses MS Word on Win/macOS)
3. QPrinter PDF output                      (always works; limited formatting)
```

---

## Theme System (theme.py)

### Theme fields

```
# Backgrounds
bg_main     "#21232a"    workspace
bg_sidebar  "#191b21"    sidebars
bg_border   "#2a3045"    panel borders
bg_hover    "#252830"    1px dividers
viewer_bg   "#2c2f3d"    scroll area under PDF pages
accent      "#6EDE8A"    DropZone drag highlight

# Nav overlay (color + alpha 0-255)
nav_active_bg / nav_active_bg_alpha
nav_hover_bg  / nav_hover_bg_alpha

# Icon colors (color + alpha)
nav_icon_active_color   / nav_icon_active_alpha    (default: white/220)
nav_icon_inactive_color / nav_icon_inactive_alpha  (default: white/150)

# Label colors (color + alpha)
nav_label_active_color   / nav_label_active_alpha   (default: white/220)
nav_label_inactive_color / nav_label_inactive_alpha (default: white/170)

# Icon rendering
icon_size   int    20       px, NavButton paintEvent
icon_stroke float  0.09     × rect_min → pen width in icons.draw()

# Group colors (8 pastel Apple HIG)
group_color_0..7  str   read by constants.group_color(n)

# Status bar (alpha 0-255)
statusbar_file_alpha    166
statusbar_page_alpha    115
statusbar_cursor_alpha  90

# Viewer
scrollbar_alpha   46          scrollbar handle alpha
selection_color   "#50a0ff"   text selection + rubber-band
```

### ThemeManager API

```python
THEME_MGR.get()            → Theme
THEME_MGR.update(**kwargs) → set fields + notify listeners
THEME_MGR.save()           → write theme.json
THEME_MGR.reset()          → restore defaults + notify
THEME_MGR.add_listener(cb) → cb() on every update/reset
```

Registered listeners: `ScreenMain._apply_theme`, `ScreenViewer.apply_theme`,
`WordEditor.apply_theme`, `ScreenSettings._sync_from_theme`, `_MiniPreview.update`.

---

## Viewer (screen_viewer.py)

```
ScreenViewer (QWidget)
├── QScrollArea (_scroll)       bg: viewer_bg
│   └── _container QWidget
│       └── _vbox QVBoxLayout
│           └── PageWidget × N
└── _status_bar QWidget (28px)
    ├── _lbl_file   (stretch 1)    "filename.pdf"
    ├── _lbl_pages  (52px center)  "3/9"
    └── _lbl_cursor (130px right)  "x 123.4  y 456.7 pt"
```

### PageWidget

```
_render()     fitz.Matrix(scale) → QPixmap
_load_words() get_text("words") → rects in screen coords

paintEvent:
  drawPixmap
  highlighted words  → fillRect QColor(selection_color, alpha=90)
  rubber-band rect   → QPen(selection_color, alpha=160) + fill alpha=28

Ctrl+Wheel → eventFilter → _zoom_in/_zoom_out
mouseMoveEvent → cursor_moved signal → _lbl_cursor
leaveEvent → cursor_left signal → clears _lbl_cursor
```

### Print

```python
print_document()  → QPrintDialog  → _do_print(printer)
print_preview()   → QPrintPreviewDialog.paintRequested → _do_print(printer)
_do_print()       → QPainter per page; scaled KeepAspectRatio, centered
```

---

## Settings Screen (screen_settings.py)

```
ScreenSettings
├── _MiniPreview (256px, sticky)
│   └── paintEvent — mini replica: sidebar, nav items, viewer_bg, group swatches, accent
└── QScrollArea
    ├── ФОН ПРОГРАМИ        5 color rows (bg_main, bg_sidebar, bg_border, bg_hover, accent)
    ├── ПУНКТИ НАВІГАЦІЇ    6 color+alpha rows
    ├── ІКОНКИ              2 sliders (icon_size 16-28, icon_stroke 5-15%)
    ├── КОЛЬОРИ ГРУП        8 color buttons (2-column grid)
    └── ПЕРЕГЛЯДАЧ PDF      2 colors + 4 alpha sliders
```

`_sync_from_theme()` — THEME_MGR listener; updates controls with `blockSignals` to avoid loops.

---

## Icons (icons.py)

```python
_ICON_NAMES = {scissors, merge, rotate, compress_layers, gear,
               plus_circle, play, arrow_left, arrow_up,
               checkmark, xmark, eye, save, printer}

draw(p, rect, name, color):
  lw = max(1.5, min(rect) * THEME_MGR.get().icon_stroke)
  pen: RoundCap, RoundJoin, SolidLine

# gear is filled (setBrush), not stroked:
#   outer 12-tooth shape  subtracted  3 window sectors + centre hole
#   arcTo convention: arcTo(rect, -deg(a), -deg(span)) = clockwise on screen
```

---

## Editor State (ScreenMergeMulti)

```python
files           list[str]                       # open paths
doc_cache       dict[path → fitz.Document]
page_list       list[(path, actual_i)]          # sole source of page order
page_groups     list[int|None]                  # parallel
page_rotations  list[int]                       # parallel; 0/90/180/270
group_names     dict[int → str]
_active_group   int
_num_groups     int                             # default 4
_pixmap_cache   OrderedDict[(path,ai,rot) → QPixmap]   # LRU max 200
_page_ar_cache  dict[(path,ai) → float]         # native w/h from fitz
_undo_stack     deque(maxlen=50)                # snapshots of 3 lists

# drag state
_drag_src       int|None
_drop_idx       int|None
_dragged_card   DraggableCard|None
_drag_active    bool
_vi_to_card     dict[vi → DraggableCard]        # rebuilt each render_thumbnails
```

**Invariant:** `len(page_list) == len(page_groups) == len(page_rotations)` always.

### Drag-and-drop (critical)

`drag.exec()` is blocking — if `render_thumbnails → clear_layout` fires during it, the card is destroyed mid-drag → segfault / flicker.

```python
start_drag(src_idx, card):
  # ghost in-place via QGraphicsOpacityEffect(0.22) — no grid rebuild

end_drag():
  _drag_active = False; _dragged_card = None
  _render_timer.start(0)   # ONLY render trigger during drag cycle

reorder_pages():
  # does NOT start _render_timer — prevents rebuild while drag.exec() runs
```

### Render pipeline

```
render_thumbnails()
  _build_render_items():
    group == None           → 'page' (ungrouped)
    group == _active_group  → 'page' (expanded group)
    group != _active_group  → 'deck' (collapsed, first occurrence only)
  'page' → _add_thumb_card()
    eff_ar = ar if rot%180==0 else 1/ar
    thumb_h = clamp(thumb_w / eff_ar, 40, 500)
  'deck' → GroupDeck(pixmaps, base_thumb_h)
```

Re-render always via `_render_timer.start(0)` (0 ms debounce, single-shot).

---

## Key Flows

**Open docx:**
```
Word folder btn clicked
  → DrillDownPanel._push(sub_idx)  → _expand_sidebar() if collapsed
  → _select("word")                → show _word_drop_zone

_word_drop_zone.file_chosen / "Відкрити Word" clicked
  → _open_word_path(path)
    → unsaved check (only if _path is not None)
    → _word_editor.open_file(path)
    → _select("word")              → show _word_editor
```

**Open PDF in viewer:**
```
_viewer_drop_zone.file_chosen → _on_viewer_file_chosen() → _viewer.load_pdf() → _select("viewer")
right-panel "Відкрити PDF"    → QFileDialog              → _viewer.load_pdf()
```

**Theme change:**
```
slider/color changed
  → THEME_MGR.update(k=v) → _notify()
      ScreenMain._apply_theme()          sidebar stylesheets + btn.update()
      ScreenViewer.apply_theme()         scroll area + status bar
      WordEditor.apply_theme()           toolbar + editor + _apply_page_format()
      ScreenSettings._sync_from_theme()  controls update (blockSignals)
      _MiniPreview.update()              repaint
```

**Export PDF:**
```
run_merge():
  group page_list by page_groups (skip None)
  for each group: fitz.open() + insert_pdf() per page
    if rot: pg.set_rotation((existing + rot) % 360)
  name: group_names.get(g) or "merged_group_NN"
```

**Undo:**
```
_push_undo()  → deepcopy(page_list, page_groups, page_rotations) → deque
undo()        → pop → restore → _render_timer.start(0)
```

---

## Constants (constants.py)

```python
GREEN_COLOR  = "#6EDE8A"
RED_COLOR    = "#FF7C75"
BREAK_COLOR  = "#92DFFF"
BORDER_COLOR = "#8E8E93"
MAX_GROUPS   = 100
THUMB_SCALE  = 0.42

group_color(n):   # reads THEME_MGR.get().group_color_{n-1}  (live-updating)
```

---

## Widgets (widgets.py)

| Class | Purpose |
|---|---|
| `_HoverMixin` | Mixin: `_hover` tracking via `WA_Hover`; call `_init_hover()` in `__init__` |
| `GroupButton` | Group selector + thumbnail overlay |
| `GroupDeck` | Collapsed group (animated pixmap stack) |
| `FullBorderPaper` | White card with colored group border |
| `ThumbnailActionButton` | 28×28 rotate button in card strip |
| `DraggableCard` | Thumbnail wrapper; drag + click |

### Card structure

```
DraggableCard  (cell_w × thumb_h+60)
├── FullBorderPaper  (thumb_w × thumb_h)   click = toggle group
│   └── GroupButton  (42×42, pos 4,4)      WA_TransparentForMouseEvents
└── strip QWidget  (cell_w × 60)
    ├── QLabel "Ф-N с.M"                   WA_TransparentForMouseEvents
    └── ThumbnailActionButton (28×28)       click = rotate_page
```

---

## Build

### Windows

```
PyInstaller:  venv\Scripts\pyinstaller PdfPickerApp.spec --clean
              → dist\PdfPickerApp\PdfPickerApp.exe  (onedir)

Inno Setup:   ISCC.exe installer.iss
              → installer_output\PdfPickerApp_Setup_v1.0.exe

win_register.py: runs only when frozen (sys.frozen) on win32
```

### Linux

```
bash linux/build.sh [--appimage] [--deb] [--rpm]   (default: all three)
  → dist_linux/PdfPickerApp-1.0.0-x86_64.AppImage
  → dist_linux/pdfpickerapp_1.0.0_amd64.deb
  → dist_linux/pdfpickerapp-1.0.0-1.x86_64.rpm

AppDir/
├── AppRun    sets LD_LIBRARY_PATH + QT_QPA_PLATFORM_PLUGIN_PATH
├── pdfpickerapp.desktop
├── pdfpickerapp.png
└── usr/bin/  PyInstaller onedir output
```
