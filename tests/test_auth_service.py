import pytest

import auth_service as auth
import db
import navigation
import session


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    session.logout()


def make_user(username="juan", email="juan@example.com", password="secret123"):
    return auth.register_user(username, "Juan Cruz", email, password)


def test_01_register_valid_user_stores_hash_not_password():
    user_id = make_user()
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    assert row["username"] == "juan"
    assert row["password_hash"] != "secret123"
    assert "secret123" not in [str(value) for value in tuple(row)]
    assert len(row["salt"]) == 32


def test_02_duplicate_username_rejected():
    make_user()
    with pytest.raises(ValueError):
        make_user(username="JUAN", email="other@example.com")   # case-insensitive


def test_03_duplicate_email_rejected():
    make_user()
    with pytest.raises(ValueError):
        make_user(username="maria")


def test_04_short_password_rejected():
    with pytest.raises(ValueError):
        make_user(password="short")


def test_05_correct_login_sets_session():
    make_user()
    user = auth.verify_login("juan", "secret123")
    assert user is not None and "password_hash" not in user
    session.login(user)
    assert session.current()["username"] == "juan"


def test_06_wrong_password_gives_no_session():
    make_user()
    assert auth.verify_login("juan", "wrongpass") is None
    assert session.current() is None


def test_07_unknown_username_same_result():
    assert auth.verify_login("ghost", "secret123") is None


def test_08_same_password_gives_different_salt_and_hash():
    make_user()
    make_user(username="maria", email="maria@example.com")
    with db.connection() as conn:
        rows = conn.execute("SELECT salt, password_hash FROM users").fetchall()
    assert rows[0]["salt"] != rows[1]["salt"]
    assert rows[0]["password_hash"] != rows[1]["password_hash"]


def test_09_change_password():
    user_id = make_user()
    auth.update_password(user_id, "secret123", "newsecret456")
    assert auth.verify_login("juan", "secret123") is None
    assert auth.verify_login("juan", "newsecret456") is not None


def test_09b_change_password_rules():
    user_id = make_user()
    with pytest.raises(ValueError):
        auth.update_password(user_id, "wrong-old", "newsecret456")
    with pytest.raises(ValueError):
        auth.update_password(user_id, "secret123", "secret123")
    with pytest.raises(ValueError):
        auth.update_password(user_id, "secret123", "short")


def test_10_main_window_blocked_without_session():
    with pytest.raises(PermissionError):
        session.require_login()
    with pytest.raises(PermissionError):
        navigation.go_main()


def test_profile_updates():
    user_id = make_user()
    other = make_user(username="maria", email="maria@example.com")
    auth.update_name(user_id, "Juan D. Cruz")
    assert auth.get_user(user_id)["full_name"] == "Juan D. Cruz"
    with pytest.raises(ValueError):
        auth.update_name(user_id, "   ")
    with pytest.raises(ValueError):
        auth.update_email(user_id, "maria@example.com")
    auth.update_email(user_id, "new@example.com")
    assert auth.get_user(user_id)["email"] == "new@example.com"
    assert other != user_id
