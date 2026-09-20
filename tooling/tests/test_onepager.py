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
