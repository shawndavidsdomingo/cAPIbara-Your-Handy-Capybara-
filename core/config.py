"""Settings and secrets, read from environment variables or a .env file."""
import os

from core.paths import app_folder, resource_path

ENV_PATH = os.path.join(app_folder(), ".env")
BUNDLED_ENV_PATH = resource_path(".env")

DEFAULTS = {
    "SENDER_EMAIL": "noreply@capibara-shawn-neo.online",   # address the app sends from
    "SENDER_NAME": "cAPIbara",
    "LOGO_URL": "",    # logo shown
    "TEXTBEE_BASE_URL": "https://api.textbee.dev/api/v1",
    "TEXTBEE_DEVICE_ID": "",   # which phone send TextBee device
}


def parse_env(text):
    """KEY=VALUE lines -> dict."""
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
    return (os.environ.get(name) or DEFAULTS.get(name, "")).strip()


load_env()
load_env(BUNDLED_ENV_PATH)