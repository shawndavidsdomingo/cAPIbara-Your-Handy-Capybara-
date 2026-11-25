import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui import navigation
from core.db import init_db
from ui.theme import STYLESHEET
from ui.widgets import ICON_PATH

if __name__ == "__main__":
    init_db()                                   # creates capibara.db on first launch
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(ICON_PATH))      # every window and the taskbar use the logo
    app.setStyleSheet(STYLESHEET)
    navigation.go_login()
    sys.exit(app.exec())