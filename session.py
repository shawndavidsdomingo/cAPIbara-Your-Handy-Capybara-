"""Who is logged in right now (guide section 3.4)."""

_current = None


def login(user):
    global _current
    _current = dict(user)


def logout():
    global _current
    _current = None


def current():
    return _current


def require_login():
    if _current is None:
        raise PermissionError("Not logged in")
