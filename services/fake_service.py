"""Fake person data from the FakerAPI (https://fakerapi.it), plus storage.

ALL FakerAPI-specific code lives in FIELDS and fetch_persons(), so the rest of
the app never changes if the API does. The page only sees rows (dicts) or a
FakeDataError with a readable message.

How it works
- GET https://fakerapi.it/api/v1/persons?_quantity=10 (no API key). The reply is
  {"status": "OK", "code": 200, "total": 10, "data": [ {person}, ... ]}.
- Each person has firstname, lastname, email, phone, birthday, gender, website
  and an address object (street, city, zipcode, country, latitude, longitude).
- The user ticks which fields they want (FIELDS). Only those are kept and saved.

Storage: `fake_generations` (one row per batch) and `fake_records` (one row per
person, the chosen fields saved as JSON). Every query is scoped to the user's id.
"""
import json
import logging

import requests

from core.db import connection

log = logging.getLogger(__name__)

ENDPOINT = "https://fakerapi.it/api/v1/persons"
TIMEOUT = 20
MIN_RECORDS = 10           # project rule: at least 10 records
MAX_RECORDS = 1000         # FakerAPI's own limit per request
GENDERS = {"Any": None, "Male": "male", "Female": "female"}

MSG_NO_FIELDS = "Pick at least one kind of data to generate."
MSG_BAD_COUNT = f"Choose between {MIN_RECORDS} and {MAX_RECORDS} records."
MSG_NO_CONNECTION = "Could not reach the data service. Check your connection."
MSG_TIMEOUT = "The data service took too long. Try again."
MSG_RATE_LIMIT = "Too many requests. Please wait a moment and try again."
MSG_UNEXPECTED = "The data service sent an unexpected reply."


class FakeDataError(Exception):
    """Message is safe to show to the user."""


# ---------- The fields the user can pick ----------

def _text(value):
    return "" if value is None else str(value).strip()


def _top(key):
    return lambda person: _text(person.get(key))


def _address(key):
    def get(person):
        address = person.get("address")
        return _text(address.get(key)) if isinstance(address, dict) else ""
    return get


def _full_name(person):
    return f"{_text(person.get('firstname'))} {_text(person.get('lastname'))}".strip()


# key -> (column label, function that reads it from one person in the reply)
FIELDS = {
    "full_name":  ("Full Name",  _full_name),
    "first_name": ("First Name", _top("firstname")),
    "last_name":  ("Last Name",  _top("lastname")),
    "address":    ("Address",    _address("street")),
    "city":       ("City",       _address("city")),
    "zip_code":   ("Zip Code",   _address("zipcode")),
    "country":    ("Country",    _address("country")),
    "birthdate":  ("Birthdate",  _top("birthday")),
    "mobile":     ("Mobile",     _top("phone")),
    "email":      ("Email",      _top("email")),
    "gender":     ("Gender",     _top("gender")),
    "website":    ("Website",    _top("website")),
    "latitude":   ("Latitude",   _address("latitude")),
    "longitude":  ("Longitude",  _address("longitude")),
}
# ticked when the page opens (10 fields, as the project requires)
DEFAULT_FIELDS = ["full_name", "address", "birthdate", "mobile", "email",
                  "gender", "city", "zip_code", "country", "website"]


def label(key):
    return FIELDS[key][0]


# ---------- FakerAPI provider ----------

def fetch_persons(count, field_keys, gender=None):
    """Ask FakerAPI for `count` people. Returns a list of {field_key: text}."""
    if not field_keys or any(key not in FIELDS for key in field_keys):
        raise FakeDataError(MSG_NO_FIELDS)
    if not MIN_RECORDS <= count <= MAX_RECORDS:
        raise FakeDataError(MSG_BAD_COUNT)

    params = {"_quantity": count, "_locale": "en_US"}
    if gender:
        params["_gender"] = gender
    try:
        reply = requests.get(ENDPOINT, params=params, timeout=TIMEOUT)
        if reply.status_code == 429:
            raise FakeDataError(MSG_RATE_LIMIT)
        reply.raise_for_status()
        payload = reply.json()
    except FakeDataError:
        raise
    except requests.exceptions.Timeout:
        raise FakeDataError(MSG_TIMEOUT)
    except ValueError:                        # the reply was not JSON
        log.warning("FakerAPI reply was not JSON")
        raise FakeDataError(MSG_UNEXPECTED)
    except requests.exceptions.RequestException:
        raise FakeDataError(MSG_NO_CONNECTION)

    people = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(people, list) or not people:
        log.warning("Unexpected FakerAPI reply: %.500s", payload)
        raise FakeDataError(MSG_UNEXPECTED)
    return [{key: FIELDS[key][1](person) for key in field_keys}
            for person in people if isinstance(person, dict)]


def generate_and_save(user_id, count, field_keys, gender=None):
    """Fetch and store one batch in a single step (the page runs this on a
    background thread, so a closing app can wait for it). Returns the batch id."""
    rows = fetch_persons(count, field_keys, gender)
    return create_generation(user_id, field_keys, rows)


# ---------- Storage (every query is scoped to the user) ----------

def create_generation(user_id, field_keys, rows):
    """Store one batch and all its records in one transaction. Returns its id."""
    with connection() as conn:
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM fake_generations "
            "WHERE user_id = ?", (user_id,)).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO fake_generations (user_id, number, fields) VALUES (?, ?, ?)",
            (user_id, number, json.dumps(list(field_keys))))
        generation_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO fake_records (generation_id, data) VALUES (?, ?)",
            [(generation_id, json.dumps(row)) for row in rows])
        return generation_id


def get_generations(user_id):
    """The user's batches, oldest first: id, name ("Gen 3"), time, fields, total."""
    sql = ("SELECT g.id, g.number, g.fields, "
           "datetime(g.created_at, 'localtime') AS created_at, "
           "COUNT(r.id) AS total "
           "FROM fake_generations g "
           "LEFT JOIN fake_records r ON r.generation_id = g.id "
           "WHERE g.user_id = ? GROUP BY g.id ORDER BY g.id")
    with connection() as conn:
        rows = conn.execute(sql, (user_id,)).fetchall()
    return [{"id": row["id"], "name": f"Gen {row['number']}",
             "time": row["created_at"], "fields": json.loads(row["fields"]),
             "total": row["total"]} for row in rows]


def get_records(user_id, generation_id):
    """The records of one batch, in the order they were generated."""
    sql = ("SELECT r.data FROM fake_records r "
           "JOIN fake_generations g ON g.id = r.generation_id "
           "WHERE g.id = ? AND g.user_id = ? ORDER BY r.id")
    with connection() as conn:
        return [json.loads(row["data"])
                for row in conn.execute(sql, (generation_id, user_id)).fetchall()]


def delete_generation(user_id, generation_id):
    """Its records go too (ON DELETE CASCADE). True if a batch was deleted."""
    with connection() as conn:
        cursor = conn.execute(
            "DELETE FROM fake_generations WHERE id = ? AND user_id = ?",
            (generation_id, user_id))
        return cursor.rowcount > 0


def clear_generations(user_id):
    with connection() as conn:
        conn.execute("DELETE FROM fake_generations WHERE user_id = ?", (user_id,))
