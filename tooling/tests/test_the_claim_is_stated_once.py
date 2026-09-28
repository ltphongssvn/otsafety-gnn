# tooling/tests/test_the_claim_is_stated_once.py
"""What the project is for is stated once (G.75), and no prose is typed twice (G.76).

THE THIRD INSTANCE OF THE SAME COPY. 8.5 found the nine layers typed in the
sheet and again on the site, already diverged. G.66 found the ladder the same
way: six rungs against seven. This is the research question itself, the central
goal and the machine-learning objective -- the sentences that say what the
project is for -- typed in scripts/build_arch_onepager.py and again in
apps/site/src/data/architecture.ts.

EACH WAS FOUND BY SOMEONE ASKING, NEVER BY A GATE, so a fourth would last until
someone happened to look. G.76 is that gate: the renderers are compared against
the document, and a long sentence appearing in two places fails.

THE DOCUMENT ALREADY HOLDS THE SPINE. Each question carries its contrast and
what follows if the contrast ties -- a hypothesis and its falsification
condition, which is the shape 2026 research infrastructure keeps. What was
missing is the prose around it.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.architecture import Architecture
from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.75")

SOURCE = REPO_ROOT / "context" / "architecture.yaml"
SHEET = REPO_ROOT / "scripts" / "build_arch_onepager.py"
SITE = REPO_ROOT / "apps" / "site" / "src" / "data" / "architecture.ts"


def _architecture() -> Architecture:
    return read_yaml(SOURCE, Architecture)


def test_the_document_states_the_claim() -> None:
    """Question, goal and objective, where the layers and the ladder already live."""
    claim = _architecture().claim
    assert "relationships" in claim.question
    assert "either direction" in claim.goal
    assert "multi-label" in claim.objective.lower()


def test_the_sheet_types_none_of_it() -> None:
    """It renders the document, as it does for the layers and the rungs."""
    source = SHEET.read_text(encoding="utf-8")
    for name in ("RESEARCH_QUESTION =", "CENTRAL_GOAL =", "ML_OBJECTIVE ="):
        assert name not in source, f"the sheet still types {name.split()[0]}"


def test_the_site_types_none_of_it() -> None:
    """The copy that diverged, and the file that held it.

    IT TURNED OUT TO BE DEAD CODE. Five exports, no importer: the site never
    rendered the research question at all, so the claim was typed twice and
    shown once, and the stale copy read as authoritative to anyone who opened
    it. The file is gone; this asserts it stays gone rather than returning
    early, which would make the test green for the wrong reason.
    """
    assert not SITE.exists(), "the site's second copy of the claim is back"
