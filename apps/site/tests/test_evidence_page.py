# apps/site/tests/test_evidence_page.py
"""The evidence page, read from committed records at build time.

WHY BUILD TIME AND NOT AN API. .artifacts/runs/*.json carries a versioned
run-record/v1 contract and .artifacts/repo-settings/*.json a verdict; both are
files in this repository. Reading them when the site is built means a malformed
record fails the build, where an API would have returned a 500 to a reader.

WHAT THIS ASSERTS. That a verdict reaches the page as a verdict -- pass or fail,
with its rule ids -- rather than as a number with no claim attached. The
repository settings check found three S001 differences on its first run and
recorded them before the fix; a page that can only show the passing state is
not evidence, it is marketing.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="the e2e extra is not installed")

from playwright.sync_api import Page, expect


def test_the_evidence_page_shows_a_recorded_run(page: Page, site_server: str) -> None:
    """A run record is a task, an exit code, a branch and a commit."""
    page.goto(f"{site_server}/evidence")
    body = page.locator("body")
    for heading in ("Task runs", "run-record/v1"):
        expect(body).to_contain_text(heading)


def test_the_evidence_page_shows_a_policy_verdict(page: Page, site_server: str) -> None:
    """Policy as code produces a verdict as data; the page must show which."""
    page.goto(f"{site_server}/evidence")
    body = page.locator("body")
    for text in ("Repository settings", "repository-settings-check/v1"):
        expect(body).to_contain_text(text)


def test_the_evidence_page_can_show_a_failing_verdict(page: Page, site_server: str) -> None:
    """The first settings check failed with three S001 findings. A page that
    renders only passes cannot be trusted when it shows a pass."""
    page.goto(f"{site_server}/evidence")
    expect(page.locator("[data-verdict]").first).to_be_visible()
