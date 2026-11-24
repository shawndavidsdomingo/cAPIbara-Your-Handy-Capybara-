"""Settings and secrets, read from environment variables or a .env file.

The .env file sits next to the app (the project's top folder, or the .exe) and is NEVER committed (it is in
.gitignore). Copy .env.example to .env and fill in your own values.
Values already set in the real environment win over the file. When the app is
packaged with `--add-data ".env;."`, a copy of .env travels inside it (anyone with
the app folder can read it, so only share the build with people you trust).
"""
import os

from core.paths import app_folder, resource_path

ENV_PATH = os.path.join(app_folder(), ".env")             # next to the app: wins if present
BUNDLED_ENV_PATH = resource_path(".env")                    # copy packed inside the .exe by PyInstaller

DEFAULTS = {
    "SENDER_EMAIL": "noreply@capibara-shawn-neo.online",   # the one address the app sends from
    "SENDER_NAME": "cAPIbara",
    "LOGO_URL": "",    # public https link to the logo shown at the top of every email
}


def parse_env(text):
    """KEY=VALUE lines -> dict. Blank lines and # comments are skipped."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_env(path=ENV_PATH):
    try:
        with open(path, encoding="utf-8") as file:
            values = parse_env(file.read())
    except OSError:                       # no .env file: that is fine
        return
    for key, value in values.items():
        os.environ.setdefault(key, value)


def get(name):
    """A setting, read at call time. Falls back to DEFAULTS, then to ''."""
    return (os.environ.get(name) or DEFAULTS.get(name, "")).strip()


load_env()                      # a .env next to the app wins...
load_env(BUNDLED_ENV_PATH)      # ...otherwise the one packed inside it is used