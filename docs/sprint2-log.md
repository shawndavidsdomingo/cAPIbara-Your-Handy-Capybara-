# Sprint 2 Log: URL Shortening (Ulvis API)

**Dates:** Nov 17 to Nov 23, 2026
**Goal:** Replace the dummy short.ly generator with the real Ulvis API and store each user's links.

## Pull requests

| # | Member | Branch | Summary | Status |
| --- | --- | --- | --- | --- |
| 1 | A | `db/links-schema` | `links` and `link_clicks` tables (clicks cascade-delete with their link) | |
| 2 | A | `feat/url-service-ulvis` | `url_service.py`: `ulvis_shorten()` provider, URL validation, save, list, delete and click functions; dashboard link count becomes a SQL COUNT in `stats.py` | |
| 3 | A | `test/url-service` | pytest suite for validation, provider replies and errors (network faked) and per-user storage | |
| 4 | A | `refactor/remove-alias` | Custom aliases removed from the service and schema; reply parser made tolerant of JSON, plain text and XML | |
| 5 | B | `feat/url-ui-history` | History loaded from the database, Open / Copy / Delete per row, empty state, worker thread with a "Shortening…" state | |
| 6 | A | `feat/url-reuse-existing` | `find_link`, `bump_link`; saving a URL the user already has moves that row to the top instead of adding a duplicate | |
| 7 | B | `feat/url-move-to-top` | URL page reuses an existing link without calling Ulvis and shows "Already shortened. Moved to the top." | |
| 8 | A | `feat/url-arrange-links` | `arrange_links()`: search by short or original link, sort by short, original or date (default / A to Z or earliest / Z to A or latest) | |
| 9 | B | `feat/url-click-copy-sort-search` | Click a short or original link to copy it, sortable column headers, search box | |
| 10 | B | `feat/close-confirm-guard` | Closing the app asks "Are you sure?"; a running request is allowed to finish and its link is saved before the app exits | |
| 11 | B | `docs/sprint2-log` | This log | |

## Ulvis API notes (confirmed vs. still to verify)

Confirmed from the Ulvis GitHub README:

- Endpoint: `GET https://ulvis.net/API/write/get`, no API key.
- Request parameters: `url`, `custom`, `type`, `private`, `password`, `uses`, `expire`, `via`.

Rate limit: reported as 100 requests per hour per IP by third-party directories (unconfirmed).

Verified with `tools/ulvis_probe.py` on _date_ (paste the raw output below):

```
(paste the probe output here)
```

Result: success field = ___ , error field = ___ , JSON needs extra parameter? ___

## What changed

- URLs must start with http:// or https://, checked before any network call.
- **Custom aliases were dropped.** A duplicate alias made Ulvis return an error, so the page only sends the URL and every request gets a generated short link.
- The request runs on a QThread, so the window never freezes. A failed request saves nothing.
- Every Ulvis detail lives in `ulvis_shorten()` and its helpers; the rest of the app only sees a short URL string or a `ShortenError` with a readable message.
- The reply is read tolerantly: the service looks for a ulvis.net short link in the raw reply (JSON, plain text or XML, with escaped slashes handled). An unrecognised reply is logged as a warning in the Run console.
- **Shortening the same URL again** does not call Ulvis and does not add a row. The existing row moves to the top, keeps its click count, and the page says "Already shortened. Moved to the top." The match is per user and exact, so the same link with a different query string is a new link. The history column is named "Shortened" because it shows when the link was last shortened (local time).
- **Click to copy:** clicking a short or original link in the history copies it (hover underlines it and shows a tooltip). The Copy button stays.
- **Sort:** click the Short URL, Original URL or Shortened header. Short and original go default, A to Z, Z to A; Shortened goes default, earliest, latest. A ▲ or ▼ marks the active column. Default is the order of last use, newest first.
- **Search:** the box above the history matches the short or the original link in any letter case. Search and sort stay when a link is opened or deleted, and both reset when a new or reused link is added so it shows at the top.
- Clicks are logged locally when "Open" is pressed, so the feature does not depend on any Ulvis statistics endpoint.
- Every query filters by the logged-in user's id; deleting a link also deletes its click history.
- Dashboard "Links shortened" is now `SELECT COUNT(*) FROM links WHERE user_id = ?`, so it counts distinct URLs.
- **Closing the app** asks "Are you sure you want to close the app?" (default No). If a request is running, the dialog adds that the app will close once it finishes. The window then waits (wait cursor), the new link is saved, and the app exits. Pages opt in with `is_busy()` and `shutdown()`.
- **Logout** does not ask, because it is a deliberate action. It closes the window the same way, so a running request still finishes and is saved.
- The login and register windows do not ask before closing.

## Sprint 2 gate

- [ ] A real Ulvis short link is created, saved and still listed after restarting the app
- [ ] A duplicate alias shows "That alias is already taken..."
- [ ] A bad URL shows a readable error and nothing is saved
- [ ] With the internet off, the error is readable and the window does not freeze
- [ ] Open launches the browser and the click count goes up
- [ ] Shortening the same URL again moves its row to the top, with no duplicate and the same click count
- [ ] Clicking a short or original link copies it; the Copy button still works
- [ ] Each sortable header cycles through its three states
- [ ] Search finds a link by its short or original text, and shows a message when nothing matches
- [ ] Delete removes the row and the dashboard count drops
- [ ] Another account cannot see these links
- [ ] Closing the window asks "Are you sure you want to close the app?"; No keeps the app open
- [ ] Closing while a link is being shortened waits for it, saves the link, then exits
- [ ] Logout does not show the close question
- [ ] `python -m pytest` passes

## Issues and notes

_Add anything found while testing against the real API._

## Next sprint

Sprint 3 (Nov 24 to Nov 30): Email and SMS. The SMS and email providers still need to be chosen before it starts.
