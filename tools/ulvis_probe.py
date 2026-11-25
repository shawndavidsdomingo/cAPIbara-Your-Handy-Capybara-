"""Sprint 2 Day 1: see what Ulvis really sends back.

Run from the project root:   python tools/ulvis_probe.py
Then paste the whole output into the chat. It makes 4 requests (the API is
rate limited, so do not run it over and over). Not part of the app.
"""
import random
import string

import requests

ENDPOINT = "https://ulvis.net/API/write/get"
alias = "capi" + "".join(random.choices(string.ascii_lowercase, k=6))

CASES = [
    ("1. plain link", {"url": "https://example.com/capibara-test"}),
    ("2. link with alias", {"url": "https://example.com/with-alias", "custom": alias}),
    ("3. same alias again (should fail)", {"url": "https://example.com/other", "custom": alias}),
    ("4. bad url (should fail)", {"url": "not-a-link"}),
]

for title, params in CASES:
    print("=" * 60)
    print(title, params)
    try:
        r = requests.get(ENDPOINT, params=params, timeout=10)
        print("HTTP", r.status_code, "|", r.headers.get("Content-Type"))
        print(r.text[:600])
    except requests.RequestException as error:
        print("REQUEST FAILED:", error)
