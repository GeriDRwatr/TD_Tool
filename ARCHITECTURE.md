# TDTool — Architecture Reference

Stack: **PySide6 + PyMuPDF (fitz)**. All UI custom-painted (paintEvent). No Qt Designer / .ui files.

---

## Files

| File | Key class(es) / purpose |
|---|---|
| `main.py` | `QApplication` (style=Fusion) → `ScreenMain`; handles CLI PDF arg |
| `app/theme.py` | `Theme` dataclass · `ThemeManager` · `THEME_MGR` singleton |
| `app/constants.py` | `group_color(n)` reads THEME_MGR; fixed color constants |
| `app/icons.py` | `draw(p,rect,name,color)` · `sf_font(px,w)` — stroke from THEME_MGR |
| `app/pdf_utils.py` | `clear_layout` · `safe_thumbnail_render` |
| `app/widgets.py` | All reusable thumbnail/card widgets (see Widgets section) |
| `app/screens/main.py` | `ScreenMain` · `DropZone` · `NavButton` · `DrillDownPanel` · `ComingSoonWidget` |
| `app/screens/merge.py` | `ScreenMergeMulti` — split/merge editor |
| `app/screens/viewer.py` | `ScreenViewer` · `PageWidget` · `_ThumbnailPanel` · `_TocPanel` · `_SearchBox` · `PdfViewerTabs` · `_FileTabBar` |
| `app/screens/settings.py` | `ScreenSettings` · `_MiniPreview` — live theme editor (not wired into `ScreenMain` yet) |
| `app/word_editor.py` | `WordEditor` — embedded .docx editor (workspace screen) |
| `app/win_register.py` | `register_as_pdf_viewer()` · `set_title_bar_color()` — Windows-only; no-op elsewhere |
| `theme.json` | Saved theme overrides (created on first save) |
| `window_state.json` | Saved window size |

### Linux packaging (`linux/`)

| File | Purpose |
|---|---|
| `linux/build.sh` | PyInstaller → AppImage / .deb / .rpm |
| `linux/TDTool_linux.spec` | PyInstaller spec (excludes winreg/pywin32) |
| `linux/AppRun` | AppImage entry; sets `LD_LIBRARY_PATH`, `QT_QPA_PLATFORM_PLUGIN_PATH` |
| `linux/tdtool.desktop` | XDG desktop; registers `application/pdf` MIME |

---

## Screen Layout (app/screens/main.py)

No left sidebar. The app starts on one universal drop zone; format is detected
from the dropped file's extension, and the right sidebar becomes a format-aware
tool panel (hidden entirely until a file is loaded).

```
ScreenMain (QWidget)
│
├── _top_gap  QFrame (8px)             — gap below the native title bar, bg_main colored
│
├── _stack  QStackedWidget  (workspace)
│   ├── _drop_zone     DropZone()                 universal — any extension, no filter
│   ├── _viewer_tabs   PdfViewerTabs               browser-style tabs, one per open PDF
│   ├── _merge         ScreenMergeMulti            split/merge editor
│   ├── _word_editor   WordEditor
│   └── _coming_soon   ComingSoonWidget            unsupported formats (label set dynamically)
│
└── _right_sidebar  QFrame  (right, 210px / 62px collapsed; hidden when no file is open)
    ├── _right_toggle_btn "☰  Інструменти"
    └── _right_tool_stack  QStackedWidget
        ├── [0] empty QWidget                      no file loaded
        ├── [1] PDF tools     DrillDownPanel — Переглянути / Розділити-Об'єднати (folder,
        │                     pulls ALL open tab paths into _merge) / Друк документа (folder)
        │                     / Новий файл
        ├── [2] Word tools    just "Новий файл" (WordEditor has its own toolbar)
        └── [3] unsupported   just "Новий файл"
    └── "?" Довідка (always visible, pinned below the tool stack) → _merge._show_help()
```

### File-open dispatch

```python
_on_file_chosen(paths):
  exts = {splitext(p)[1].lower() for p in paths}
  {".pdf"}                    → _open_pdf_tabs(paths)   # 1 or many — always opens as tabs
  {".docx"} and len(paths)==1 → _open_word(paths[0])
  else                        → _open_unsupported(paths[0])

_open_pdf_tabs(paths):
  _current_format='pdf'; _pdf_scenario='viewer'
  _viewer_tabs.reset(); add_tab(p) for each path
  show _viewer_tabs; right_tool_stack→1; right_sidebar.setVisible(True)

_on_pdf_edit():            # "Розділити/Об'єднати PDF" in the right panel
  for p in _viewer_tabs.paths(): if p not in _merge.files: _merge.add_file(p)
  show _merge; _pdf_scenario='editor'

_on_pdf_view():             # "Переглянути" — just switches back, tabs are untouched
  show _viewer_tabs; _pdf_scenario='viewer'

_on_new_file():              # "Новий файл" — also fired by PdfViewerTabs.all_closed
  _merge.reset(); _viewer_tabs.reset(); _current_format='none'
  show _drop_zone; right_tool_stack→0; right_sidebar.setVisible(False)
```

`open_in_viewer(path)` (OS file-association launch from `main.py`) just calls `_open_pdf_tabs([path])`.

### DropZone (universal)

```python
DropZone(
    hint_text     = "Перетягни файл сюди або натисни, щоб вибрати",
    extensions    = None,              # None = accept any extension
    dialog_filter = "Усі файли (*)",
)
# _accepts(path): True if extensions is None, else any(path.lower().endswith(ext) for ext in extensions)
```

### PdfViewerTabs / _FileTabBar (app/screens/viewer.py)

browser-style tabs, one `ScreenViewer` per open PDF. The tab bar is **fully
custom-painted** (`_FileTabBar(QTabBar)`, overrides `paintEvent`/`tabSizeHint`/
mouse events) instead of relying on QSS, because the native Windows style
(`windows11`) mostly ignores stylesheet rules on `QTabBar` — confirmed by
direct comparison: identical QSS rendered correctly in an automated/headless
run but as unstyled native "pill" tabs on a real interactive desktop session.
`main.py` also sets `app.setStyle("Fusion")` as a belt-and-suspenders fallback.

```
PdfViewerTabs (QWidget)
└── _tabs  QTabWidget (documentMode, tabsClosable=False — close glyph is custom-drawn)
    └── tabBar() = _FileTabBar
        ├── real tab × N    one ScreenViewer each (setAcceptDrops(False) — adding
        │                   goes through "+" or the drop zone, not drag-onto-tab)
        └── "+" tab         tabData(idx) == "plus"; always the LAST tab (not a
                             QTabWidget cornerWidget — that left a gap before it)
```

```python
add_tab(path):
  if path already open: setCurrentIndex(that tab); return
  ScreenViewer().load_pdf(path) → insertTab(at plus_index(), viewer, basename)
reset():            remove every tab except the trailing "+" one; viewer.close_doc() each
paths() -> list[str]
current_viewer() -> ScreenViewer | None
all_closed signal:  emitted from _close_tab() when only the "+" tab is left
```

**"+" tab as a real tab, not a corner widget** — `QTabWidget.setCornerWidget`
anchors to the far edge of the whole bar, leaving a gap before it whenever tabs
don't fill the width. Making "+" the actual last tab (`tabData == "plus"`, no
close glyph) keeps it flush against the last document tab. Clicking it
(`_on_current_changed`) reverts `currentIndex` to the previous tab and opens
`QFileDialog.getOpenFileNames`.

**Shrink-to-fit sizing** (`tabSizeHint`) — real tabs split the bar width evenly
(`_PREF_W=200` cap, `_MIN_W=64` floor); recalculated on every `resizeEvent`.

**Custom drag-reorder** (`setMovable(False)` — native QTabBar movable was
replaced entirely for full visual control):
```python
mousePressEvent  → on a tab body: setCurrentIndex(idx); _drag_idx=idx; _press_x=mouse.x
mouseMoveEvent   → _drag_offset = mouse.x - _press_x; _maybe_swap(); _clamp_drag_offset()
_maybe_swap()    → swaps with a neighbor once the dragged tab has covered
                   _SWAP_OVERLAP (0.60) of the neighbor's width.
                   CRITICAL: must adjust _press_x by the same `shift` as
                   _drag_offset after a swap — _drag_offset is recomputed from
                   scratch every move as (mouse.x - _press_x), so leaving
                   _press_x stale made the tab "teleport"/cascade-swap to one
                   end of the bar on the very next move event.
mouseReleaseEvent → clears _drag_idx/_drag_offset (no separate "drop" animation)
```

**Paint order** (`paintEvent`) — non-selected tabs (background + their own
text/close) are painted first, **then** the selected/dragged tab is painted
last as one opaque unit (background bled `±_RADIUS` into neighbors, then its
own text/close). This two-phase order is required: drawing all backgrounds
then all text in a single pass let a neighbor's text — drawn after the
selected tab's background fill — show through on top of it during a drag.

```python
active_bg   = THEME_MGR.get().viewer_bg     # exact match to the page-thumbnail area
                                             # → active tab visually "flows into" the document
inactive_bg = bg_sidebar.lighter(115)       # a step above the bar itself (lighter(115) too)
hover_bg    = bg_sidebar.lighter(140)
```
Brightness ordering matters: inactive/bar must stay clearly *below* `viewer_bg`
or the active tab stops reading as "the highlighted one" (regressed once when
inactive briefly ended up brighter than flat `bg_main`).

`QTabWidget::pane` background is set to `viewer_bg` too (not `bg_main`) so
there's no mismatched sliver between the tab bottom and the actual viewer.
`_FileTabBar.setFixedHeight(_TAB_H)` is required — native styles otherwise
reserve a few px of margin beyond `tabSizeHint`, which left a thin `bar_bg`
line between the tab shapes and the content below.

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

## Word Editor (app/word_editor.py)

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

## Theme System (app/theme.py)

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

Registered listeners: `ScreenMain._apply_theme` (also calls `set_title_bar_color`),
`PdfViewerTabs.apply_theme` (forwards to every open `ScreenViewer` + repaints the tab bar),
`ScreenViewer.apply_theme`, `WordEditor.apply_theme`, `ScreenSettings._sync_from_theme`,
`_MiniPreview.update`.

---

## Viewer (app/screens/viewer.py)

```
ScreenViewer (QWidget)
├── body  QHBoxLayout
│   ├── _side_panel  QWidget (168px, hidden until toggled)
│   │   ├── _side_header   QWidget (44px) — current file name only, no buttons
│   │   └── _side_stack    QStackedWidget
│   │       ├── [0] _thumb_panel  _ThumbnailPanel (QScrollArea)
│   │       └── [1] _toc_panel    _TocPanel (QTreeWidget) — doc.get_toc()
│   └── right  QVBoxLayout                       — sits over the WORK AREA only,
│       ├── _toolbar  QWidget (44px)                NOT above _side_panel
│       │   ├── _thumb_toggle_btn  _ToolbarButton("sidebar", chevron=True)
│       │   │     left-click  → _toggle_thumbnails()         (show/hide thumbnails)
│       │   │     right-click → _show_sidebar_menu()  QMenu  (sidebar mode + page mode)
│       │   ├── zoom_out_btn / _lbl_zoom / zoom_in_btn
│       │   └── _search_box  _SearchBox  (QLineEdit + magnifying-glass icon)
│       ├── _toolbar_divider  QFrame (1px)
│       ├── QScrollArea (_scroll)       bg: viewer_bg
│       │   └── _container QWidget → _vbox QVBoxLayout → PageWidget × N
│       │       (or row-wrapper QWidget × N/2 in "two" page mode — see below)
│       └── _status_bar QWidget (28px)
│           ├── _lbl_file   (stretch 1)    "filename.pdf"
│           ├── _lbl_pages  (52px center)  "3/9"
│           └── _lbl_cursor (130px right)  "x 123.4  y 456.7 pt"
```

`close_doc()` — releases `_doc`/`_pages`, clears `_thumb_panel`/`_toc_panel`/
search state, and closes the fitz handle; called by `PdfViewerTabs` before
deleting a tab's viewer (on close or `reset()`), so the native PDF handle
doesn't leak.

### Sidebar menu (right-click on `_thumb_toggle_btn`)

```
Мініатюри / Зміст         checkable, switch _side_stack content + show panel
Виділення та нотатки /
Закладки / Індексний аркуш   disabled — no backing storage subsystem exists yet
─────────────────────────
Неперервне прокручування / Окрема сторінка / Дві сторінки
                           checkable → _set_page_mode("continuous"|"single"|"two")
```
No "hide sidebar" entry — left-click on the same button already toggles it.

### Page layout modes (`_page_mode`)

```
_rebuild_page_layout()   re-parents existing PageWidgets into _vbox without
                          destroying them:
  "continuous" / "single"   each PageWidget added directly to _vbox
  "two"                     paired into QWidget row wrappers (QHBoxLayout), 2/row
  _apply_page_visibility()  "single" → only _pages[_current_page] visible
                             else     → all visible

_scroll_anchor(i)        the widget whose .pos().y() drives scrolling for
                          page i — the PageWidget itself, or its row wrapper
                          in "two" mode (pw.parentWidget() is not _container)

_go_to_page(i)           "single" → just flips visibility + labels (no scroll)
                          else     → scrolls to _scroll_anchor(i).pos().y()

_update_current_page()   skipped entirely in "single" mode (no meaningful
                          scroll position); dedupes by anchor identity so a
                          "two" mode pair isn't counted twice
```

### PageWidget

```
_render()     fitz.Matrix(scale * dpr) → QImage.setDevicePixelRatio(dpr) → QPixmap
              dpr = devicePixelRatioF() (HiDPI/Retina-sharp; logical widget
              size = pixmap.deviceIndependentSize(), NOT pixmap.size())
              all coordinate math (words/selection/search/cursor) uses
              self._logical_w/_logical_h, never pixmap.width()/height()
_load_words() get_text("words") → (rect, text, block_no, line_no) in screen coords
              block_no/line_no kept for line/paragraph selection grouping

paintEvent:
  drawPixmap
  highlighted words  → fillRect QColor(selection_color, alpha=90)
  rubber-band rect   → QPen(selection_color, alpha=160) + fill alpha=28
  search hits        → fillRect (255,213,0,95); current hit → orange outline+fill

Click counting (_register_click via QElapsedTimer + doubleClickInterval()):
  2 clicks → _select_word()       3 clicks → _select_line() (same block+line)
  4+ clicks → _select_paragraph() (same block_no, all lines, "\n"-joined)
  Qt quirk: the 2nd physical click arrives as mouseDoubleClickEvent (not
  mousePressEvent), so both handlers route through _apply_click_selection().

set_search_highlights(hits_pdf, current_pdf)  — rects stored in PDF-point
  space, re-projected to widget space on every _render() (so they survive zoom)

Ctrl+Wheel / pinch (QEvent.NativeGesture, Qt.ZoomNativeGesture) →
  eventFilter on _scroll.viewport() → _zoom_in/_zoom_out/_apply_scale()
mouseMoveEvent → cursor_moved signal → _lbl_cursor
leaveEvent → cursor_left signal → clears _lbl_cursor
```

### Search (`_run_search` / `_search_*`)

```python
_search_page_ci(page, query):
  # page.search_for() is case-sensitive for non-ASCII (Cyrillic) text —
  # query {query, .lower(), .upper(), .capitalize()} and dedupe by rounded rect
_run_search(query)        → rebuilds _search_results [(page_i, (x0,y0,x1,y1))]
                             jumps to first hit; empty query just clears highlights
_search_next/_prev()      → cyclic _go_to_search_result(idx)
Enter / Shift+Enter in _SearchField → next/prev; Esc → clear
```

### Print

```python
print_document()  → QPrintDialog  → _do_print(printer)
print_preview()   → QPrintPreviewDialog.paintRequested → _do_print(printer)
_do_print()       → QPainter per page; scaled KeepAspectRatio, centered
```

---

## Settings Screen (app/screens/settings.py)

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

## Icons (app/icons.py)

```python
_ICON_NAMES = {scissors, merge, rotate, compress_layers, gear,
               plus_circle, play, arrow_left, arrow_up,
               checkmark, xmark, eye, save, printer,
               sidebar, search}

draw(p, rect, name, color):
  lw = max(1.5, min(rect) * THEME_MGR.get().icon_stroke)
  pen: RoundCap, RoundJoin, SolidLine

# gear is filled (setBrush), not stroked:
#   outer 12-tooth shape  subtracted  3 window sectors + centre hole
#   arcTo convention: arcTo(rect, -deg(a), -deg(span)) = clockwise on screen
```

---

## Editor State (app/screens/merge.py — ScreenMergeMulti)

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
.docx dropped/picked on _drop_zone → _on_file_chosen([path])
  → _open_word(path)
    → unsaved check (only if WordEditor.has_unsaved_changes())
    → _word_editor.open_file(path)
    → show _word_editor; right_tool_stack→2; right_sidebar.setVisible(True)
```

**Open PDF (single or multiple):**
```
.pdf(s) dropped/picked on _drop_zone → _on_file_chosen(paths)
  → _open_pdf_tabs(paths)
    → _viewer_tabs.reset(); _viewer_tabs.add_tab(p) for each path
    → show _viewer_tabs; right_tool_stack→1 (PDF tools); right_sidebar.setVisible(True)

right-panel "+"/drag-drop onto a tab → PdfViewerTabs._on_add_clicked() → QFileDialog → add_tab(p)
right-panel "Розділити/Об'єднати PDF" → _on_pdf_edit() → pulls _viewer_tabs.paths() into _merge
```

**Theme change:**
```
slider/color changed
  → THEME_MGR.update(k=v) → _notify()
      ScreenMain._apply_theme()          bg/top_gap/right_sidebar stylesheets + set_title_bar_color()
      PdfViewerTabs.apply_theme()        pane stylesheet + tab bar repaint + every open ScreenViewer
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

## Constants (app/constants.py)

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

## Widgets (app/widgets.py)

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
PyInstaller:  venv\Scripts\pyinstaller TDTool.spec --clean
              → dist\TDTool\TDTool.exe  (onedir)

Inno Setup:   ISCC.exe installer.iss
              → installer_output\TDTool_Setup_v1.0.exe

win_register.py: runs only when frozen (sys.frozen) on win32
```

### Linux

```
bash linux/build.sh [--appimage] [--deb] [--rpm]   (default: all three)
  → dist_linux/TDTool-1.0.0-x86_64.AppImage
  → dist_linux/tdtool_1.0.0_amd64.deb
  → dist_linux/tdtool-1.0.0-1.x86_64.rpm

AppDir/
├── AppRun    sets LD_LIBRARY_PATH + QT_QPA_PLATFORM_PLUGIN_PATH
├── tdtool.desktop
├── tdtool.png
└── usr/bin/  PyInstaller onedir output
```
