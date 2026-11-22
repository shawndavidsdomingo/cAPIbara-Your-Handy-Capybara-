import sys
from PySide6.QtWidgets import QApplication

from ui import navigation
from core.db import init_db
from ui.theme import STYLESHEET

if __name__ == "__main__":
    init_db()                        # creates capibara.db on first launch
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    navigation.go_login()
    sys.exit(app.exec())
