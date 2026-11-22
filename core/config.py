"""Settings and secrets, read from environment variables or a .env file.

The .env file sits in the project's top folder and is NEVER committed (it is in
.gitignore). Copy .env.example to .env and fill in your own values.
Values already set in the real environment win over the file.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

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


load_env()