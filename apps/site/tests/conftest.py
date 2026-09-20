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


def _seed_evidence() -> None:
    """Guarantee one failing verdict and one run record exist before the build.

    .artifacts/ IS IGNORED BY GIT, so a fresh checkout has none: CI rendered the
    empty state and the verdict assertion could not pass. Asserting that records
    happen to be present tests the machine, not the page. These fixtures are
    written only when a kind is absent, so a developer's real records are used
    where they exist and CI still has something to render.

    The settings fixture is a FAILING verdict on purpose. The first real check
    found three S001 differences and recorded them before the fix; a page that
    can only render a pass cannot be trusted when it shows one.
    """
    import json

    artifacts = REPO_ROOT / ".artifacts"
    seeds = {
        "repo-settings": {
            "contract": "repository-settings-check/v1",
            "verdict": "fail",
            "repository": "otsafety-gnn",
            "recorded_at": "2026-01-01T00:00:00Z",
            "findings": [
                {
                    "rule": "S001",
                    "code": "SETTING_DIFFERS",
                    "detail": "allow_squash_merge is True but the policy requires False",
                }
            ],
        },
        "runs": {
            "contract": "run-record/v1",
            "id": "000000000000",
            "task": "fixture",
            "arguments": [],
            "started_at": "2026-01-01T00:00:00Z",
            "duration_ms": 0,
            "exit_code": 1,
            "outcome": "failure",
            "repository": "otsafety-gnn",
            "branch": "fixture",
            "commit": "0" * 40,
            "output_bytes": 0,
            "output_sha256": "0" * 64,
            "truncated": False,
        },
    }
    for kind, record in seeds.items():
        folder = artifacts / kind
        if folder.is_dir() and any(folder.glob("*.json")):
            continue
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "00000000T000000000000Z-fixture.json").write_text(json.dumps(record))


@pytest.fixture(scope="session")
def site_server() -> Iterator[str]:
    """Build the site, serve it, and stop the server even when a test fails."""
    _seed_evidence()
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
