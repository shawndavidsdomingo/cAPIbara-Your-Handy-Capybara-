"""URL shortening through the Ulvis API, plus link storage (guide section 5).

ALL Ulvis-specific code lives in ulvis_shorten() and the helpers right under
it, so the rest of the app never changes if the API does.

Confirmed (Ulvis GitHub README): GET https://ulvis.net/API/write/get takes the
request parameters url, custom, type, private, password, uses, expire and via.
No API key. We only send `url`.

The reply format is read tolerantly (JSON, plain text or XML): we look for a
ulvis.net short link in the raw reply. If nothing usable is found, the raw
reply is logged as a warning (see the Run console) so it can be checked.
"""
import json
import logging
import re
from urllib.parse import urlparse

import requests

from db import connection

log = logging.getLogger(__name__)

ULVIS_ENDPOINT = "https://ulvis.net/API/write/get"
ULVIS_HOST = "https://ulvis.net"
EXTRA_PARAMS = {}          # e.g. {"type": "json"} if the API ever needs it
TIMEOUT = 10

MSG_INVALID_URL = "Please enter a full link starting with http:// or https://."
MSG_NO_CONNECTION = "Could not reach the shortener. Check your connection."
MSG_TIMEOUT = "The shortener took too long. Try again."
MSG_RATE_LIMIT = "Too many requests. Please wait a moment and try again."
MSG_UNEXPECTED = "The shortener sent an unexpected reply."

# A short link on ulvis.net (page names like /developer.html are not short links)
SHORT_LINK = re.compile(
    r"https?://(?:www\.)?ulvis\.net/"
    r"(?!(?:API|api|developer|multishrink|contact|disclaimer|privacy|browser)\b)"
    r"[A-Za-z0-9_-]+")


class ShortenError(Exception):
    """Message is safe to show to the user."""


# ---------- Validation (runs before any network call) ----------

def is_valid_url(url):
    if not url or re.search(r"\s", url):
        return False
    parts = urlparse(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


# ---------- Ulvis provider ----------

def ulvis_shorten(long_url):
    """Return the short URL string, or raise ShortenError."""
    params = {"url": long_url, **EXTRA_PARAMS}
    try:
        reply = requests.get(ULVIS_ENDPOINT, params=params, timeout=TIMEOUT)
        if reply.status_code == 429:
            raise ShortenError(MSG_RATE_LIMIT)
        reply.raise_for_status()
        text = reply.text
    except ShortenError:
        raise
    except requests.exceptions.Timeout:
        raise ShortenError(MSG_TIMEOUT)
    except requests.exceptions.RequestException:
        raise ShortenError(MSG_NO_CONNECTION)
    return _read_reply(text, long_url)


def _find_short_url(text, long_url):
    """First ulvis.net short link in the reply that is not the original link."""
    original = long_url.rstrip("/")
    for match in SHORT_LINK.finditer(text):
        if match.group(0).rstrip("/") != original:
            return match.group(0)
    return None


def _error_text(payload):
    """Pull a message out of a JSON error reply (any of the usual shapes)."""
    if not isinstance(payload, dict):
        return ""
    for key in ("error", "message", "msg", "data"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            for inner in ("msg", "message", "error"):
                if isinstance(value.get(inner), str) and value[inner]:
                    return value[inner]
    return ""


def _friendly(text):
    t = str(text or "").lower()
    if any(word in t for word in ("rate", "limit", "too many", "flood")):
        return MSG_RATE_LIMIT
    if any(word in t for word in ("url", "invalid", "http")):
        return MSG_INVALID_URL
    return MSG_UNEXPECTED


def _read_reply(text, long_url):
    text = (text or "").replace("\\/", "/")          # PHP escapes slashes in JSON
    short = _find_short_url(text, long_url)
    if short:
        return short

    try:
        payload = json.loads(text)
    except ValueError:
        payload = None

    message = _error_text(payload)
    if message:
        raise ShortenError(_friendly(message))

    # Some replies give only a code: {"data": {"id": "abc123"}}
    data = payload.get("data") if isinstance(payload, dict) else None
    code = data.get("id") if isinstance(data, dict) else None
    if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]+", code):
        return f"{ULVIS_HOST}/{code}"

    log.warning("Unexpected Ulvis reply: %.500s", text)
    raise ShortenError(MSG_UNEXPECTED)


# ---------- Storage (every query is scoped to the user) ----------

def save_link(user_id, short_url, original_url):
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO links (user_id, short_url, original_url) VALUES (?, ?, ?)",
            (user_id, short_url, original_url))
        return cursor.lastrowid


def get_links(user_id):
    """Newest first, each with its local click count."""
    sql = ("SELECT l.id, l.short_url, l.original_url, l.created_at, "
           "COUNT(c.id) AS clicks "
           "FROM links l LEFT JOIN link_clicks c ON c.link_id = l.id "
           "WHERE l.user_id = ? GROUP BY l.id ORDER BY l.id DESC")
    with connection() as conn:
        return [dict(row) for row in conn.execute(sql, (user_id,)).fetchall()]


def delete_link(user_id, link_id):
    """Clicks go too (ON DELETE CASCADE). Returns True if a row was deleted."""
    with connection() as conn:
        cursor = conn.execute("DELETE FROM links WHERE id = ? AND user_id = ?",
                              (link_id, user_id))
        return cursor.rowcount > 0


def record_click(user_id, link_id):
    """Log one local click, only if the link belongs to this user."""
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO link_clicks (link_id) "
            "SELECT id FROM links WHERE id = ? AND user_id = ?",
            (link_id, user_id))
        return cursor.rowcount > 0
