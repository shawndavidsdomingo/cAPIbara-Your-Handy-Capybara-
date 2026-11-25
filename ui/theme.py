"""The look of the whole app: a warm, minimal brown palette.

Change a colour once in COLORS and every screen follows. Code that needs a
colour outside the stylesheet (a spinner, a status message) imports COLORS from
here instead of typing its own hex value.
"""
import re
from string import Template

from core import zoom

COLORS = {
    "bg": "#F7F3EE",              # window background (warm off-white)
    "surface": "#FDFBF8",         # cards, inputs, tables
    "border": "#E2D8CC",
    "border_strong": "#CDBFB1",   # hover / disabled outlines
    "text": "#3B2F2A",            # dark espresso
    "muted": "#7D6E63",
    "primary": "#6F4E37",         # coffee brown (main buttons, focus, accents)
    "primary_hover": "#5C402C",
    "primary_pressed": "#4A3323",
    "on_primary": "#FBF8F4",
    "soft": "#EFE6DB",            # hover background
    "selected": "#E6D8C8",        # selected rows and menu items
    "disabled": "#CDBFB1",
    "error": "#A3453A",
    "success": "#5E7A4F",
}

# One colour per kind of activity (dashboard charts). Warm browns plus one soft green.
CHART_COLORS = {
    "emails": "#6F4E37",     # coffee
    "sms":    "#B98A5E",     # caramel
    "links":  "#8A9A78",     # sage
    "gens":   "#D9C3A5",     # latte
}

_TEMPLATE = Template("""
QWidget {
    background-color: $bg;
    color: $text;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
}
QLabel, QCheckBox { background: transparent; }
QToolTip {
    background-color: $text;
    color: $on_primary;
    border: none;
    padding: 4px 8px;
}

/* ---------- Text styles (set with objectName) ---------- */
QLabel#title      { font-size: 24px; font-weight: 600; }
QLabel#heading    { font-size: 18px; font-weight: 600; }
QLabel#bold       { font-weight: 600; }
QLabel#muted      { color: $muted; font-size: 12px; }
QLabel#error      { color: $error; }
QLabel#success    { color: $success; }
QLabel#link       { color: $primary; }
QLabel#successBadge {
    background-color: $success;
    color: $on_primary;
    border-radius: 22px;
    font-size: 22px;
    font-weight: 700;
}
QLabel#fieldLabel { font-size: 12px; font-weight: 600; color: $muted; }
QLabel#statNumber { font-size: 34px; font-weight: 600; color: $primary; }

/* ---------- Cards and dividers ---------- */
QFrame#divider { background-color: $border; border: none; }
QWidget#card {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 10px;
}

/* ---------- Inputs ---------- */
QLineEdit, QTextEdit {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: $selected;
    selection-color: $text;
}
QLineEdit:hover, QTextEdit:hover {
    border: 1px solid $border_strong;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid $primary;
}
/* QSpinBox keeps Qt's own look so its up/down arrows stay visible */
QLineEdit:read-only { background-color: $bg; color: $muted; }
QLineEdit#otp { font-size: 20px; }

/* ---------- Buttons ---------- */
QPushButton {
    background-color: $primary;
    color: $on_primary;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
    font-weight: 600;
}
QPushButton:hover    { background-color: $primary_hover; }
QPushButton:pressed  { background-color: $primary_pressed; }
QPushButton:disabled { background-color: $disabled; color: $bg; }

QPushButton#secondary {
    background-color: transparent;
    color: $primary;
    border: 1px solid $border_strong;
    font-weight: 500;
}
QPushButton#secondary:hover    { background-color: $soft; }
QPushButton#secondary:pressed  { background-color: $selected; }
QPushButton#secondary:disabled { background-color: transparent; color: $disabled; border-color: $border; }

/* Segmented control: joined buttons, one selected (Gender, Export as) */
QPushButton#segment {
    background-color: transparent;
    color: $muted;
    border: 1px solid $border_strong;
    border-radius: 0px;
    padding: 7px 14px;
    font-weight: 500;
}
QPushButton#segment[edge="first"], QPushButton#segment[edge="only"] {
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
}
QPushButton#segment[edge="last"], QPushButton#segment[edge="only"] {
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QPushButton#segment[edge="middle"], QPushButton#segment[edge="last"] { border-left-width: 0px; }
QPushButton#segment:hover:!checked { background-color: $soft; color: $text; }
QPushButton#segment:checked {
    background-color: $primary;
    color: $on_primary;
    border: 1px solid $primary;
    font-weight: 600;
}

QPushButton#trash {
    background: transparent;
    color: $muted;
    border: none;
    padding: 2px 6px;
    font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji";
    font-size: 16px;
}
QPushButton#trash:hover { background: transparent; color: $error; }

/* ---------- Check boxes and group boxes ---------- */
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $border_strong;
    border-radius: 4px;
    background-color: $surface;
}
QCheckBox::indicator:hover   { border: 1px solid $primary; }
QCheckBox::indicator:checked { background-color: $primary; border: 1px solid $primary; }

QGroupBox {
    border: 1px solid $border;
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 10px 8px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: $primary;
}

/* ---------- Lists (sidebar menu, drafts, history) ---------- */
QListWidget {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QListWidget::item { padding: 9px 10px; border-radius: 6px; }
QListWidget::item:hover    { background-color: $soft; }
QListWidget::item:selected { background-color: $selected; color: $text; }
QListWidget#history { background: transparent; border: none; padding: 0px; }
QListWidget#history::item  { padding: 0px; }

/* Main window sidebar and its menu */
QWidget#sidebar { background-color: $surface; border-right: 1px solid $border; }
QListWidget#menu { background: transparent; border: none; padding: 0px; }
QListWidget#menu::item { padding: 11px 14px; margin: 2px 0px; }
QListWidget#menu::item:selected { background-color: $selected; color: $primary; }
QWidget#historyRow { background: transparent; }

/* ---------- Tables ---------- */
QTableWidget {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    gridline-color: $border;
    selection-background-color: $selected;
    selection-color: $text;
    outline: none;
}
QHeaderView::section {
    background-color: $bg;
    color: $muted;
    border: none;
    border-bottom: 1px solid $border;
    padding: 8px 6px;
    font-weight: 600;
}

/* ---------- Tabs: a quiet underline on the active one ---------- */
QTabWidget::pane {
    border: 1px solid $border;
    border-radius: 8px;
    top: -1px;
}
QTabBar { background: transparent; }
QTabWidget#pageTabs::pane { border: none; border-top: 1px solid $border; border-radius: 0; }
QTabWidget#inner::pane    { border: none; border-top: 1px solid $border; border-radius: 0; }
QTabWidget#inner QStackedWidget { background: transparent; }
QWidget#clear { background: transparent; }
QListWidget#plainList { background: transparent; border: none; }
QTabBar::tab {
    background: transparent;
    color: $muted;
    padding: 9px 20px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover    { color: $text; }
QTabBar::tab:selected { color: $primary; border-bottom: 2px solid $primary; font-weight: 600; }

/* ---------- Scroll bars: thin and calm ---------- */
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical   { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: $border_strong;
    border-radius: 5px;
    min-height: 28px;
    min-width: 28px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: $muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---------- Message boxes ---------- */
QMessageBox QPushButton { min-width: 72px; }
""")

def scale_px(css, factor):
    """Multiply every 'Npx' in a stylesheet by the zoom. 1px lines stay thin."""
    def one(match):
        size = int(match.group(1))
        return f"{size if size <= 1 else round(size * factor)}px"
    return re.sub(r"(\d+)px", one, css)


def build_stylesheet(factor=None):
    """The whole stylesheet at a zoom (the current one if none is given)."""
    factor = zoom.factor() if factor is None else factor
    return scale_px(_TEMPLATE.substitute(COLORS), factor)


STYLESHEET = build_stylesheet()