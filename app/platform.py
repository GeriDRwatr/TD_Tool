import logging
import sys

_log = logging.getLogger(__name__)

_SHCNE_ASSOCCHANGED = 0x08000000
_SHCNF_IDLIST        = 0x0000
_DWMWA_CAPTION_COLOR = 35


def register_as_pdf_viewer() -> None:
    """
    Register TDTool in HKCU so it appears in the Windows
    'Open with' context menu for .pdf files.
    Runs silently; errors are swallowed so the app always starts.
    Only active when running as a frozen .exe (PyInstaller build).
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import winreg
        exe      = sys.executable
        prog_id  = "TDTool.PDF"
        open_cmd = f'"{exe}" "%1"'
        cu       = winreg.HKEY_CURRENT_USER

        def _set(subkey, name="", value=None, regtype=winreg.REG_SZ):
            with winreg.CreateKey(cu, subkey) as k:
                if value is not None:
                    winreg.SetValueEx(k, name, 0, regtype, value)

        _set(rf"Software\Classes\{prog_id}",
             "", "PDF Document")
        _set(rf"Software\Classes\{prog_id}\DefaultIcon",
             "", f"{exe},0")
        _set(rf"Software\Classes\{prog_id}\shell\open",
             "FriendlyAppName", "TDTool")
        _set(rf"Software\Classes\{prog_id}\shell\open\command",
             "", open_cmd)
        _set(r"Software\Classes\.pdf\OpenWithProgids",
             prog_id, b"", winreg.REG_NONE)
        _set(r"Software\TDTool\Capabilities",
             "ApplicationName", "TDTool")
        _set(r"Software\TDTool\Capabilities",
             "ApplicationDescription", "PDF Viewer & Editor")
        _set(r"Software\TDTool\Capabilities\FileAssociations",
             ".pdf", prog_id)
        _set(r"Software\RegisteredApplications",
             "TDTool", r"Software\TDTool\Capabilities")

        # Notify the shell so the change appears immediately
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(
            _SHCNE_ASSOCCHANGED, _SHCNF_IDLIST, None, None
        )
    except Exception:
        _log.debug("Не вдалося зареєструвати PDF-асоціацію", exc_info=True)


def set_title_bar_color(widget, hex_color: str) -> None:
    """
    Tint the native window title bar to match the app's theme background.
    Windows 11 22H2+ only (DWM caption-color attribute); silently no-ops
    on older Windows, other platforms, or any failure.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        colorref = r | (g << 8) | (b << 16)   # COLORREF is 0x00BBGGRR
        value = ctypes.c_int(colorref)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_CAPTION_COLOR, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        _log.debug("Не вдалося зафарбувати тайтлбар", exc_info=True)
