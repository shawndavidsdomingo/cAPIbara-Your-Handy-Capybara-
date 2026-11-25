"""Where things live, both when run from source and when packaged with PyInstaller.

- app_folder(): where the database (capibara.db) and the settings file (.env) are.
  From source it is the project's top folder. Packaged, it is the folder that
  holds cAPIbara.exe, so your data survives rebuilds and is never hidden or temporary.
- resource_path(): read-only files bundled inside the app (the logo images).
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_folder():
    if getattr(sys, "frozen", False):                  # running as the packaged .exe
        return os.path.dirname(sys.executable)
    return PROJECT_ROOT


def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", PROJECT_ROOT)      # PyInstaller's bundle folder
    return os.path.join(base, *parts)