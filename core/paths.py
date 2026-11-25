import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_folder():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return PROJECT_ROOT


def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", PROJECT_ROOT)
    return os.path.join(base, *parts)