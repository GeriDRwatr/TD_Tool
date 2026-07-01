import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtWidgets


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
