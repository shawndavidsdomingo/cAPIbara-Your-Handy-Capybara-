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
  header. The sender's own spacing (indents, blank lines) is kept in both, and a
  signed-in user's email ends with "Sent from <registered name> <registered email>". If LOGO_URL (a public https link) is set, the header is that picture.
- The API key comes from .env / the environment (see config.py). It is never
  logged and never committed.

SMS goes through TextBee (https://textbee.dev), which sends the text from your
own Android phone running the TextBee app.
- POST {TEXTBEE_BASE_URL}/gateway/send-sms with the key in the `x-api-key`
  header and a JSON body {"recipients": ["+639..."], "message": "..."}.
  An optional TEXTBEE_DEVICE_ID picks the phone (otherwise your default device).
- HTTP 200 means TextBee QUEUED the message (not that it was delivered). The
  reply is {"data": {"success": true, "smsBatchId": "...", ...}}.
- The app takes Philippine numbers as 09XXXXXXXXX and sends them as +639XXXXXXXXX.
- TEXTBEE_API_KEY comes from .env / the environment, like the Brevo key.
  Without it the SMS tab stays in demo mode (nothing leaves the app).

Storage: the `messages` table (kind SMS or Email, status DRAFT or SENT). Every
query is scoped to the user's id.
"""
import html
import logging
import re
import time

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


MSG_BAD_NUMBER = "Enter a Philippine mobile number like 09XXXXXXXXX."
MSG_NO_SMS_TEXT = "Please write a message."
MSG_SMS_NOT_CONFIGURED = "SMS sending is not set up. Add TEXTBEE_API_KEY to the .env file."
MSG_SMS_NO_CONNECTION = "Could not reach the SMS service. Check your connection."
MSG_SMS_TIMEOUT = "The SMS service took too long. Try again."
MSG_SMS_REFUSED = "The SMS service refused the API key. Check TEXTBEE_API_KEY in the .env file."
MSG_SMS_NO_DEVICE = ("TextBee could not use your phone. Make sure the TextBee app is "
                     "online and the device is enabled.")
MSG_SMS_DEVICE_UNKNOWN = "TextBee does not know that device. Check TEXTBEE_DEVICE_ID in the .env file."
MSG_SMS_REJECTED = "The SMS service could not accept this message. Check the number and try again."
MSG_SMS_LIMIT = "The TextBee sending limit was reached. Try again later."
MSG_SMS_SERVER = "The SMS service is having problems. Try again later."
MSG_SMS_UNEXPECTED = "The SMS service sent an unexpected reply."

MSG_SMS_PHONE_FAILED = ("The phone could not send the text. Check its signal, load and SIM, "
                        "then try again.")
# TextBee errorCode -> what to tell the user (anything else shows TextBee's own text)
SMS_ERROR_CODES = {
    "2": "The phone's radio is off (airplane mode?). Turn it off and try again.",
    "4": "The phone has no mobile service. Check its signal and try again.",
    "5": "Android's per-app text limit was reached. Wait a while and try again.",
    "17": "The phone had a network error. Try again in a moment.",
}

SMS_WAIT = 20                 # seconds to wait for the phone to report its result
SMS_POLL = 2                  # seconds between checks
MAX_SEND_SECONDS = SMS_WAIT + TIMEOUT * 2     # the longest a send can take (see msg_page.shutdown)
SMS_FAILED = ("failed", "delivery_failed")
SMS_SENT = ("sent", "delivered")

PH_MOBILE = re.compile(r"09\d{9}")


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


def _keep_spacing(text):
    """HTML squeezes spaces and ignores tabs. Turn the user's indents and runs of
    spaces into non-breaking spaces so the email looks the way it was typed."""
    text = text.replace("\t", "    ")
    text = re.sub(r"(?m)^ ", "&nbsp;", text)               # a space at the start of a line
    return re.sub(r" {2,}", lambda m: " " + "&nbsp;" * (len(m.group(0)) - 1), text)


def sender_line(email, name=""):
    """Plain text for the footer: Sent from Juan Cruz <juan@example.com>."""
    return f"Sent from {name} <{email}>" if name else f"Sent from {email}"


def build_html(body, sent_from=None, sent_name=""):
    """The HTML version of an email: a small header (logo + name), the
    message, and a quiet footer ("Sent from Name <email>" when the sender is known).
    Everything the user typed is escaped, so it can never inject markup. It uses no page background, so it sits cleanly on
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
    text = html.escape(body).replace("\r\n", "\n")
    text = _keep_spacing(text).replace("\n", "<br>")
    if sent_from:
        who = f"{html.escape(sent_name)} " if sent_name else ""
        address = html.escape(sent_from, quote=True)
        footer = (f'Sent from {who}&lt;<a href="mailto:{address}" '
                  f'style="color:#8A8A86;text-decoration:none">{address}</a>&gt;')
    else:
        footer = "Sent with cAPIbara"
    return (
        '<!DOCTYPE html><html><body style="margin:0;padding:0">'
        '<div style="max-width:520px;margin:0;padding:20px 4px;'
        'font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#2B2B2B">'
        f'<div style="padding-bottom:18px;border-bottom:1px solid #E3E3DF">{header}</div>'
        f'<div style="padding:22px 0;font-size:15px;line-height:1.6">{text}</div>'
        '<div style="padding-top:14px;border-top:1px solid #E3E3DF;'
        f'font-size:12px;color:#8A8A86">{footer}</div>'
        '</div></body></html>'
    )


def send_email(to, subject, body, reply_to=None):
    """Send an email. Returns Brevo's message id, or raises SendError.

    reply_to is an optional (email, name) pair.
    """
    to, subject = to.strip(), subject.strip()
    body = body.strip("\r\n") if body.strip() else ""     # keep the first line's indent
    if not is_valid_email(to):
        raise SendError(MSG_BAD_RECIPIENT)
    if not subject:
        raise SendError(MSG_NO_SUBJECT)
    if not body:
        raise SendError(MSG_NO_BODY)
    api_key = config.get("BREVO_API_KEY")
    if not api_key:
        raise SendError(MSG_NOT_CONFIGURED)

    sent_from, sent_name = (reply_to[0], reply_to[1] or "") if reply_to else (None, "")
    payload = {
        "sender": {"name": config.get("SENDER_NAME"), "email": config.get("SENDER_EMAIL")},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": f"{body}\n\n{sender_line(sent_from, sent_name)}" if sent_from else body,
        "htmlContent": build_html(body, sent_from, sent_name),
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


# ---------- SMS provider (TextBee) ----------

def sms_enabled():
    """True when a TextBee API key is set. Without one the SMS tab stays in demo mode."""
    return bool(config.get("TEXTBEE_API_KEY"))


def is_valid_ph_mobile(number):
    """09XXXXXXXXX (11 digits)."""
    return PH_MOBILE.fullmatch(number.strip()) is not None


def to_e164(number):
    """09171234567 -> +639171234567 (the format TextBee expects)."""
    return "+63" + number.strip()[1:]


def send_sms(number, text):
    """Send an SMS through TextBee. Returns the batch id, or raises SendError.

    Success means TextBee accepted (queued) the message for your phone."""
    number, text = number.strip(), text.strip()
    if not is_valid_ph_mobile(number):
        raise SendError(MSG_BAD_NUMBER)
    if not text:
        raise SendError(MSG_NO_SMS_TEXT)
    api_key = config.get("TEXTBEE_API_KEY")
    if not api_key:
        raise SendError(MSG_SMS_NOT_CONFIGURED)

    payload = {"recipients": [to_e164(number)], "message": text}
    device_id = config.get("TEXTBEE_DEVICE_ID")
    if device_id:
        payload["deviceId"] = device_id
    url = config.get("TEXTBEE_BASE_URL").rstrip("/") + "/gateway/send-sms"

    try:
        reply = requests.post(
            url, json=payload, timeout=TIMEOUT,
            # own User-Agent: Python's default one can be blocked by Cloudflare
            headers={"x-api-key": api_key, "accept": "application/json",
                     "User-Agent": "cAPIbara/1.0"})
    except requests.exceptions.Timeout:
        raise SendError(MSG_SMS_TIMEOUT)
    except requests.exceptions.RequestException:
        raise SendError(MSG_SMS_NO_CONNECTION)

    if reply.status_code in (200, 201, 202):
        batch_id = _sms_batch_id(reply)
        if batch_id:
            _wait_for_phone(batch_id)
        return batch_id

    log.warning("TextBee error %s: %.300s", reply.status_code, reply.text)
    raise SendError(_sms_friendly(reply))


def _sms_item(batch_id):
    """The message row TextBee holds for this batch, or None if it cannot be read now."""
    url = config.get("TEXTBEE_BASE_URL").rstrip("/") + "/gateway/messages"
    try:
        reply = requests.get(
            url, params={"smsBatchId": batch_id}, timeout=TIMEOUT,
            headers={"x-api-key": config.get("TEXTBEE_API_KEY"),
                     "accept": "application/json", "User-Agent": "cAPIbara/1.0"})
        if reply.status_code != 200:
            return None
        rows = reply.json().get("data")
    except (requests.exceptions.RequestException, ValueError, AttributeError):
        return None
    if isinstance(rows, dict):
        rows = rows.get("data") or rows.get("messages")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]
    return None


def _wait_for_phone(batch_id):
    """TextBee answers 200 as soon as the message is QUEUED. The phone and the
    carrier decide later. Check the result for a few seconds so a text the phone
    could not send is reported as an error instead of 'sent'.

    Returns when the message is sent or delivered, or when the phone has not
    answered yet (the message is still queued, so the user must not resend it).
    Raises SendError when TextBee reports it failed. If the status cannot be
    read (network hiccup), the send is treated as accepted."""
    deadline = time.monotonic() + SMS_WAIT
    while True:
        item = _sms_item(batch_id)
        status = str((item or {}).get("status", "")).lower()
        if status in SMS_FAILED:
            log.warning("TextBee delivery failed: %.300s", item)
            raise SendError(_sms_failure_text(item))
        if status in SMS_SENT:
            return
        if time.monotonic() >= deadline:
            log.info("TextBee message %s still %r after %ss", batch_id, status or "unknown", SMS_WAIT)
            return
        time.sleep(SMS_POLL)


def _sms_failure_text(item):
    known = SMS_ERROR_CODES.get(str(item.get("errorCode") or ""))
    if known:
        return known
    detail = str(item.get("errorMessage") or "").strip()
    if detail:
        return f"The phone could not send the text. {detail}"[:300]
    return MSG_SMS_PHONE_FAILED


def _sms_batch_id(reply):
    """The batch id from a success reply. A 2xx body that says success=false is an error."""
    try:
        data = reply.json().get("data") or {}
    except (ValueError, AttributeError):
        return ""
    if not isinstance(data, dict):
        return ""
    if data.get("success") is False:
        log.warning("TextBee refused: %.300s", reply.text)
        raise SendError(MSG_SMS_REJECTED)
    return data.get("smsBatchId", "")


def _sms_friendly(reply):
    status = reply.status_code
    try:
        body = reply.json()
    except ValueError:
        body = None
    text = ""
    if isinstance(body, dict):
        text = str(body.get("error") or body.get("message") or "").lower()
    if status == 400:
        return MSG_SMS_NO_DEVICE if "device" in text else MSG_SMS_REJECTED
    if status in (401, 403):
        return MSG_SMS_REFUSED
    if status == 404:
        return MSG_SMS_DEVICE_UNKNOWN
    if status == 429:
        return MSG_SMS_LIMIT
    if status >= 500:
        return MSG_SMS_SERVER
    return MSG_SMS_UNEXPECTED


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