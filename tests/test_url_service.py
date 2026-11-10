import pytest
import requests

import auth_service as auth
import db
import stats
import url_service as svc


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


@pytest.fixture
def users():
    a = auth.register_user("juan", "Juan Cruz", "juan@example.com", "secret123")
    b = auth.register_user("maria", "Maria Reyes", "maria@example.com", "secret123")
    return a, b


class FakeReply:
    def __init__(self, payload=None, status=200, bad_json=False):
        self.payload, self.status_code, self.bad_json = payload, status, bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))

    def json(self):
        if self.bad_json:
            raise ValueError("not json")
        return self.payload


def fake_get(reply):
    def _get(url, params=None, timeout=None):
        if isinstance(reply, Exception):
            raise reply
        return reply
    return _get


# ---------- Validation ----------

@pytest.mark.parametrize("url", ["https://example.com", "http://example.com/a?b=1"])
def test_valid_urls(url):
    assert svc.is_valid_url(url)


@pytest.mark.parametrize("url", ["", "example.com", "ftp://example.com", "http://", "https://a b.com", "not a link"])
def test_invalid_urls_rejected(url):
    assert not svc.is_valid_url(url)


def test_alias_rules():
    assert svc.is_valid_alias("my_link1")
    for bad in ("ab", "x" * 21, "has space", "dash-ed", ""):
        assert not svc.is_valid_alias(bad)


# ---------- Provider (the network is always faked) ----------

def test_success_reply_with_string_data(monkeypatch):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(
        {"status": "success", "data": "https://ulvis.net/abc123"})))
    assert svc.ulvis_shorten("https://example.com") == "https://ulvis.net/abc123"


def test_success_reply_with_dict_data(monkeypatch):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(
        {"error": 0, "data": {"id": "abc123", "short": "https://ulvis.net/abc123"}})))
    assert svc.ulvis_shorten("https://example.com") == "https://ulvis.net/abc123"


def test_alias_is_sent_as_custom(monkeypatch):
    seen = {}

    def _get(url, params=None, timeout=None):
        seen.update(params=params, timeout=timeout)
        return FakeReply({"status": "success", "data": "https://ulvis.net/mine"})

    monkeypatch.setattr(requests, "get", _get)
    svc.ulvis_shorten("https://example.com", "mine")
    assert seen["params"]["custom"] == "mine"
    assert seen["params"]["url"] == "https://example.com"
    assert seen["timeout"] == svc.TIMEOUT


@pytest.mark.parametrize("payload, message", [
    ({"status": "error", "error": "custom name already exists"}, svc.MSG_ALIAS_TAKEN),
    ({"status": "error", "error": "Invalid url"}, svc.MSG_INVALID_URL),
    ({"status": "error", "error": "Too many requests"}, svc.MSG_RATE_LIMIT),
    ({"status": "error", "error": "boom"}, svc.MSG_UNEXPECTED),
    ({"hello": "world"}, svc.MSG_UNEXPECTED),
    (["not", "a", "dict"], svc.MSG_UNEXPECTED),
])
def test_error_replies_become_readable_messages(monkeypatch, payload, message):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(payload)))
    with pytest.raises(svc.ShortenError) as error:
        svc.ulvis_shorten("https://example.com")
    assert str(error.value) == message


@pytest.mark.parametrize("reply, message", [
    (requests.exceptions.Timeout(), svc.MSG_TIMEOUT),
    (requests.exceptions.ConnectionError(), svc.MSG_NO_CONNECTION),
    (FakeReply(status=429), svc.MSG_RATE_LIMIT),
    (FakeReply(status=500), svc.MSG_NO_CONNECTION),
    (FakeReply(bad_json=True), svc.MSG_UNEXPECTED),
])
def test_network_problems_become_readable_messages(monkeypatch, reply, message):
    monkeypatch.setattr(requests, "get", fake_get(reply))
    with pytest.raises(svc.ShortenError) as error:
        svc.ulvis_shorten("https://example.com")
    assert str(error.value) == message


def test_failed_shorten_saves_nothing(monkeypatch, users):
    monkeypatch.setattr(requests, "get", fake_get(requests.exceptions.Timeout()))
    with pytest.raises(svc.ShortenError):
        svc.ulvis_shorten("https://example.com")
    assert svc.get_links(users[0]) == []


# ---------- Storage ----------

def test_saved_link_appears_in_history(users):
    juan, _ = users
    link_id = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a", "mine")
    links = svc.get_links(juan)
    assert len(links) == 1
    assert links[0]["id"] == link_id and links[0]["alias"] == "mine"
    assert links[0]["short_url"] == "https://ulvis.net/a" and links[0]["clicks"] == 0


def test_history_is_newest_first(users):
    juan, _ = users
    svc.save_link(juan, "https://ulvis.net/1", "https://example.com/1")
    svc.save_link(juan, "https://ulvis.net/2", "https://example.com/2")
    assert [l["short_url"] for l in svc.get_links(juan)] == [
        "https://ulvis.net/2", "https://ulvis.net/1"]


def test_links_of_one_user_are_invisible_to_another(users):
    juan, maria = users
    svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    assert svc.get_links(maria) == []
    assert stats.count_links(maria) == 0 and stats.count_links(juan) == 1


def test_clicks_are_counted(users):
    juan, _ = users
    link_id = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    assert svc.record_click(juan, link_id)
    assert svc.record_click(juan, link_id)
    assert svc.get_links(juan)[0]["clicks"] == 2


def test_cannot_click_or_delete_another_users_link(users):
    juan, maria = users
    link_id = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    assert not svc.record_click(maria, link_id)
    assert not svc.delete_link(maria, link_id)
    assert len(svc.get_links(juan)) == 1


def test_delete_link_removes_its_clicks(users):
    juan, _ = users
    link_id = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    svc.record_click(juan, link_id)
    assert svc.delete_link(juan, link_id)
    assert svc.get_links(juan) == []
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM link_clicks").fetchone()[0] == 0
