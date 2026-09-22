#!/usr/bin/env python3
"""Assert the published site answers correctly, against any base URL.

ONE DEFINITION OF "THE SITE WORKS", used before a deploy against the local image
and after it against production. It replaces shell one-liners that failed twice
in one session on zsh word-splitting: `set -- $p` does not split in zsh, so every
check requested a URL containing a space and reported 000 for a healthy site.

HTTPS IS VERIFIED BY urllib ITSELF: a certificate that does not name the host
fails the request, so a passing run against production proves the certificate.

THE EVIDENCE CHECK catches the failure this deployment was designed around. The
site is built where .artifacts/ lives because a build elsewhere publishes empty
evidence pages; a page with no verdicts means exactly that happened.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

EXPECTED = [
    ("/", 200),
    ("/results/", 200),
    ("/evidence/", 200),
    ("/architecture/", 200),
    ("/no-such-page", 404),
]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def status(url: str) -> tuple[int, str]:
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(url, timeout=15) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Location", "") or ""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_site.py BASE_URL", file=sys.stderr)
        return 2
    base = sys.argv[1].rstrip("/")
    failures = 0
    for path, expected in EXPECTED:
        got, _ = status(base + path)
        ok = got == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} {got} {path} (expected {expected})")

    got, location = status(base + "/results")
    canonical = location in (base + "/results/", "/results/")
    failures += not (got == 308 and canonical)
    print(f"{'PASS' if got == 308 and canonical else 'FAIL'} {got} /results -> {location}")

    _, body = status(base + "/evidence/")
    verdicts = body.count("data-verdict=")
    failures += verdicts == 0
    print(f"{'PASS' if verdicts else 'FAIL'} evidence page carries {verdicts} verdicts")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
