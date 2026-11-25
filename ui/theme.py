STYLESHEET = """
QWidget {
    background-color: #EDEDEA;
    color: #2B2B2B;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
}
QLabel { background: transparent; }
QLabel#title   { font-size: 22px; font-weight: bold; }
QLabel#heading { font-size: 18px; font-weight: bold; }
QLabel#bold    { font-weight: 600; }
QLabel#muted   { color: #6B6B68; font-size: 12px; }
QLabel#error   { color: #A3524A; }
QLabel#success { color: #5B7F5E; }
QLabel#statNumber { font-size: 32px; font-weight: bold; }
QWidget#card {
    background-color: #F5F5F2;
    border: 1px solid #D6D5D0;
    border-radius: 6px;
}

QLineEdit, QTextEdit, QSpinBox, QListWidget, QTableWidget {
    background-color: #F5F5F2;
    border: 1px solid #D6D5D0;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #C9CCD1;
    selection-color: #2B2B2B;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus { border: 1px solid #4A4F57; }
QLineEdit#otp { font-size: 20px; }

QPushButton {
    background-color: #4A4F57;
    color: #F5F5F2;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
}
QPushButton:hover   { background-color: #3A3E45; }
QPushButton:pressed { background-color: #2F3237; }
QPushButton:disabled { background-color: #B9B9B5; color: #EDEDEA; }
QPushButton#secondary {
    background-color: transparent;
    color: #4A4F57;
    border: 1px solid #D6D5D0;
}
QPushButton#secondary:hover { background-color: #E3E3DF; }
QPushButton#secondary:disabled { background-color: transparent; color: #9A9A96; }
QPushButton#trash {
    background: transparent;
    color: #6B6B68;
    border: none;
    padding: 2px 6px;
    font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji";
    font-size: 16px;
}
QPushButton#trash:hover { background: transparent; color: #A3524A; }

QListWidget::item { padding: 8px; }
QListWidget::item:selected { background-color: #DCDCD7; color: #2B2B2B; }
QListWidget#history::item { padding: 0px; }
QWidget#historyRow { background: transparent; }

QTableWidget { gridline-color: #E3E3DF; }
QHeaderView::section {
    background-color: #E3E3DF;
    border: none;
    border-bottom: 1px solid #D6D5D0;
    padding: 6px;
}

QTabWidget::pane { border: 1px solid #D6D5D0; border-radius: 4px; }
QTabBar::tab { background: #E3E3DF; padding: 8px 16px; border: none; }
QTabBar::tab:selected { background: #F5F5F2; }
"""