import os
import sys
import fitz
from PySide6 import QtWidgets

fitz.TOOLS.mupdf_display_errors(False)

from app.win_register import register_as_pdf_viewer
from app.screens.main import ScreenMain
from app.icons import sf_font


def main():
    register_as_pdf_viewer()
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(sf_font(13))
    w = ScreenMain()
    w.show()

    # Open PDF passed as command-line argument (e.g. from Windows file association)
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isfile(path) and path.lower().endswith(".pdf"):
            w.open_in_viewer(path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
