import pytest
from unittest.mock import patch, MagicMock
import requests
from services import message_service as ms


def reply(status, body=None, text=""):
    r = MagicMock(status_code=status, text=text)
    if body is None:
        r.json.side_effect = ValueError
    else:
        r.json.return_value = body
    return r


def status_reply(status, **extra):
    return reply(200, {"data": [{"status": status, **extra}]})


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("TEXTBEE_API_KEY", "k123")
    monkeypatch.delenv("TEXTBEE_DEVICE_ID", raising=False)
    monkeypatch.setattr(ms, "SMS_POLL", 0)
    monkeypatch.setattr(ms, "SMS_WAIT", 0)
    # by default the phone reports "sent"; tests override ms.requests.get when needed
    monkeypatch.setattr(ms.requests, "get", lambda *a, **k: status_reply("sent"))


QUEUED = reply(200, {"data": {"success": True, "smsBatchId": "b1"}})


def test_phone_failure_is_an_error():
    item = status_reply("failed", errorCode="CARRIER_0x44",
                        errorMessage="The carrier could not give the SMS the service it needs.")
    with patch.object(ms.requests, "post", return_value=QUEUED), \
            patch.object(ms.requests, "get", return_value=item) as get:
        with pytest.raises(ms.SendError, match="carrier could not give"):
            ms.send_sms("09171234567", "hi")
    assert get.call_args[1]["params"] == {"smsBatchId": "b1"}


def test_known_error_code_and_fallback():
    with patch.object(ms.requests, "post", return_value=QUEUED):
        with patch.object(ms.requests, "get", return_value=status_reply("failed", errorCode="4")):
            with pytest.raises(ms.SendError, match="no mobile service"):
                ms.send_sms("09171234567", "hi")
        with patch.object(ms.requests, "get", return_value=status_reply("failed")):
            with pytest.raises(ms.SendError) as e:
                ms.send_sms("09171234567", "hi")
        assert str(e.value) == ms.MSG_SMS_PHONE_FAILED


def test_still_queued_or_unreadable_status_counts_as_accepted():
    with patch.object(ms.requests, "post", return_value=QUEUED):
        with patch.object(ms.requests, "get", return_value=status_reply("pending")):
            assert ms.send_sms("09171234567", "hi") == "b1"
        with patch.object(ms.requests, "get", side_effect=requests.exceptions.ConnectionError):
            assert ms.send_sms("09171234567", "hi") == "b1"
        with patch.object(ms.requests, "get", return_value=reply(500)):
            assert ms.send_sms("09171234567", "hi") == "b1"


def test_waits_until_the_phone_answers(monkeypatch):
    monkeypatch.setattr(ms, "SMS_WAIT", 5)
    answers = iter([status_reply("pending"), status_reply("dispatched"), status_reply("sent")])
    with patch.object(ms.requests, "post", return_value=QUEUED), \
            patch.object(ms.requests, "get", side_effect=lambda *a, **k: next(answers)) as get:
        assert ms.send_sms("09171234567", "hi") == "b1"
    assert get.call_count == 3


def test_validation():
    assert ms.is_valid_ph_mobile("09171234567")
    for bad in ("9171234567", "0917123456", "+639171234567", "0917123456a", ""):
        assert not ms.is_valid_ph_mobile(bad)
    assert ms.to_e164("09171234567") == "+639171234567"


def test_success_request_shape():
    with patch.object(ms.requests, "post",
                      return_value=reply(200, {"data": {"success": True, "smsBatchId": "b1"}})) as post:
        assert ms.send_sms("09171234567", " hi ") == "b1"
    args, kw = post.call_args
    assert args[0] == "https://api.textbee.dev/api/v1/gateway/send-sms"
    assert kw["json"] == {"recipients": ["+639171234567"], "message": "hi"}
    assert kw["headers"]["x-api-key"] == "k123" and kw["headers"]["User-Agent"]


def test_device_id_sent(monkeypatch):
    monkeypatch.setenv("TEXTBEE_DEVICE_ID", "dev9")
    with patch.object(ms.requests, "post", return_value=reply(200, {"data": {}})) as post:
        ms.send_sms("09171234567", "hi")
    assert post.call_args[1]["json"]["deviceId"] == "dev9"


@pytest.mark.parametrize("status,body,msg", [
    (400, {"error": "No enabled device found"}, ms.MSG_SMS_NO_DEVICE),
    (400, {"error": "recipient has letters"}, ms.MSG_SMS_REJECTED),
    (401, {"error": "Unauthorized"}, ms.MSG_SMS_REFUSED),
    (404, {"error": "Device not found"}, ms.MSG_SMS_DEVICE_UNKNOWN),
    (429, {"message": "daily limit"}, ms.MSG_SMS_LIMIT),
    (503, None, ms.MSG_SMS_SERVER),
    (418, None, ms.MSG_SMS_UNEXPECTED),
])
def test_errors(status, body, msg):
    with patch.object(ms.requests, "post", return_value=reply(status, body)):
        with pytest.raises(ms.SendError) as e:
            ms.send_sms("09171234567", "hi")
    assert str(e.value) == msg


def test_network_errors():
    for exc, msg in ((requests.exceptions.Timeout, ms.MSG_SMS_TIMEOUT),
                     (requests.exceptions.ConnectionError, ms.MSG_SMS_NO_CONNECTION)):
        with patch.object(ms.requests, "post", side_effect=exc):
            with pytest.raises(ms.SendError, match=msg[:20]):
                ms.send_sms("09171234567", "hi")


def test_success_false_in_2xx():
    with patch.object(ms.requests, "post", return_value=reply(200, {"data": {"success": False}})):
        with pytest.raises(ms.SendError):
            ms.send_sms("09171234567", "hi")


def test_guards_before_network(monkeypatch):
    with patch.object(ms.requests, "post") as post:
        with pytest.raises(ms.SendError): ms.send_sms("123", "hi")
        with pytest.raises(ms.SendError): ms.send_sms("09171234567", "  ")
        monkeypatch.delenv("TEXTBEE_API_KEY")
        with pytest.raises(ms.SendError, match="not set up"): ms.send_sms("09171234567", "hi")
        assert not ms.sms_enabled()
    post.assert_not_called()