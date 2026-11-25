<p align="center">
  <img src="assets/logo.png" alt="cAPIbara Logo" width="160" />
</p>

# cAPIbara: Your Handy Capybara

A desktop utility app built with Python, PySide6 and SQLite for the ITL313-18 (SIA 2 Lab) final term mini project. The name is a pun on API, because the app talks to outside services.

## Features

| Feature | Status |
| --- | --- |
| Register and log in with salted, hashed passwords (SQLite) | Done (Sprint 1) |
| Profile: change name, email (OTP) and password (OTP) | Done (Sprint 1) |
| URL Shortening through the Ulvis API with history | Sprint 2 |
| SMS and Email drafts, sending and history | Sprint 3 |
| Fake Data generation with a customization panel | Sprint 4 |
| Dashboard totals from real database queries | Sprints 2 to 4 |

The OTP dialog runs in demo mode: the code is shown on screen and no email is sent.

## Tech stack

- Python 3.10+
- PySide6 (GUI)
- SQLite through the built-in `sqlite3` module (nothing extra to install)
- `requests` (Ulvis API), `openpyxl` (Excel export), `pytest` (tests)

## Requirements

You need Python 3.10 or newer. Check with `python --version`. These packages are installed from `requirements.txt`:

| Package | Used for | Needed from |
| --- | --- | --- |
| PySide6 | The GUI (Qt for Python) | Now |
| requests | Calling the Ulvis URL shortening API | Sprint 2 |
| openpyxl | Excel export of generated fake data | Now (Fake Data page) |
| pytest | Running the tests | Now |

`sqlite3` is built into Python, so SQLite needs no install. `requirements.txt` contains:

```
PySide6
openpyxl
requests
pytest
```

Optional: install [DB Browser for SQLite](https://sqlitebrowser.org/) to look inside `capibara.db` while testing.

## Setup

```
git clone <repo-url>
cd <repo-folder>
git checkout dev
python -m venv venv
venv\Scripts\activate          (Windows)
source venv/bin/activate       (macOS / Linux)
pip install -r requirements.txt
```

## Run

Run from the project root (the folder that contains `main.py`):

```
python main.py
```

`capibara.db` is created next to `main.py` on first launch. There is no default account, so click **Create an account** and register. The demo OTP code is shown in the dialog.

## Run the tests

```
python -m pytest
```

Tests use a temporary database, so your real `capibara.db` is never touched.

## Project structure

```
main.py              entry point, creates the database, applies the theme
navigation.py        go_login / go_register / go_main (main needs a session)
db.py                SQLite connection helper and schema
session.py           the currently logged-in user
auth_service.py      register, login, profile updates, password hashing
theme.py             global stylesheet
widgets.py           make_label / make_input / make_button helpers
dialogs.py           OTP, new email, new password and sent dialogs
login_window.py
register_window.py
main_window.py       sidebar and stacked pages
pages/               dashboard, url, messages, fake data, profile
tests/               pytest files
docs/                sprint logs
```

Rules the code follows: no plain-text passwords, every SQL statement uses `?` placeholders, and the GUI only calls service functions, never SQL directly.

## Git workflow

`feature branch -> pull request -> dev -> release PR -> main`

- Branch from `dev`, never from `main` or another feature branch.
- Branch prefixes: `feat/`, `fix/`, `db/`, `test/`, `docs/`, `refactor/`, `chore/`.
- Every PR is reviewed by the other member and merged into `dev`.
- `capibara.db`, `.env` files and API keys are never committed.

## Team

| Role | Member | Responsibility |
| --- | --- | --- |
| A | Domingo, Shawn David S. | Data and Services: schema, hashing, services, API, tests |
| B | Gloria, Jan-Neo S. | UI and Integration: windows, pages, dialogs, theme, docs |

## Documentation

- [Sprint 1 log](docs/sprint1-log.md)
