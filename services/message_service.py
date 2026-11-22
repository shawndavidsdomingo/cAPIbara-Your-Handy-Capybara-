"""Email sending through Brevo, and message storage (guide section 6).

Every Brevo detail lives here, so the rest of the app only sees a message id
or a SendError with a readable message.

How sending works
- POST https://api.brevo.com/v3/smtp/email with the API key in the `api-key`
  header. Success is HTTP 201 and a JSON body {"messageId": "..."}.
- The app has ONE sender address (SENDER_EMAIL in .env, on the authenticated
  domain capibara-shawn-neo.online). When a signed-in user writes an email,
  their own address goes in Reply-To so replies reach them.
- Every email is sent as plain text plus a small HTML version with the cAPIbara
  header. If LOGO_URL (a public https link) is set, the header is that picture.
- The API key comes from .env / the environment (see config.py). It is never
  logged and never committed.

Storage: the `messages` table (kind SMS or Email, status DRAFT or SENT). Every
query is scoped to the user's id.
"""
import html
import logging

import requests

from core import config
from services.auth_service import is_valid_email
from core.db import connection

log = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
TIMEOUT = 10

MSG_NOT_CONFIGURED = "Email sending is not set up. Add BREVO_API_KEY to the .env file."
MSG_BAD_RECIPIENT = "Please enter a valid email address."
MSG_NO_SUBJECT = "Please enter a subject."
MSG_NO_BODY = "Please write a message."
MSG_NO_CONNECTION = "Could not reach the email service. Check your connection."
MSG_TIMEOUT = "The email service took too long. Try again."
MSG_REFUSED = ("The email service refused the request. "
               "Check the Brevo API key and its authorized IP addresses.")
MSG_REJECTED = "The email service could not accept this message. Check the address and try again."
MSG_RATE_LIMIT = "Too many emails. Please wait a moment and try again."
MSG_SERVER = "The email service is having problems. Try again later."
MSG_UNEXPECTED = "The email service sent an unexpected reply."


class SendError(Exception):
    """Message is safe to show to the user."""


# ---------- Email provider (Brevo) ----------

def email_enabled():
    """True when an API key is set. Without one the app stays in demo mode."""
    return bool(config.get("BREVO_API_KEY"))


def logo_url():
    """The configured logo link, or '' if it is missing or not a public https link."""
    url = config.get("LOGO_URL")
    if url and not url.lower().startswith("https://"):
        log.warning("LOGO_URL ignored: it must start with https://")
        return ""
    return url


def build_html(body):
    """The HTML version of an email: a small header (logo + name), the
    message, and a quiet footer. Everything the user typed is escaped, so it can
    never inject markup. It uses no page background, so it sits cleanly on
    Gmail's white (or dark) reading pane."""
    logo = logo_url()
    name = ('<span style="font-size:17px;font-weight:600;color:#2B2B2B">cAPIbara</span><br>'
            '<span style="font-size:12px;color:#6B6B68">Your Handy Capybara</span>')
    if logo:
        header = (
            '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="padding-right:12px"><img src="{html.escape(logo, quote=True)}" '
            'alt="cAPIbara" width="56" height="56" '
            'style="display:block;width:56px;height:56px;border-radius:12px;border:0"></td>'
            f'<td style="vertical-align:middle;line-height:1.3">{name}</td>'
            '</tr></table>')
    else:
        header = f'<div style="line-height:1.3">{name}</div>'
    text = html.escape(body).replace("\r\n", "\n").replace("\n", "<br>")
    return (
        '<!DOCTYPE html><html><body style="margin:0;padding:0">'
        '<div style="max-width:520px;margin:0;padding:20px 4px;'
        'font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#2B2B2B">'
        f'<div style="padding-bottom:18px;border-bottom:1px solid #E3E3DF">{header}</div>'
        f'<div style="padding:22px 0;font-size:15px;line-height:1.6">{text}</div>'
        '<div style="padding-top:14px;border-top:1px solid #E3E3DF;'
        'font-size:12px;color:#8A8A86">Sent with cAPIbara</div>'
        '</div></body></html>'
    )


def send_email(to, subject, body, reply_to=None):
    """Send an email. Returns Brevo's message id, or raises SendError.

    reply_to is an optional (email, name) pair.
    """
    to, subject, body = to.strip(), subject.strip(), body.strip()
    if not is_valid_email(to):
        raise SendError(MSG_BAD_RECIPIENT)
    if not subject:
        raise SendError(MSG_NO_SUBJECT)
    if not body:
        raise SendError(MSG_NO_BODY)
    api_key = config.get("BREVO_API_KEY")
    if not api_key:
        raise SendError(MSG_NOT_CONFIGURED)

    payload = {
        "sender": {"name": config.get("SENDER_NAME"), "email": config.get("SENDER_EMAIL")},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
        "htmlContent": build_html(body),
    }
    if reply_to:
        address, name = reply_to
        payload["replyTo"] = {"email": address, **({"name": name} if name else {})}

    try:
        reply = requests.post(
            BREVO_ENDPOINT, json=payload, timeout=TIMEOUT,
            headers={"api-key": api_key, "accept": "application/json"})
    except requests.exceptions.Timeout:
        raise SendError(MSG_TIMEOUT)
    except requests.exceptions.RequestException:
        raise SendError(MSG_NO_CONNECTION)

    if reply.status_code in (200, 201, 202):
        return _message_id(reply)

    log.warning("Brevo error %s: %.300s", reply.status_code, reply.text)
    raise SendError(_friendly(reply.status_code))


def _message_id(reply):
    try:
        return reply.json().get("messageId", "")
    except (ValueError, AttributeError):
        return ""


def _friendly(status):
    if status == 400:
        return MSG_REJECTED
    if status in (401, 403):
        return MSG_REFUSED
    if status == 429:
        return MSG_RATE_LIMIT
    if status >= 500:
        return MSG_SERVER
    return MSG_UNEXPECTED


def send_otp_email(to, code):
    """The verification code email used by registration and profile changes."""
    body = (f"Your cAPIbara verification code is {code}.\n\n"
            "Enter it in the app to confirm your email address.\n"
            "Never share this code with anyone. If you did not ask for it, "
            "you can ignore this message.")
    return send_email(to, "Your cAPIbara verification code", body)


# ---------- Storage (drafts and sent messages) ----------
# SMS rows keep the number in `recipient`, the text in `body`, and no subject.

_COLUMNS = "id, recipient, subject, body, created_at, sent_at"


def save_draft(user_id, kind, recipient, subject, body):
    """Store a new draft and return its id."""
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (user_id, kind, recipient, subject, body, status) "
            "VALUES (?, ?, ?, ?, ?, 'DRAFT')",
            (user_id, kind, recipient, subject, body))
        return cursor.lastrowid


def update_draft(user_id, message_id, recipient, subject, body):
    """Overwrite a draft (its saved time moves to now). True if it was found."""
    with connection() as conn:
        cursor = conn.execute(
            "UPDATE messages SET recipient = ?, subject = ?, body = ?, "
            "created_at = datetime('now') "
            "WHERE id = ? AND user_id = ? AND status = 'DRAFT'",
            (recipient, subject, body, message_id, user_id))
        return cursor.rowcount > 0


def delete_draft(user_id, message_id):
    with connection() as conn:
        cursor = conn.execute(
            "DELETE FROM messages WHERE id = ? AND user_id = ? AND status = 'DRAFT'",
            (message_id, user_id))
        return cursor.rowcount > 0


def get_drafts(user_id, kind):
    """The user's drafts of one kind, oldest first."""
    with connection() as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM messages "
            "WHERE user_id = ? AND kind = ? AND status = 'DRAFT' ORDER BY id",
            (user_id, kind)).fetchall()
    return [dict(row) for row in rows]


def record_sent(user_id, kind, recipient, subject, body, draft_id=None):
    """Store a sent message and return its id. If it came from a draft, that
    draft is removed in the same transaction."""
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (user_id, kind, recipient, subject, body, status, sent_at) "
            "VALUES (?, ?, ?, ?, ?, 'SENT', datetime('now'))",
            (user_id, kind, recipient, subject, body))
        if draft_id is not None:
            conn.execute(
                "DELETE FROM messages WHERE id = ? AND user_id = ? AND status = 'DRAFT'",
                (draft_id, user_id))
        return cursor.lastrowid


def get_sent(user_id, kind):
    """The user's sent messages of one kind, newest first."""
    with connection() as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM messages "
            "WHERE user_id = ? AND kind = ? AND status = 'SENT' "
            "ORDER BY sent_at DESC, id DESC",
            (user_id, kind)).fetchall()
    return [dict(row) for row in rows]