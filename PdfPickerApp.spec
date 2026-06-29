# -*- mode: python ; coding: utf-8 -*-

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
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('app/theme.json', 'app')],
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
    name='PdfPickerApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
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
    strip=False,
    upx=False,
    name='PdfPickerApp',
)
