"""FakerAPI provider and fake-data storage. The network is always faked."""
import json

import pytest
import requests

from services import auth_service as auth
from core import db
from services import fake_service as svc
from services import stats


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
    def __init__(self, body=None, status=200):
        self._body, self.status_code = body, status

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))


def person(n=1):
    return {"id": n, "firstname": f"First{n}", "lastname": f"Last{n}",
            "email": f"p{n}@example.com", "phone": f"+1555000{n}",
            "birthday": "1990-05-17", "gender": "female",
            "address": {"street": f"{n} Main St", "city": "Manila",
                        "zipcode": "1000", "country": "Philippines",
                        "latitude": 14.59, "longitude": 120.98},
            "website": "http://example.com", "image": "http://x/y.jpg"}


def reply_with(n=10):
    return FakeReply({"status": "OK", "code": 200, "total": n,
                      "data": [person(i) for i in range(1, n + 1)]})


def fake_get(reply, seen=None):
    def _get(url, params=None, timeout=None):
        if seen is not None:
            seen.update(url=url, params=params, timeout=timeout)
        if isinstance(reply, Exception):
            raise reply
        return reply
    return _get


# ---------- Provider ----------

def test_only_the_chosen_fields_are_kept(monkeypatch):
    monkeypatch.setattr(requests, "get", fake_get(reply_with(10)))
    rows = svc.fetch_persons(10, ["full_name", "city", "zip_code"])
    assert len(rows) == 10
    assert rows[0] == {"full_name": "First1 Last1", "city": "Manila", "zip_code": "1000"}


def test_every_field_can_be_read(monkeypatch):
    monkeypatch.setattr(requests, "get", fake_get(reply_with(10)))
    rows = svc.fetch_persons(10, list(svc.FIELDS))
    assert set(rows[0]) == set(svc.FIELDS)
    assert rows[0]["address"] == "1 Main St" and rows[0]["latitude"] == "14.59"
    assert rows[0]["mobile"] == "+15550001" and rows[0]["birthdate"] == "1990-05-17"


def test_default_fields_are_ten_valid_fields():
    assert len(svc.DEFAULT_FIELDS) == 10
    assert all(key in svc.FIELDS for key in svc.DEFAULT_FIELDS)


def test_request_shape(monkeypatch):
    seen = {}
    monkeypatch.setattr(requests, "get", fake_get(reply_with(10), seen))
    svc.fetch_persons(10, ["email"], gender="male")
    assert seen["url"] == svc.ENDPOINT
    assert seen["params"] == {"_quantity": 10, "_locale": "en_US", "_gender": "male"}
    assert seen["timeout"] == svc.TIMEOUT


def test_gender_any_sends_no_gender(monkeypatch):
    seen = {}
    monkeypatch.setattr(requests, "get", fake_get(reply_with(10), seen))
    svc.fetch_persons(10, ["email"])
    assert "_gender" not in seen["params"]


def test_missing_address_gives_empty_text(monkeypatch):
    body = {"data": [{"firstname": "A", "lastname": "B"}] * 10}
    monkeypatch.setattr(requests, "get", fake_get(FakeReply(body)))
    rows = svc.fetch_persons(10, ["full_name", "city", "email"])
    assert rows[0] == {"full_name": "A B", "city": "", "email": ""}


@pytest.mark.parametrize("fields, count, message", [
    ([], 10, svc.MSG_NO_FIELDS),
    (["nope"], 10, svc.MSG_NO_FIELDS),
    (["email"], 9, svc.MSG_BAD_COUNT),
    (["email"], 1001, svc.MSG_BAD_COUNT),
])
def test_bad_input_is_rejected_before_any_network_call(monkeypatch, fields, count, message):
    def blocked(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(requests, "get", blocked)
    with pytest.raises(svc.FakeDataError) as error:
        svc.fetch_persons(count, fields)
    assert str(error.value) == message


@pytest.mark.parametrize("reply, message", [
    (requests.exceptions.Timeout(), svc.MSG_TIMEOUT),
    (requests.exceptions.ConnectionError(), svc.MSG_NO_CONNECTION),
    (FakeReply(status=429), svc.MSG_RATE_LIMIT),
    (FakeReply(status=500), svc.MSG_NO_CONNECTION),
    (FakeReply(ValueError("not json")), svc.MSG_UNEXPECTED),
    (FakeReply({"hello": "world"}), svc.MSG_UNEXPECTED),
    (FakeReply({"data": []}), svc.MSG_UNEXPECTED),
    (FakeReply(["a", "list"]), svc.MSG_UNEXPECTED),
], ids=["timeout", "no-connection", "http-429", "http-500",
        "not-json", "no-data", "empty-data", "list"])
def test_problems_become_readable_messages(monkeypatch, reply, message):
    monkeypatch.setattr(requests, "get", fake_get(reply))
    with pytest.raises(svc.FakeDataError) as error:
        svc.fetch_persons(10, ["email"])
    assert str(error.value) == message


def test_failed_request_saves_nothing(monkeypatch, users):
    monkeypatch.setattr(requests, "get", fake_get(requests.exceptions.Timeout()))
    with pytest.raises(svc.FakeDataError):
        svc.generate_and_save(users[0], 10, ["email"])
    assert svc.get_generations(users[0]) == []


# ---------- Storage ----------

def test_generate_and_save_stores_a_batch(monkeypatch, users):
    juan, _ = users
    monkeypatch.setattr(requests, "get", fake_get(reply_with(12)))
    gen_id = svc.generate_and_save(juan, 12, ["full_name", "email"])
    gens = svc.get_generations(juan)
    assert len(gens) == 1
    assert gens[0]["id"] == gen_id and gens[0]["name"] == "Gen 1"
    assert gens[0]["fields"] == ["full_name", "email"] and gens[0]["total"] == 12
    records = svc.get_records(juan, gen_id)
    assert len(records) == 12 and records[0] == {"full_name": "First1 Last1",
                                                 "email": "p1@example.com"}


def test_batches_are_numbered_per_user(users):
    juan, maria = users
    rows = [{"email": "a@b.co"}] * 10
    svc.create_generation(juan, ["email"], rows)
    svc.create_generation(juan, ["email"], rows)
    svc.create_generation(maria, ["email"], rows)
    assert [g["name"] for g in svc.get_generations(juan)] == ["Gen 1", "Gen 2"]
    assert [g["name"] for g in svc.get_generations(maria)] == ["Gen 1"]


def test_each_batch_remembers_its_own_fields(users):
    juan, _ = users
    svc.create_generation(juan, ["email"], [{"email": "a@b.co"}] * 10)
    svc.create_generation(juan, ["city", "gender"], [{"city": "X", "gender": "male"}] * 10)
    assert [g["fields"] for g in svc.get_generations(juan)] == [["email"], ["city", "gender"]]


def test_users_cannot_see_or_delete_each_others_data(users):
    juan, maria = users
    gen_id = svc.create_generation(juan, ["email"], [{"email": "a@b.co"}] * 10)
    assert svc.get_generations(maria) == []
    assert svc.get_records(maria, gen_id) == []
    assert not svc.delete_generation(maria, gen_id)
    svc.clear_generations(maria)
    assert len(svc.get_records(juan, gen_id)) == 10


def test_delete_generation_removes_its_records(users):
    juan, _ = users
    gen_id = svc.create_generation(juan, ["email"], [{"email": "a@b.co"}] * 10)
    assert svc.delete_generation(juan, gen_id)
    assert svc.get_generations(juan) == []
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM fake_records").fetchone()[0] == 0


def test_clear_generations_only_clears_this_user(users):
    juan, maria = users
    svc.create_generation(juan, ["email"], [{"email": "a@b.co"}] * 10)
    svc.create_generation(maria, ["email"], [{"email": "a@b.co"}] * 10)
    svc.clear_generations(juan)
    assert svc.get_generations(juan) == [] and len(svc.get_generations(maria)) == 1


def test_dashboard_counts(users):
    juan, maria = users
    for _ in range(2):
        svc.create_generation(juan, ["email"], [{"email": "a@b.co"}] * 10)
    svc.create_generation(maria, ["email"], [{"email": "a@b.co"}] * 10)
    assert stats.count_generations(juan) == 2 and stats.count_generations(maria) == 1
    assert stats.generation_names(juan) == ["Gen 1", "Gen 2"]
    assert stats.generation_names(maria) == ["Gen 1"]
