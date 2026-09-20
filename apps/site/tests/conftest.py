# apps/site/tests/conftest.py
"""The built site, served for the duration of a test session.

THE FIXTURE MOVED HERE THE MOMENT A SECOND MODULE NEEDED IT. Importing it across
test modules is a relative import with no parent package, which pytest reports
as a collection error -- a broken test rather than a failing one, and a broken
test proves nothing about the thing under test.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SITE = REPO_ROOT / "apps" / "site"
BASE_URL = "http://localhost:4321"


@pytest.fixture(scope="session")
def site_server() -> Iterator[str]:
    """Build the site, serve it, and stop the server even when a test fails."""
    if not (SITE / "package.json").is_file():
        pytest.fail(f"no site at {SITE}: run `mise run site:install` after scaffolding")

    subprocess.run(["bun", "run", "build"], cwd=SITE, check=True)  # noqa: S603, S607
    proc = subprocess.Popen(  # noqa: S603, S607
        ["bun", "run", "preview", "--port", "4321"], cwd=SITE
    )
    try:
        for _ in range(60):
            if proc.poll() is not None:
                pytest.fail("the preview server exited before it served anything")
            try:
                import urllib.request

                urllib.request.urlopen(BASE_URL, timeout=1)  # noqa: S310
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            pytest.fail(f"the preview server never answered on {BASE_URL}")
        yield BASE_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)
