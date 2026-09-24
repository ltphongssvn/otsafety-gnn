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

import json
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping

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


CONTRACT = "command-outcome/v1"


def note(text: str) -> None:
    """Human-facing progress: stderr, never the payload channel."""
    sys.stderr.write(f"{text}\n")


# THE PAYLOAD IS JSON, AND THIS SCRIPT IS STANDARD LIBRARY ONLY: the contract
# model may not be installed where it runs, so the payload cannot be a Pydantic
# model. Mapping[str, object] is the honest stdlib type -- object rather than Any,
# so nothing is exempted from checking, and Mapping rather than dict because dict
# is INVARIANT in its value type: dict[str, str] is not a dict[str, object], which
# is what made an earlier alias need widening at every call site.
def emit(command: str, outcome: str, code: str, message: str, data: Mapping[str, object]) -> int:
    """The envelope on stdout, and the exit code the outcome carries.

    BUILT AS PLAIN DATA: this runs where the contract model may not be installed,
    so it uses only the standard library. A test validates the shape through the
    model, so a drift fails there rather than in a caller.
    """
    envelope = {
        "contract": CONTRACT,
        "command": command,
        "outcome": outcome,
        "code": code,
        "message": message,
        "data": data,
    }
    sys.stdout.write(json.dumps(envelope) + "\n")
    return {"success": 0, "failed": 1, "refused": 2}[outcome]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return emit(
            "site:check", "refused", "usage", "usage: check_site.py BASE_URL", {"arguments": args}
        )
    base = args[0].rstrip("/")
    checks: list[Mapping[str, object]] = []

    for path, expected in EXPECTED:
        got, _ = status(base + path)
        ok = got == expected
        checks.append({"check": path, "passed": ok, "detail": f"{got} (expected {expected})"})
        note(f"{'PASS' if ok else 'FAIL'} {got} {path} (expected {expected})")

    got, location = status(base + "/results")
    canonical = location in (base + "/results/", "/results/")
    redirects = got == 308 and canonical
    checks.append(
        {"check": "/results redirect", "passed": redirects, "detail": f"{got} -> {location}"}
    )
    note(f"{'PASS' if redirects else 'FAIL'} {got} /results -> {location}")

    _, body = status(base + "/evidence/")
    verdicts = body.count("data-verdict=")
    checks.append(
        {"check": "evidence verdicts", "passed": bool(verdicts), "detail": f"{verdicts} verdicts"}
    )
    note(f"{'PASS' if verdicts else 'FAIL'} evidence page carries {verdicts} verdicts")

    failed = [check["check"] for check in checks if not check["passed"]]
    if failed:
        return emit(
            "site:check",
            "refused",
            "site_assertions_failed",
            f"{len(failed)} of {len(checks)} assertions failed: "
            + ", ".join(str(f) for f in failed),
            {"base": base, "checks": checks, "failed": failed},
        )
    return emit(
        "site:check",
        "success",
        "site_serves_what_it_promises",
        f"all {len(checks)} assertions passed against {base}",
        {"base": base, "checks": checks, "failed": []},
    )


if __name__ == "__main__":
    raise SystemExit(main())
