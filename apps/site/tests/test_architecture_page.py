# apps/site/tests/test_architecture_page.py
"""The outermost boundary: a real browser against the BUILT site.

AGAINST THE BUILD, NOT THE DEV SERVER. The dev server transforms on demand, so
a page can render there and fail once built. The proposal ships the build, so
the build is what these tests judge.

WHAT THIS ASSERTS, AND WHY THESE THINGS. The PDF's first draft named Q1, Q2 and
Q3 in its open-deliverables panel and defined them nowhere, so a reader met three
labels with no referent. The site must not repeat that: each question is asserted
by its full text, not its label.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="the e2e extra is not installed")

from playwright.sync_api import Page, expect  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
SITE = REPO_ROOT / "apps" / "site"
BASE_URL = "http://localhost:4321"

LAYERS = [
    "REALITY",
    "SELECTION",
    "EVIDENCE",
    "ATTRIBUTION",
    "LABELING RULE",
    "DATASET LABEL",
    "SPLIT",
    "MODEL",
    "VERDICT",
]

QUESTIONS = [
    "Is there any signal beyond node popularity?",
    "Does the graph help beyond non-graph target features?",
    "Do the relation TYPES carry the signal?",
]


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


def test_the_architecture_page_names_every_layer(page: Page, site_server: str) -> None:
    """Nine layers, each named. Four of them (2, 4, 7, 9) are the ones whose
    failures are silent, so a page missing one is worse than a page missing all."""
    page.goto(f"{site_server}/architecture")
    for layer in LAYERS:
        expect(page.get_by_text(layer, exact=False).first).to_be_visible()


def test_the_architecture_page_states_each_nested_question(page: Page, site_server: str) -> None:
    """Q1, Q2 and Q3 in full, not as labels. Q3 is the literal research question."""
    page.goto(f"{site_server}/architecture")
    body = page.locator("body")
    for question in QUESTIONS:
        expect(body).to_contain_text(question)
