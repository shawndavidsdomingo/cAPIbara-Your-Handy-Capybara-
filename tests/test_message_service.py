"""Email provider tests. The network is always faked: no real email is sent."""
import pytest
import requests

from core import config
from services import message_service
from services.message_service import SendError


class FakeReply:
    def __init__(self, status=201, body=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {"messageId": "<abc@brevo>"}
        self.text = text

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """Any test that forgets to fake requests.post fails instead of sending."""
    def blocked(*args, **kwargs):
        raise AssertionError("test tried to use the real network")
    monkeypatch.setattr(message_service.requests, "post", blocked)
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("SENDER_EMAIL", "noreply@capibara-shawn-neo.online")
    monkeypatch.setenv("SENDER_NAME", "cAPIbara")


def fake_post(monkeypatch, reply=None, error=None):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if error:
            raise error
        return reply or FakeReply()
    monkeypatch.setattr(message_service.requests, "post", post)
    return calls


# ---------- success and request shape ----------

def test_send_email_returns_message_id_and_builds_request(monkeypatch):
    calls = fake_post(monkeypatch)
    result = message_service.send_email(
        "juan@example.com", "Hello", "Body text",
        reply_to=("me@example.com", "Me"))
    assert result == "<abc@brevo>"

    url, kwargs = calls[0]
    assert url == "https://api.brevo.com/v3/smtp/email"
    assert kwargs["headers"]["api-key"] == "test-key"
    assert kwargs["timeout"] == message_service.TIMEOUT
    payload = dict(kwargs["json"])
    html_part = payload.pop("htmlContent")
    assert payload == {
        "sender": {"name": "cAPIbara", "email": "noreply@capibara-shawn-neo.online"},
        "to": [{"email": "juan@example.com"}],
        "subject": "Hello",
        "textContent": "Body text",
        "replyTo": {"email": "me@example.com", "name": "Me"},
    }
    assert "Body text" in html_part


def test_no_reply_to_when_not_given(monkeypatch):
    calls = fake_post(monkeypatch)
    message_service.send_email("juan@example.com", "Hi", "Body")
    assert "replyTo" not in calls[0][1]["json"]


def test_sender_defaults_to_the_domain_address(monkeypatch):
    monkeypatch.delenv("SENDER_EMAIL")
    monkeypatch.delenv("SENDER_NAME")
    calls = fake_post(monkeypatch)
    message_service.send_email("juan@example.com", "Hi", "Body")
    sender = calls[0][1]["json"]["sender"]
    assert sender == {"name": "cAPIbara", "email": "noreply@capibara-shawn-neo.online"}


def test_success_with_unreadable_body_still_succeeds(monkeypatch):
    fake_post(monkeypatch, FakeReply(201, body=ValueError("not json")))
    assert message_service.send_email("a@b.co", "Hi", "Body") == ""


# ---------- checks that run before any network call ----------

@pytest.mark.parametrize("to, subject, body, expected", [
    ("", "Hi", "Body", message_service.MSG_BAD_RECIPIENT),
    ("not-an-email", "Hi", "Body", message_service.MSG_BAD_RECIPIENT),
    ("a@b.co,c@d.co", "Hi", "Body", message_service.MSG_BAD_RECIPIENT),
    ("a@b.co", "  ", "Body", message_service.MSG_NO_SUBJECT),
    ("a@b.co", "Hi", "   ", message_service.MSG_NO_BODY),
])
def test_invalid_input_is_rejected_without_network(to, subject, body, expected):
    with pytest.raises(SendError) as error:      # network is blocked by the fixture
        message_service.send_email(to, subject, body)
    assert str(error.value) == expected


def test_missing_api_key_is_a_readable_error(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY")
    assert not message_service.email_enabled()
    with pytest.raises(SendError) as error:
        message_service.send_email("a@b.co", "Hi", "Body")
    assert str(error.value) == message_service.MSG_NOT_CONFIGURED


def test_email_enabled_with_key():
    assert message_service.email_enabled()


# ---------- provider errors ----------

@pytest.mark.parametrize("status, expected", [
    (400, message_service.MSG_REJECTED),
    (401, message_service.MSG_REFUSED),
    (403, message_service.MSG_REFUSED),
    (429, message_service.MSG_RATE_LIMIT),
    (500, message_service.MSG_SERVER),
    (503, message_service.MSG_SERVER),
    (418, message_service.MSG_UNEXPECTED),
])
def test_http_errors_become_readable_messages(monkeypatch, status, expected):
    fake_post(monkeypatch, FakeReply(status, text="provider detail"))
    with pytest.raises(SendError) as error:
        message_service.send_email("a@b.co", "Hi", "Body")
    assert str(error.value) == expected


def test_timeout(monkeypatch):
    fake_post(monkeypatch, error=requests.exceptions.Timeout())
    with pytest.raises(SendError) as error:
        message_service.send_email("a@b.co", "Hi", "Body")
    assert str(error.value) == message_service.MSG_TIMEOUT


def test_no_connection(monkeypatch):
    fake_post(monkeypatch, error=requests.exceptions.ConnectionError())
    with pytest.raises(SendError) as error:
        message_service.send_email("a@b.co", "Hi", "Body")
    assert str(error.value) == message_service.MSG_NO_CONNECTION


def test_api_key_is_never_in_an_error_message(monkeypatch):
    fake_post(monkeypatch, FakeReply(401, text="bad key test-key"))
    with pytest.raises(SendError) as error:
        message_service.send_email("a@b.co", "Hi", "Body")
    assert "test-key" not in str(error.value)


# ---------- HTML version and logo ----------

def test_html_escapes_what_the_user_typed():
    page = message_service.build_html('<script>alert(1)</script>\nsecond & line')
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "second &amp; line" in page
    assert "<br>" in page                      # new lines survive


def test_html_uses_text_header_without_a_logo(monkeypatch):
    monkeypatch.delenv("LOGO_URL", raising=False)
    page = message_service.build_html("Hi")
    assert "<img" not in page and "cAPIbara" in page


def test_html_uses_the_logo_when_set(monkeypatch):
    monkeypatch.setenv("LOGO_URL", "https://example.com/logo.png")
    page = message_service.build_html("Hi")
    assert '<img src="https://example.com/logo.png"' in page


@pytest.mark.parametrize("bad", ["http://example.com/logo.png", 'javascript:alert(1)',
                                 "C:\\Users\\me\\logo.png"])
def test_logo_that_is_not_https_is_ignored(monkeypatch, bad):
    monkeypatch.setenv("LOGO_URL", bad)
    assert message_service.logo_url() == ""
    assert "<img" not in message_service.build_html("Hi")


def test_logo_url_cannot_break_out_of_the_attribute(monkeypatch):
    monkeypatch.setenv("LOGO_URL", 'https://x.com/a.png" onerror="alert(1)')
    page = message_service.build_html("Hi")
    assert '" onerror=' not in page


# ---------- OTP email ----------

def test_otp_email_contains_the_code(monkeypatch):
    calls = fake_post(monkeypatch)
    message_service.send_otp_email("juan@example.com", "123456")
    payload = calls[0][1]["json"]
    assert payload["to"] == [{"email": "juan@example.com"}]
    assert "123456" in payload["textContent"]
    assert "verification code" in payload["subject"].lower()


# ---------- .env parsing ----------

def test_parse_env():
    text = '# comment\n\nBREVO_API_KEY="abc123"\nSENDER_NAME = cAPIbara \nbad line\nX=\'q\'\n'
    assert config.parse_env(text) == {
        "BREVO_API_KEY": "abc123", "SENDER_NAME": "cAPIbara", "X": "q"}


def test_load_env_does_not_override_real_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MY_TEST_SETTING=from_file\nMY_OTHER_SETTING=from_file\n")
    monkeypatch.setenv("MY_TEST_SETTING", "from_env")
    monkeypatch.delenv("MY_OTHER_SETTING", raising=False)
    config.load_env(str(env_file))
    assert config.get("MY_TEST_SETTING") == "from_env"
    assert config.get("MY_OTHER_SETTING") == "from_file"
    monkeypatch.delenv("MY_OTHER_SETTING", raising=False)   # load_env set it outside monkeypatch


def test_load_env_missing_file_is_fine(tmp_path):
    config.load_env(str(tmp_path / "nope.env"))