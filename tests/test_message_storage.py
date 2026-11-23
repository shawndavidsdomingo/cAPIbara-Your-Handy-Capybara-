"""Saved drafts and sent messages. Uses a temporary database, never capibara.db."""
import sqlite3

import pytest

import auth_service
import db
import message_service as ms
import stats


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


@pytest.fixture
def users():
    a = auth_service.register_user("alice", "Alice A", "alice@example.com", "password1")
    b = auth_service.register_user("bobby", "Bobby B", "bobby@example.com", "password2")
    return a, b


def test_messages_table_exists_with_foreign_keys():
    with db.connection() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "messages" in tables
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_save_and_reload_a_draft(users):
    a, _ = users
    draft_id = ms.save_draft(a, "Email", "x@y.co", "Hi", "Body")
    rows = ms.get_drafts(a, "Email")
    assert [(r["id"], r["recipient"], r["subject"], r["body"]) for r in rows] == [
        (draft_id, "x@y.co", "Hi", "Body")]
    assert ms.get_sent(a, "Email") == []


def test_update_draft(users):
    a, _ = users
    draft_id = ms.save_draft(a, "Email", "x@y.co", "Hi", "Body")
    assert ms.update_draft(a, draft_id, "z@y.co", "New", "Changed")
    row = ms.get_drafts(a, "Email")[0]
    assert (row["recipient"], row["subject"], row["body"]) == ("z@y.co", "New", "Changed")


def test_delete_draft(users):
    a, _ = users
    draft_id = ms.save_draft(a, "SMS", "0912", None, "hello")
    assert ms.delete_draft(a, draft_id)
    assert ms.get_drafts(a, "SMS") == []


def test_record_sent_is_listed_newest_first_and_keeps_the_text(users):
    a, _ = users
    first = ms.record_sent(a, "Email", "x@y.co", "One", "First body")
    second = ms.record_sent(a, "Email", "x@y.co", "Two", "Second body")
    sent = ms.get_sent(a, "Email")
    assert [r["id"] for r in sent] == [second, first]
    assert sent[1]["body"] == "First body" and sent[0]["sent_at"]


def test_sending_a_draft_removes_that_draft(users):
    a, _ = users
    draft_id = ms.save_draft(a, "Email", "x@y.co", "Hi", "Body")
    ms.record_sent(a, "Email", "x@y.co", "Hi", "Body", draft_id)
    assert ms.get_drafts(a, "Email") == []
    assert len(ms.get_sent(a, "Email")) == 1


def test_kinds_are_separate(users):
    a, _ = users
    ms.record_sent(a, "Email", "x@y.co", "Hi", "Body")
    ms.record_sent(a, "SMS", "0912", None, "text")
    assert len(ms.get_sent(a, "Email")) == 1
    assert len(ms.get_sent(a, "SMS")) == 1


def test_users_cannot_see_or_change_each_others_messages(users):
    a, b = users
    draft_id = ms.save_draft(a, "Email", "x@y.co", "Hi", "Body")
    ms.record_sent(a, "Email", "x@y.co", "Hi", "Body")
    assert ms.get_drafts(b, "Email") == [] and ms.get_sent(b, "Email") == []
    assert not ms.update_draft(b, draft_id, "evil@y.co", "x", "x")
    assert not ms.delete_draft(b, draft_id)
    assert len(ms.get_drafts(a, "Email")) == 1


def test_a_sent_message_is_not_treated_as_a_draft(users):
    a, _ = users
    sent_id = ms.record_sent(a, "Email", "x@y.co", "Hi", "Body")
    assert not ms.delete_draft(a, sent_id)
    assert not ms.update_draft(a, sent_id, "x", "x", "x")
    assert len(ms.get_sent(a, "Email")) == 1


def test_invalid_kind_is_rejected(users):
    a, _ = users
    with pytest.raises(sqlite3.IntegrityError):
        ms.save_draft(a, "Fax", "x", None, "y")


def test_dashboard_counts_only_sent_messages_of_the_user(users):
    a, b = users
    ms.save_draft(a, "Email", "x@y.co", "Draft", "not counted")
    ms.record_sent(a, "Email", "x@y.co", "One", "b")
    ms.record_sent(a, "Email", "x@y.co", "Two", "b")
    ms.record_sent(a, "SMS", "0912", None, "t")
    ms.record_sent(b, "Email", "x@y.co", "Other", "b")
    assert (stats.count_emails(a), stats.count_sms(a)) == (2, 1)
    assert (stats.count_emails(b), stats.count_sms(b)) == (1, 0)
