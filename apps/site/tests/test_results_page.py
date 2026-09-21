# apps/site/tests/test_results_page.py
"""The results page shows what was measured, and nothing that was not.

WHY THE PAGE IS BUILT FROM RECORDS, NEVER FROM TYPED NUMBERS. A number typed
into a page drifts from the run that produced it, arrives without an interval,
and cannot say which baseline it beats. 2026 reporting practice -- REFORMS and
the NeurIPS checklist -- asks every reported number for the seeds behind it,
their variance or interval, and the baseline it is compared with. So the page
reads experiment-run/v1 records, groups them by experiment, and computes those
itself.

WHAT MUST NEVER HAPPEN. A rung with no records must say it has not run, rather
than render a blank or a zero. A rung with fewer than five seeds must say so,
because one seed cannot resolve a 0.02 difference in average precision. And
rungs measured on different data must not be set side by side as though they
were comparable: the dataset digest on every record makes that checkable.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="the e2e extra is not installed")

from playwright.sync_api import Page, expect


def test_the_results_page_names_every_rung(page: Page, site_server: str) -> None:
    page.goto(f"{site_server}/results")
    body = page.locator("body")
    for rung in ("Degree-only null", "Relation-agnostic GNN", "Relation-aware GNN"):
        expect(body).to_contain_text(rung)


def test_a_rung_with_no_records_says_it_has_not_run(page: Page, site_server: str) -> None:
    """Never a blank and never a zero: those read as results."""
    page.goto(f"{site_server}/results")
    expect(page.locator('[data-rung="shallow-kge"]')).to_contain_text("not yet run")


def test_five_seeds_give_a_mean_and_an_interval(page: Page, site_server: str) -> None:
    page.goto(f"{site_server}/results")
    rung = page.locator('[data-rung="degree-null"]')
    expect(rung).to_contain_text("5 seeds")
    expect(rung).to_contain_text("0.330")  # mean of 0.31..0.35
    expect(rung.locator("[data-interval]")).to_be_visible()


def test_one_seed_is_marked_below_the_protocol(page: Page, site_server: str) -> None:
    """One seed cannot resolve a 0.02 difference; the page must not imply it can."""
    page.goto(f"{site_server}/results")
    expect(page.locator('[data-rung="relation-aware"]')).to_contain_text("below the 5")


def test_a_rung_on_different_data_is_flagged_not_comparable(page: Page, site_server: str) -> None:
    page.goto(f"{site_server}/results")
    expect(page.locator('[data-rung="relation-agnostic"]')).to_contain_text("not comparable")
