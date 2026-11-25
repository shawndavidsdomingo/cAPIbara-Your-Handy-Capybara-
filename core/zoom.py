"""Zoom: how big the whole app is drawn, for people who find it hard to read.

The level is a percentage picked from LEVELS and is remembered between launches
in settings.json, next to the app (the same place as capibara.db and .env). It
belongs to the computer, not to an account, so the Login window is already the
right size before anyone signs in.

- px(n)   scales a pixel size written in the code (a fixed width, a logo height).
- theme.py scales every "12px" in the stylesheet the same way.
- navigation.set_zoom() changes the level and redraws the window on screen.
"""
import json
import os

from core.paths import app_folder

LEVELS = (90, 100, 110, 125, 150, 175, 200)
DEFAULT = 100
SETTINGS_PATH = os.path.join(app_folder(), "settings.json")

_level = DEFAULT


def _load():
    global _level
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as file:
            value = json.load(file).get("zoom", DEFAULT)
    except (OSError, ValueError, AttributeError):    # no file, or not readable: default
        return
    _level = value if value in LEVELS else DEFAULT


def _save():
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as file:
            json.dump({"zoom": _level}, file)
    except OSError:                                  # a read-only folder: just not remembered
        pass


def level():
    """The zoom as a percentage, e.g. 125."""
    return _level


def factor():
    """The zoom as a multiplier, e.g. 1.25."""
    return _level / 100


def px(size):
    """A pixel size from the code, scaled to the current zoom."""
    return max(1, round(size * factor())) if size > 0 else 0


def step(direction):
    """The next level up (+1) or down (-1), or None at the end of the range."""
    index = LEVELS.index(_level) + direction
    return LEVELS[index] if 0 <= index < len(LEVELS) else None


def shifted(steps):
    """The level `steps` places up (+) or down (-) from now, kept inside LEVELS."""
    index = LEVELS.index(_level) + steps
    return LEVELS[max(0, min(len(LEVELS) - 1, index))]


def set_level(new_level):
    global _level
    _level = new_level if new_level in LEVELS else DEFAULT
    _save()


_load()