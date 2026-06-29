import sys


def register_as_pdf_viewer() -> None:
    """
    Register PdfPickerApp in HKCU so it appears in the Windows
    'Open with' context menu for .pdf files.
    Runs silently; errors are swallowed so the app always starts.
    Only active when running as a frozen .exe (PyInstaller build).
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import winreg
        exe      = sys.executable
        prog_id  = "PdfPickerApp.PDF"
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
             "FriendlyAppName", "PdfPickerApp")
        _set(rf"Software\Classes\{prog_id}\shell\open\command",
             "", open_cmd)
        _set(rf"Software\Classes\.pdf\OpenWithProgids",
             prog_id, b"", winreg.REG_NONE)
        _set(r"Software\PdfPickerApp\Capabilities",
             "ApplicationName", "PdfPickerApp")
        _set(r"Software\PdfPickerApp\Capabilities",
             "ApplicationDescription", "PDF Viewer & Editor")
        _set(r"Software\PdfPickerApp\Capabilities\FileAssociations",
             ".pdf", prog_id)
        _set(r"Software\RegisteredApplications",
             "PdfPickerApp", r"Software\PdfPickerApp\Capabilities")

        # Notify the shell so the change appears immediately
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass
