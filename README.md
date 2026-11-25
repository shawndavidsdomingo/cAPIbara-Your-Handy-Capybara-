# cAPIbara: Your Handy Capybara

A desktop utility app built with Python, PySide6 and SQLite for the ITL313-18 (SIA 2 Lab) final term mini project. The name is a pun on API, because the app talks to outside services.

The project follows **3B. Utilities** and covers all three options in one app: **3B.1 URL Shortening**, **3B.2 SMS and Email** and **3B.3 Fake Data Generation**.

## Features

| Feature | Details | Status |
| --- | --- | --- |
| Register and log in | Salted PBKDF2-SHA256 passwords in SQLite, login with username or email, Terms and Conditions on sign-up | Done |
| Email verification (OTP) | 6-digit code emailed through Brevo on register, email change and password change | Done |
| Forgot username or password | Find the account by email or username, verify with a code, then set a new password | Done |
| Profile | Change name, email (OTP to the new address) and password (OTP to the current address) | Done |
| URL Shortening | Ulvis API with is.gd as automatic fallback, history, search, sort, copy, open, delete and local click counts | Done |
| SMS and Email | Send emails (Brevo) and texts (TextBee), save drafts, pick recipients from contacts, sent history | Done |
| Contacts | Personal address book (name plus mobile and/or email), used by the SMS and Email pickers | Done |
| Fake Data | FakerAPI, 14 selectable fields, 10 to 1000 records per batch, stored per user, rename, export to Excel, CSV or JSON | Done |
| Dashboard | Totals and 7-day activity charts from real database queries | Done |
| Zoom | Ctrl + mouse wheel, or Ctrl and + / - / 0, redraws the whole app larger or smaller (90% to 200%) | Done |
| Full screen | F11 to switch, Esc to leave | Done |

## Tech stack

- Python 3.10+
- PySide6 (GUI, Qt for Python)
- SQLite through the built-in `sqlite3` module
- `requests` (all API calls), `openpyxl` (Excel export), `pytest` (tests)

## Requirements

### System

| Requirement | Notes |
| --- | --- |
| Python 3.10 or newer | Check with `python --version` |
| Internet connection | Needed for shortening links, sending messages, fake data and verification codes |
| Android phone with the TextBee app | Only for sending real SMS (see [TextBee](#textbee-sms)) |

### Python packages

Installed from `requirements.txt`:

| Package | Used for |
| --- | --- |
| PySide6 | The GUI |
| requests | Calling the Ulvis, is.gd, FakerAPI, Brevo and TextBee APIs |
| openpyxl | Excel (`.xlsx`) export of generated fake data |
| pytest | Running the tests |

`sqlite3`, `hashlib`, `hmac`, `json`, `csv` and `logging` are part of Python, so nothing extra is needed for them.

```
PySide6
openpyxl
requests
pytest
```

Optional: install [DB Browser for SQLite](https://sqlitebrowser.org/) to look inside `capibara.db` while testing.

## APIs used

| Service | Used for | API key | Where the code lives |
| --- | --- | --- | --- |
| [Ulvis](https://ulvis.net) | URL shortening (first choice) | No | `services/url_service.py` (`ulvis_shorten`) |
| [is.gd](https://is.gd) | URL shortening (fallback when Ulvis fails) | No | `services/url_service.py` (`isgd_shorten`) |
| [FakerAPI](https://fakerapi.it) | Fake person data | No | `services/fake_service.py` (`fetch_persons`) |
| [Brevo](https://www.brevo.com) | Sending emails and OTP codes | Yes (`BREVO_API_KEY`) | `services/message_service.py` (`send_email`) |
| [TextBee](https://textbee.dev) | Sending SMS from your own Android phone | Yes (`TEXTBEE_API_KEY`) | `services/message_service.py` (`send_sms`) |

### Endpoints

| Service | Request |
| --- | --- |
| Ulvis | `GET https://ulvis.net/API/write/get?url=<link>` |
| is.gd | `GET https://is.gd/create.php?format=json&url=<link>` |
| FakerAPI | `GET https://fakerapi.it/api/v1/persons?_quantity=<n>&_locale=en_US[&_gender=male\|female]` |
| Brevo | `POST https://api.brevo.com/v3/smtp/email` (header `api-key`) |
| TextBee | `POST https://api.textbee.dev/api/v1/gateway/send-sms` and `GET .../gateway/messages?smsBatchId=<id>` (header `x-api-key`) |

All provider-specific code is kept in one service file per provider. The GUI only calls service functions and shows readable error messages, so an API change never reaches the pages.

## Configuration

Secrets are read from environment variables or from a `.env` file placed next to `main.py` (or next to the `.exe`). A real environment variable always wins over the file. **Never commit `.env`.**

Create `.env`:

```
BREVO_API_KEY=your-brevo-key
TEXTBEE_API_KEY=your-textbee-key
TEXTBEE_DEVICE_ID=your-device-id
SENDER_EMAIL=noreply@capibara-shawn-neo.online
SENDER_NAME=cAPIbara
LOGO_URL=https://example.com/logo.png
```

| Setting | Required | Default | Purpose |
| --- | --- | --- | --- |
| `BREVO_API_KEY` | For real email and OTP | none | Brevo API key. Without it, email stays in demo mode |
| `TEXTBEE_API_KEY` | For real SMS | none | TextBee API key. Without it, SMS stays in demo mode |
| `TEXTBEE_DEVICE_ID` | No | your default device | Picks which phone sends the text |
| `TEXTBEE_BASE_URL` | No | `https://api.textbee.dev/api/v1` | TextBee API address |
| `SENDER_EMAIL` | No | `noreply@capibara-shawn-neo.online` | Address emails are sent from (must be a Brevo-authorized sender) |
| `SENDER_NAME` | No | `cAPIbara` | Sender name shown to recipients |
| `LOGO_URL` | No | none | Public `https://` image for the email header. Anything else is ignored |

**Demo mode:** with no API keys the app still runs. The OTP dialog shows the code on screen instead of emailing it, and SMS and Email sending is not performed.

### Brevo (email)

1. Create a Brevo account and generate an API key (SMTP and API section).
2. Authorize the sender address or domain. If you restrict the key by IP address, add your own IP, or sending fails with a "refused" error.
3. Put the key in `BREVO_API_KEY`.

### TextBee (SMS)

1. Create a TextBee account and generate an API key.
2. Install the TextBee app on an Android phone, sign in and register the device.
3. Keep the phone on, online, with signal and load while the app sends.
4. Put the key in `TEXTBEE_API_KEY` (and the device id in `TEXTBEE_DEVICE_ID` if you have several phones).

Texts go to Philippine mobile numbers only (`09XXXXXXXXX`, sent as `+639XXXXXXXXX`). The recipient sees the phone's number, not yours.

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

Then create the `.env` file described above.

## Run

Run from the project root (the folder that contains `main.py`):

```
python main.py
```

On first launch the app creates two files next to `main.py`:

| File | What it holds |
| --- | --- |
| `capibara.db` | All accounts, links, messages, contacts and fake data |
| `settings.json` | The zoom level (belongs to the computer, not to an account) |

There is no default account, so click **Create an account** and register.

## Run the tests

```
python -m pytest
```

Tests use a temporary database and fake every network call, so your real `capibara.db` is never touched and no real email, text or API request is made.

| Test file | Covers |
| --- | --- |
| `test_auth_service.py` | Registration, hashing, login, profile and password changes, session guard |
| `test_url_service.py` | Ulvis and is.gd handling, link storage, search and sort |
| `test_message_service.py` | Brevo email, HTML footer and logo, OTP email, `.env` parsing |
| `test_sms.py` | TextBee requests, errors, phone status polling, number validation |
| `test_message_storage.py` | Drafts, sent messages, per-user isolation |
| `test_fake_service.py` | FakerAPI parsing, errors, batches, rename and delete |
| `test_stats_activity.py` | Dashboard 7-day activity numbers |

## Project structure

```
main.py                 entry point: creates the database, applies the theme
assets/                 logo.png, icon.png, icon.ico
core/
    config.py           reads .env and environment variables
    db.py               SQLite connection helper and schema
    paths.py            finds the app folder (also when packaged as .exe)
    session.py          the currently logged-in user
    zoom.py             zoom levels, remembered in settings.json
services/               no GUI code, no SQL in the UI
    auth_service.py     register, login, profile updates, password hashing
    url_service.py      Ulvis, is.gd and link storage
    message_service.py  Brevo, TextBee and draft/sent storage
    contact_service.py  contacts storage and checks
    fake_service.py     FakerAPI and fake data storage
    stats.py            dashboard totals and activity
ui/
    navigation.py       go_login / go_register / go_main, zoom redraw
    login_window.py, register_window.py, main_window.py
    dialogs.py          OTP, new email, new password, contact and message dialogs
    forgot_dialog.py    forgot username or password flow
    rename_dialog.py    rename a fake data generation
    terms_dialog.py     Terms and Conditions
    theme.py            colours and global stylesheet
    widgets.py          shared label, input, button and zoom helpers
    charts.py           bar and donut charts drawn with QPainter
    workers.py          runs network calls on a background thread
    pages/              dashboard, url, messages, contacts, fake data, profile
tests/                  pytest files
docs/                   guide
```

## Security notes

- Passwords are never stored as typed: each one gets a random 16-byte salt and a PBKDF2-HMAC-SHA256 hash (200,000 iterations).
- Wrong username and wrong password give the same login error.
- Every SQL statement uses `?` placeholders, and every query is scoped to the logged-in user's id.
- API keys live in `.env` or the environment, are never logged, and never appear in error messages.
- Text typed into emails is HTML-escaped before it is sent.
- The GUI only calls service functions, never SQL directly.

## Known limitations

- Internet is required for almost everything except login and browsing saved data.
- Outside services can be slow, rate-limited, blocked or offline. Ulvis sometimes answers scripts with a Cloudflare check page, which is why is.gd is the fallback.
- Short links belong to Ulvis and is.gd and may expire. Click counts only count links opened from inside the app.
- "Sent" for a text means the phone accepted it, not that it was delivered.
- Email may arrive late or land in spam, and Brevo's sending quota applies.
- The app can only send, not receive.
- Data is stored only in the local `capibara.db`: no cloud backup and no syncing.
- Account recovery needs access to the email on the account.

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
