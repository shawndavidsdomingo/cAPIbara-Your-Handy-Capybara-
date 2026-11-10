# Sprint 1 Log: Authentication and SQLite Foundation

**Dates:** Nov 10 to Nov 16, 2026
**Goal:** Replace the in-memory `demo_store.py` with a SQLite users table and salted password hashing, and tie the app to a real session.

## Pull requests

| # | Member | Branch | Summary | Status |
| --- | --- | --- | --- | --- |
| 1 | A | `db/sqlite-schema` | `db.py` with the connection helper (foreign keys on) and the users table | |
| 2 | A | `feat/auth-service` | `session.py` and `auth_service.py`: PBKDF2 hashing with a random salt, register, login, profile updates | |
| 3 | A | `test/auth-service` | pytest suite for the 10 authentication cases, using a temporary database | |
| 4 | B | `feat/auth-ui-wiring` | Login, Register, OTP and password dialogs use the service; `go_main()` requires a session; `init_db()` runs at startup | |
| 5 | B | `feat/auth-profile-session` | Dashboard and Profile read the user from the session; logout clears it | |
| 6 | B | `chore/remove-demo-store` | Delete `demo_store.py` | |
| 7 | B | `docs/sprint1-log-readme` | README and this log | |

Fill the Status column with the PR number and merge date as each one lands in `dev`.

## What changed

- Passwords are stored only as a 16-byte random salt and a PBKDF2-SHA256 hash (200,000 iterations). Two users with the same password get different hashes.
- Username and email are unique regardless of letter case.
- A wrong username and a wrong password show the same message: "Invalid username or password."
- Registration creates the account only after the email OTP is verified.
- Changing the password now asks for the current password, and the service rejects a new password that equals the old one.
- `go_main()` raises `PermissionError` when nobody is logged in, and logout clears the session.
- Window titles, the login heading and the README use the cAPIbara name.
- All validators (`is_valid_email`, `is_valid_username`, `mask_email`) moved from `demo_store.py` into `auth_service.py`.

## Decisions

- **No seeded test account.** A seeded password would sit in the source as plain text, so testers register through the app (the demo OTP makes this quick).
- **`stats.py` stays in memory for now.** The dashboard counters move to SQL queries in Sprints 2 to 4, as each feature gets its table.
- **Database path** is anchored to the folder that contains `db.py`, so it does not depend on where the app is launched from.

## Sprint 1 gate

Tick each item after testing it by hand.

- [ ] Register a new account; the OTP step works
- [ ] Log in with that account
- [ ] Close and reopen the app; the account still works
- [ ] The users table holds only salts and hashes (open `capibara.db` in DB Browser for SQLite)
- [ ] Change name, email and password in Profile
- [ ] A wrong password and an unknown username show the same error
- [ ] Logout returns to the login window and the main window cannot be reached without logging in
- [ ] `python -m pytest` passes

## GUI improvement slot

Planned for this sprint, not yet done: show/hide password toggle, inline field errors instead of one error line, Enter-key flow between fields, window sizing on small screens.

## Issues and notes

_Add bugs found, merge conflicts, and anything to carry into Sprint 2._

## Next sprint

Sprint 2 (Nov 17 to Nov 23): URL Shortening with the Ulvis API. Day 1 task for Member A is one real test call to confirm the parameter names and response fields.
