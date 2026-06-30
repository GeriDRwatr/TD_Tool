# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Linux.  Run from the project root:
#   python -m PyInstaller linux/TDTool_linux.spec --noconfirm
import os

ROOT = os.path.dirname(SPECPATH)   # project root  (spec lives in linux/)

excluded = [
    'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
    'PySide6.QtBluetooth', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
    'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtLocation',
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtNfc',
    'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtPositioning',
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D',
    'PySide6.QtQuickWidgets', 'PySide6.QtRemoteObjects', 'PySide6.QtSensors',
    'PySide6.QtSerialPort', 'PySide6.QtSql', 'PySide6.QtStateMachine',
    'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtTest',
    'PySide6.QtUiTools', 'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets', 'PySide6.QtXml',
    'tkinter', '_tkinter',
    'matplotlib', 'numpy', 'scipy', 'PIL', 'cv2',
    'email', 'http', 'urllib', 'xml', 'xmlrpc',
    'unittest', 'doctest', 'pdb',
    # Windows-only — safe to exclude on Linux
    'winreg', 'win32api', 'win32con', 'win32gui',
    'pywin32', 'pywin32_ctypes', 'pywintypes',
    'ctypes.wintypes',
]

# theme.json must be bundled: theme.py resolves it relative to __file__
# window_state.json is created at runtime — not bundled
_datas = []
_theme_json = os.path.join(ROOT, 'theme.json')
if os.path.exists(_theme_json):
    _datas.append((_theme_json, '.'))

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtPrintSupport',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TDTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,   # strip debug symbols — safe on Linux, reduces binary ~30 %
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    name='TDTool',
)
