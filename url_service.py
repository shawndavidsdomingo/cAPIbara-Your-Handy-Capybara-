"""URL shortening through the Ulvis API, plus link storage (guide section 5).

ALL Ulvis-specific code lives in ulvis_shorten() and its two helpers below, so
the rest of the app never changes if the API does.

What is confirmed (Ulvis GitHub README): GET https://ulvis.net/API/write/get
takes these request parameters: url, custom, type, private, password, uses,
expire, via. No API key. Rate limit reported as 100 requests/hour per IP.

VERIFY on Sprint 2 day 1 (run tools/ulvis_probe.py and paste the raw replies
here): the exact JSON field names for success and for errors, and whether JSON
needs an extra parameter (put it in EXTRA_PARAMS).
"""
import re
from urllib.parse import urlparse

import requests

from db import connection

ULVIS_ENDPOINT = "https://ulvis.net/API/write/get"
ULVIS_HOST = "https://ulvis.net"
EXTRA_PARAMS = {}          # VERIFY: e.g. {"type": "json"} if JSON is not the default
TIMEOUT = 10

MSG_INVALID_URL = "Please enter a full link starting with http:// or https://."
MSG_INVALID_ALIAS = "Alias must be 3-20 letters, numbers or underscores."
MSG_ALIAS_TAKEN = "That alias is already taken. Try another or leave it blank."
MSG_NO_CONNECTION = "Could not reach the shortener. Check your connection."
MSG_TIMEOUT = "The shortener took too long. Try again."
MSG_RATE_LIMIT = "Too many requests. Please wait a moment and try again."
MSG_UNEXPECTED = "The shortener sent an unexpected reply."


class ShortenError(Exception):
    """Message is safe to show to the user."""


# ---------- Validation (runs before any network call) ----------

def is_valid_url(url):
    if not url or re.search(r"\s", url):
        return False
    parts = urlparse(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def is_valid_alias(alias):
    return re.fullmatch(r"[A-Za-z0-9_]{3,20}", alias or "") is not None


# ---------- Ulvis provider ----------

def ulvis_shorten(long_url, alias=None):
    """Return the short URL string, or raise ShortenError."""
    params = {"url": long_url, **EXTRA_PARAMS}
    if alias:
        params["custom"] = alias
    try:
        reply = requests.get(ULVIS_ENDPOINT, params=params, timeout=TIMEOUT)
        if reply.status_code == 429:
            raise ShortenError(MSG_RATE_LIMIT)
        reply.raise_for_status()
        payload = reply.json()
    except ShortenError:
        raise
    except requests.exceptions.Timeout:
        raise ShortenError(MSG_TIMEOUT)
    except requests.exceptions.RequestException:
        raise ShortenError(MSG_NO_CONNECTION)
    except ValueError:
        raise ShortenError(MSG_UNEXPECTED)
    return _read_reply(payload)


def _find_short_url(data):
    """Look for a short link in a string, or in the usual keys of a dict."""
    if isinstance(data, str) and data.startswith(("http://", "https://")):
        return data
    if isinstance(data, dict):
        for key in ("short", "short_url", "shortUrl", "shorturl", "link"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        code = data.get("id")                       # VERIFY: code-only replies
        if isinstance(code, str) and code:
            return f"{ULVIS_HOST}/{code}"
    return None


def _failed(payload):
    error = payload.get("error")
    return (error not in (None, 0, False, "", "0")
            or payload.get("success") is False
            or payload.get("status") in ("error", "fail", "failed"))


def _friendly(text):
    """Turn the service's own error text into one of our messages."""
    t = str(text or "").lower()
    if any(word in t for word in ("rate", "limit", "too many", "flood")):
        return MSG_RATE_LIMIT
    if any(word in t for word in ("custom", "alias", "taken", "exist", "already", "name")):
        return MSG_ALIAS_TAKEN
    if any(word in t for word in ("url", "invalid", "http")):
        return MSG_INVALID_URL
    return MSG_UNEXPECTED


def _read_reply(payload):
    if not isinstance(payload, dict):
        raise ShortenError(MSG_UNEXPECTED)
    data = payload.get("data")
    if _failed(payload):
        text = payload.get("error")
        if text in (None, 0, False, "", "0", True, 1):
            text = payload.get("message") or (data if isinstance(data, str) else "")
        raise ShortenError(_friendly(text))
    short = _find_short_url(data) or _find_short_url(payload)
    if short is None:
        raise ShortenError(MSG_UNEXPECTED)
    return short


# ---------- Storage (every query is scoped to the user) ----------

def save_link(user_id, short_url, original_url, alias=None):
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO links (user_id, short_url, original_url, alias) "
            "VALUES (?, ?, ?, ?)",
            (user_id, short_url, original_url, alias or None))
        return cursor.lastrowid


def get_links(user_id):
    """Newest first, each with its local click count."""
    sql = ("SELECT l.id, l.short_url, l.original_url, l.alias, l.created_at, "
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
