import json
import logging
import time

import pytest
import requests

import auth_service as auth
import db
import stats
import url_service as svc

LONG = "https://example.com/some/long/page"


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
    """Stands in for requests.Response. Pass a dict (sent as JSON) or raw text."""

    def __init__(self, body="", status=200):
        self.text = body if isinstance(body, str) else json.dumps(body)
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))


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


@pytest.mark.parametrize("url", ["", "example.com", "ftp://example.com",
                                 "http://", "https://a b.com", "not a link"])
def test_invalid_urls_rejected(url):
    assert not svc.is_valid_url(url)


# ---------- Reading the reply (the network is always faked) ----------

@pytest.mark.parametrize("body", [
    {"success": True, "data": {"id": "abc123", "url": "https://ulvis.net/abc123",
                               "full": LONG, "status": "ok"}},
    {"status": "success", "data": "https://ulvis.net/abc123"},
    {"error": 0, "data": {"short": "https://ulvis.net/abc123"}},
    {"error": {"code": 0, "msg": ""}, "data": {"url": "https://ulvis.net/abc123"}},
    '{"data":{"url":"https:\\/\\/ulvis.net\\/abc123"}}',          # PHP-escaped slashes
    "https://ulvis.net/abc123",                                   # plain text reply
    "<result><url>https://ulvis.net/abc123</url></result>",       # XML reply
], ids=["json-dict", "json-string", "json-short", "json-error-zero",
        "escaped-slashes", "plain-text", "xml"])
def test_short_link_is_found_in_any_reply_shape(monkeypatch, body):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(body)))
    assert svc.ulvis_shorten(LONG) == "https://ulvis.net/abc123"


def test_code_only_reply_is_turned_into_a_link(monkeypatch):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply({"data": {"id": "xYz9"}})))
    assert svc.ulvis_shorten(LONG) == "https://ulvis.net/xYz9"


def test_original_link_is_never_returned_as_the_short_link(monkeypatch):
    original = "https://ulvis.net/some-page-to-shorten"
    body = {"data": {"full": original, "url": "https://ulvis.net/q1w2e3"}}
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(body)))
    assert svc.ulvis_shorten(original) == "https://ulvis.net/q1w2e3"


def test_documentation_links_are_not_short_links(monkeypatch):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(
        {"error": "see https://ulvis.net/developer.html"})))
    with pytest.raises(svc.ShortenError):
        svc.ulvis_shorten(LONG)


def test_only_the_url_is_sent(monkeypatch):
    seen = {}

    def _get(url, params=None, timeout=None):
        seen.update(url=url, params=params, timeout=timeout)
        return FakeReply("https://ulvis.net/abc123")

    monkeypatch.setattr(requests, "get", _get)
    svc.ulvis_shorten(LONG)
    assert seen["url"] == svc.ULVIS_ENDPOINT
    assert seen["params"] == {"url": LONG}
    assert seen["timeout"] == svc.TIMEOUT


@pytest.mark.parametrize("body, message", [
    ({"status": "error", "error": "Invalid url"}, svc.MSG_INVALID_URL),
    ({"error": {"code": 3, "msg": "Too many requests"}}, svc.MSG_RATE_LIMIT),
    ({"status": "error", "error": "boom"}, svc.MSG_UNEXPECTED),
    ({"hello": "world"}, svc.MSG_UNEXPECTED),
    (["not", "a", "dict"], svc.MSG_UNEXPECTED),
    ("<html>oops</html>", svc.MSG_UNEXPECTED),
    ("", svc.MSG_UNEXPECTED),
], ids=["bad-url", "rate-limit-dict", "unknown-error", "no-fields",
        "list", "html", "empty"])
def test_error_replies_become_readable_messages(monkeypatch, body, message):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(body)))
    with pytest.raises(svc.ShortenError) as error:
        svc.ulvis_shorten(LONG)
    assert str(error.value) == message


def test_unrecognised_reply_is_logged_for_debugging(monkeypatch, caplog):
    monkeypatch.setattr(requests, "get", fake_get(FakeReply({"weird": "shape"})))
    with caplog.at_level(logging.WARNING, logger="url_service"):
        with pytest.raises(svc.ShortenError):
            svc.ulvis_shorten(LONG)
    assert "weird" in caplog.text


@pytest.mark.parametrize("reply, message", [
    (requests.exceptions.Timeout(), svc.MSG_TIMEOUT),
    (requests.exceptions.ConnectionError(), svc.MSG_NO_CONNECTION),
    (FakeReply(status=429), svc.MSG_RATE_LIMIT),
    (FakeReply(status=500), svc.MSG_NO_CONNECTION),
], ids=["timeout", "no-connection", "http-429", "http-500"])
def test_network_problems_become_readable_messages(monkeypatch, reply, message):
    monkeypatch.setattr(requests, "get", fake_get(reply))
    with pytest.raises(svc.ShortenError) as error:
        svc.ulvis_shorten(LONG)
    assert str(error.value) == message


def test_failed_shorten_saves_nothing(monkeypatch, users):
    monkeypatch.setattr(requests, "get", fake_get(requests.exceptions.Timeout()))
    with pytest.raises(svc.ShortenError):
        svc.ulvis_shorten(LONG)
    assert svc.get_links(users[0]) == []


# ---------- Storage ----------

def test_saved_link_appears_in_history(users):
    juan, _ = users
    link_id = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    links = svc.get_links(juan)
    assert len(links) == 1
    assert links[0]["id"] == link_id
    assert links[0]["short_url"] == "https://ulvis.net/a"
    assert links[0]["original_url"] == "https://example.com/a"
    assert links[0]["clicks"] == 0


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


# ---------- Reusing a link ----------

def tick():
    time.sleep(0.01)          # keep timestamps (millisecond resolution) distinct


def test_saving_the_same_url_again_keeps_one_row_and_moves_it_to_top(users):
    juan, _ = users
    first = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    tick(); svc.save_link(juan, "https://ulvis.net/b", "https://example.com/b")
    tick(); svc.save_link(juan, "https://ulvis.net/c", "https://example.com/c")
    tick()
    again = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    assert again == first
    assert [l["original_url"] for l in svc.get_links(juan)] == [
        "https://example.com/a", "https://example.com/c", "https://example.com/b"]


def test_bumping_a_link_moves_it_to_top_and_keeps_its_clicks(users):
    juan, _ = users
    old = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    svc.record_click(juan, old); svc.record_click(juan, old)
    tick(); svc.save_link(juan, "https://ulvis.net/b", "https://example.com/b")
    tick()
    assert svc.bump_link(juan, old)
    links = svc.get_links(juan)
    assert links[0]["id"] == old and links[0]["clicks"] == 2
    assert len(links) == 2


def test_find_link_matches_only_this_users_exact_url(users):
    juan, maria = users
    link_id = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    assert svc.find_link(juan, "https://example.com/a")["id"] == link_id
    assert svc.find_link(maria, "https://example.com/a") is None
    assert svc.find_link(juan, "https://example.com/a?x=1") is None
    assert svc.find_link(juan, "https://example.com/other") is None


def test_two_users_can_shorten_the_same_url_separately(users):
    juan, maria = users
    svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    svc.save_link(maria, "https://ulvis.net/a", "https://example.com/a")
    assert len(svc.get_links(juan)) == 1 and len(svc.get_links(maria)) == 1


def test_cannot_bump_another_users_link(users):
    juan, maria = users
    link_id = svc.save_link(juan, "https://ulvis.net/a", "https://example.com/a")
    assert not svc.bump_link(maria, link_id)


def test_old_duplicate_rows_do_not_break_lookup(users):
    juan, _ = users
    with db.connection() as conn:            # rows saved before dedup existed
        for code in ("old1", "old2"):
            conn.execute("INSERT INTO links (user_id, short_url, original_url) "
                         "VALUES (?, ?, ?)", (juan, f"https://ulvis.net/{code}",
                                              "https://example.com/a"))
    assert svc.find_link(juan, "https://example.com/a")["short_url"] == "https://ulvis.net/old2"
    svc.save_link(juan, "https://ulvis.net/new", "https://example.com/a")
    assert svc.get_links(juan)[0]["short_url"] == "https://ulvis.net/new"
