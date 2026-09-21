# apps/site/tests/test_research_pages.py
"""The pages a proposal reader needs: the question, the data, the stack.

WHAT A READER MUST NOT HAVE TO INFER. The ablation ladder is the experiment, and
the first rung that is not beaten is the answer -- so every rung must be named
with the model that occupies it, not described in the abstract. A page that says
"we compare several baselines" is not a method.

Datasets are named with their licence position, because MedDRA is proprietary
and a project specified as using a public, open-source knowledge graph cannot
redistribute its hierarchy. A reader deciding whether this is reproducible needs
that on the page, not in a footnote.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="the e2e extra is not installed")

from playwright.sync_api import Page, expect

RUNGS = [
    "Degree-only null",
    "Non-graph model",
    "Shallow KGE",
    "Relation-agnostic GNN",
    "Relation-aware GNN",
]

MODELS = ["LogisticRegression", "ComplEx", "GraphSAGE", "HGT"]


def test_the_method_page_names_every_rung_of_the_ladder(page: Page, site_server: str) -> None:
    """Each rung removes one capability from the rung above it."""
    page.goto(f"{site_server}/method")
    body = page.locator("body")
    for rung in RUNGS:
        expect(body).to_contain_text(rung)


def test_the_method_page_names_the_model_at_each_rung(page: Page, site_server: str) -> None:
    """A rung without a named model is not a falsifiable comparison."""
    page.goto(f"{site_server}/method")
    body = page.locator("body")
    for model in MODELS:
        expect(body).to_contain_text(model)


def test_the_data_page_names_its_sources_and_their_licence(page: Page, site_server: str) -> None:
    """Open Targets is the substrate; MedDRA is licensed and cannot ship."""
    page.goto(f"{site_server}/data")
    body = page.locator("body")
    for text in ("Open Targets", "MedDRA", "licence"):
        expect(body).to_contain_text(text)


def test_the_stack_page_names_the_pinned_toolchain(page: Page, site_server: str) -> None:
    """Every executable version is declared once, in toolchain.json."""
    page.goto(f"{site_server}/stack")
    body = page.locator("body")
    for tool in ("toolchain.json", "uv", "bun", "mise", "Astro"):
        expect(body).to_contain_text(tool)


# --- /data against the verified 26.03 release -----------------------------------
# The page was written before the live server was listed, so it named "Open
# Targets Platform" with no release and omitted the two datasets that turned out
# to matter most. Every name below was read off the 26.03 output directory, and
# conf/config.yaml ingests exactly these.

DATA_2603 = [
    "26.03",
    "drug_warning",
    "evidence_clinical_precedence",
    "drug_mechanism_of_action",
    "openfda_significant_adverse_drug_reactions",
    "Parquet",
]


def test_the_data_page_names_the_pinned_release_and_its_datasets(
    page: Page, site_server: str
) -> None:
    page.goto(f"{site_server}/data")
    body = page.locator("body")
    for text in DATA_2603:
        expect(body).to_contain_text(text)


def test_the_data_page_names_the_endpoint_hierarchy(page: Page, site_server: str) -> None:
    """A DAG from open ontologies, because MedDRA cannot be redistributed."""
    page.goto(f"{site_server}/data")
    body = page.locator("body")
    for text in ("EFO", "MONDO", "HPO", "DAG"):
        expect(body).to_contain_text(text)
