"""Running totals for the dashboard (in memory, GUI-only sprint).
Next sprint these become SQL COUNT queries instead."""

_data = {"emails": 0, "sms": 0, "links": 0, "generations": []}


def reset():
    _data.update(emails=0, sms=0, links=0, generations=[])


def record_sent(kind):                 # kind is "SMS" or "Email"
    _data["sms" if kind == "SMS" else "emails"] += 1


def record_link():
    _data["links"] += 1


def record_generation(name):           # e.g. "Gen 3"
    _data["generations"].append(name)


def get():
    return _data