<p align="center">
  <img src="assets/logo.png" alt="cAPIbara Logo" width="160" />
</p>

# cAPIbara: Your Handy Capybara

A desktop utility app built with Python, PySide6 and SQLite for the ITL313-18 (SIA 2 Lab) final term mini project. The name is a pun on API, because the app talks to outside services.

## Features

| Feature | Service used |
| --- | --- |
| Register and log in with salted, hashed passwords (SQLite) | built in |
| Email one-time code (OTP) when registering and when changing email or password | Brevo |
| Forgot username or password: code sent to the account's email, then set a new password | Brevo |
| Profile: change name, email (OTP) and password (OTP) | built in |
| URL Shortening with history, search, sorting and local click counts | Ulvis, with is.gd as a backup |
| SMS and Email: drafts, sending and history | TextBee (SMS), Brevo (Email) |
| Contacts: a personal address book the SMS and Email tabs pick from | built in |
| Fake Data generation: 10+ fields, 10 to 1000 records per batch, saved, renamable, exported to Excel or CSV | FakerAPI |
| Dashboard: totals, a 7-day activity chart and an all-time donut chart, all from SQL | built in |
| Zoom (90% to 200%) with Ctrl + mouse wheel or Ctrl + / - / 0, remembered between launches | built in |
| Terms and Conditions shown at sign-up | built in |

Without a `BREVO_API_KEY` the OTP dialog runs in demo mode: the code is shown on screen and no email is sent. Without a `TEXTBEE_API_KEY` the SMS tab stays in demo mode too.

For the forgot-password flow, an unknown email or username gets the same "code sent" screen as a real one, so the app never reveals which accounts exist.

## Tech stack

- Python 3.10+
- PySide6 (GUI)
- SQLite through the built-in `sqlite3` module (nothing extra to install)
- `requests` (Ulvis, is.gd, FakerAPI, Brevo, TextBee), `openpyxl` (Excel export), `pytest` (tests)

## Requirements

You need Python 3.10 or newer. Check with `python --version`. These packages are installed from `requirements.txt`:

| Package | Used for |
| --- | --- |
| PySide6 | The GUI (Qt for Python) |
| requests | Calling the outside APIs |
| openpyxl | Excel export of generated fake data |
| pytest | Running the tests |

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

### Settings and secrets (`.env`)

Create a `.env` file next to `main.py` (it is never committed). All keys are optional; a missing key only turns that feature into demo mode or shows a clear message.

```
BREVO_API_KEY=            # sends emails and OTP codes
SENDER_EMAIL=             # address the app sends from (default noreply@capibara-shawn-neo.online)
SENDER_NAME=              # default: cAPIbara
LOGO_URL=                 # public https link to a logo shown in emails
TEXTBEE_API_KEY=          # sends SMS from your Android phone
TEXTBEE_DEVICE_ID=        # which phone to use (optional)
TEXTBEE_BASE_URL=         # default: https://api.textbee.dev/api/v1
```

## Run

Run from the project root (the folder that contains `main.py`):

```
python main.py
```

`capibara.db` (data) and `settings.json` (zoom level) are created next to `main.py` on first launch. There is no default account, so click **Create an account** and register.

## Run the tests

```
python -m pytest
```

Tests use a temporary database, so your real `capibara.db` is never touched.

## Project structure

```
main.py                 entry point: creates the database, applies the theme
assets/                 logo.png, icon.png
core/
  config.py             settings and secrets from the environment or .env
  db.py                 SQLite connection helper and schema
  paths.py              app folder and bundled-resource paths
  session.py            the currently logged-in user
  zoom.py               zoom level, saved in settings.json
services/               all logic and SQL; the GUI never touches SQL
  auth_service.py       register, login, profile updates, password hashing, reset
  url_service.py        Ulvis and is.gd shortening, link storage and clicks
  message_service.py    Brevo emails, TextBee texts, drafts and history
  contact_service.py    contacts: checks and storage
  fake_service.py       FakerAPI fetching, generations and records
  stats.py              dashboard totals and activity per day
ui/
  navigation.py         go_login / go_register / go_main and set_zoom
  theme.py              global stylesheet and colours (scaled by zoom)
  widgets.py            label, input, button helpers and zoom shortcuts
  workers.py            Task: runs a function on a background thread
  charts.py             bar and donut charts drawn with QPainter
  dialogs.py            OTP, new email, new password, contact and sent dialogs
  forgot_dialog.py      forgot username or password flow
  rename_dialog.py      rename a Fake Data generation
  terms_dialog.py       Terms and Conditions
  login_window.py
  register_window.py
  main_window.py        sidebar and stacked pages
  pages/                dashboard, url, msg (SMS and Email), contacts, fake data, profile
tests/                  pytest files
docs/                   sprint logs
```

Rules the code follows: no plain-text passwords, every SQL statement uses `?` placeholders, the GUI only calls service functions, and network calls always run on a background thread.

## Git workflow

`feature branch -> pull request -> dev -> release PR -> main`

- Branch from `dev`, never from `main` or another feature branch.
- Branch prefixes: `feat/`, `fix/`, `db/`, `test/`, `docs/`, `refactor/`, `chore/`.
- Every PR is reviewed by the other member and merged into `dev`.
- `capibara.db`, `settings.json`, `.env` files and API keys are never committed.

## Team

| Role | Member | Responsibility |
| --- | --- | --- |
| A | Domingo, Shawn David S. | Data and Services: schema, hashing, services, API, tests |
| B | Gloria, Jan-Neo S. | UI and Integration: windows, pages, dialogs, theme, docs |