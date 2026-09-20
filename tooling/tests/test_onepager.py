# tooling/tests/test_onepager.py
"""The one-page architecture sheet, built from the same data the site renders.

WHY THE SITE'S DATA AND NOT ITS OWN. The sheet and apps/site/src/data both state
the nine layers and the three nested questions. Two copies drift, and the drift
is invisible until someone reads them side by side. The generator reads the
TypeScript exports so there is one source and no second place to update.

WHY A TEST AND NOT A LOOK. The first version of this sheet named Q2 and Q3 in a
panel and defined them nowhere, and the delivery band still listed a phase for
architecture decision records after that practice was dropped. Both were caught
by reading, late. These assertions catch them at build time.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

GENERATOR = REPO_ROOT / "scripts" / "build_onepager.py"

# Phases as the revised plan states them. Phase 5 is deliberately absent: the
# rule against architecture decision records removed it, and a sheet that still
# advertises it is stale documentation of exactly the kind the rule forbids.
EXPECTED_PHASES = [
    "Ground truth",
    "Branch divergence",
    "GitFlow baseline",
    "Worktree",
    "Stack inventory",
    "Toolchain and tasks",
    "The site",
    "The PDF",
    "The GNN package",
    "Lightning AI",
    "Research execution",
]

FORBIDDEN = ["ADR", "architecture decision", "FAS OnDemand"]


def _generator_source() -> str:
    if not GENERATOR.is_file():
        pytest.fail(f"no generator at {GENERATOR}")
    return GENERATOR.read_text(encoding="utf-8")


def test_the_generator_exists_and_declares_every_phase() -> None:
    src = _generator_source()
    for phase in EXPECTED_PHASES:
        assert phase in src, f"the delivery band does not name the phase {phase!r}"


def test_the_generator_names_no_cancelled_practice() -> None:
    """A band advertising a phase that was cancelled is worse than no band.

    SCOPED TO THE PHASE DECLARATION, NOT THE WHOLE FILE. Grepping the source
    failed on the banner explaining why phase 5 is absent, which is the note a
    later reader most needs. What must not contain a cancelled practice is the
    band that is rendered, so that is what this reads.
    """
    src = _generator_source()
    block = src.split("PHASES = [", 1)[1].split("]", 1)[0]
    for term in FORBIDDEN:
        assert term not in block, f"the rendered phase band still names {term!r}"


def test_the_generator_reads_the_sites_data_rather_than_copying_it() -> None:
    """One source for the layers and the questions, or they will disagree."""
    src = _generator_source()
    assert "apps/site/src/data" in src, (
        "the generator does not read the site's data; a second copy of the "
        "layers and questions will drift from the pages that render them"
    )


def test_the_generator_asserts_its_own_page_count() -> None:
    """A one-page sheet that silently becomes two pages is not a one-pager."""
    src = _generator_source()
    assert "PAGE_COUNT" in src, "the generator does not report its page count"


# --- the rendered sheet, when one has been built -----------------------------
# READING THE SOURCE IS NOT READING THE OUTPUT. The tests above check what the
# generator declares; these check what Chromium actually laid out. A section
# that is declared and then dropped by a layout error passes the first set and
# fails this one.

PDF = REPO_ROOT / "build" / "onepager" / "project-architecture.pdf"

REQUIRED_SECTIONS = [
    "THE RESEARCH QUESTION",
    "CENTRAL GOAL",
    "MACHINE LEARNING OBJECTIVE",
    "REQUIRED MODEL SWEEP",
    "THREE NESTED QUESTIONS",
    "HOW IT RUNS",
    "SCOPE BOUNDARIES",
    "DELIVERY PHASES",
]

REQUIRED_CONTENT = [
    "HALT",  # the audit gate stops the run
    "REJECT",  # the promotion gate does not
    "RotatE",  # the shallow-KGE rung
    "GraphSAGE",  # the relation-agnostic control that isolates Q3
    "Open Targets",
    "BIKG",
]


def _pdf_text() -> str:
    if not PDF.is_file():
        pytest.skip(f"no sheet at {PDF}; run `mise run pdf:build`")
    pypdf = pytest.importorskip("pypdf", reason="the e2e extra is not installed")
    # extract_text is untyped, and strict mypy will not return Any as str.
    text: str = pypdf.PdfReader(str(PDF)).pages[0].extract_text()
    return text


def test_the_rendered_sheet_carries_every_section() -> None:
    text = _pdf_text().upper()
    for section in REQUIRED_SECTIONS:
        assert section in text, f"the sheet does not render the section {section!r}"


def test_the_rendered_sheet_carries_the_content_a_reader_needs() -> None:
    text = _pdf_text()
    for item in REQUIRED_CONTENT:
        assert item in text, f"the sheet does not render {item!r}"


def test_the_rendered_sheet_is_one_page() -> None:
    if not PDF.is_file():
        pytest.skip("no sheet built")
    pypdf = pytest.importorskip("pypdf")
    assert len(pypdf.PdfReader(str(PDF)).pages) == 1


def test_the_rendered_sheet_names_no_cancelled_practice() -> None:
    assert "ADR" not in _pdf_text()
