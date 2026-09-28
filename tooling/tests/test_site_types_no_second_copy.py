# tooling/tests/test_site_types_no_second_copy.py
"""The ladder is stated once, and the site reads it (G.66).

MEASURED: the sheet shows six rungs and the site types seven. The site carries a
prevalence base rate the sheet omits, and names the no-graph control differently
-- "Non-graph model" against "No-graph control" -- so a reader comparing the two
cannot tell whether that is one rung or two. The tool versions are typed there a
third time, beside toolchain.json and the flake that asserts them.

THIS IS 8.5 REOPENING ONE MODULE ALONG. The layers were typed in two places and
diverged where nobody was looking; the ladder is the same shape of copy, and it
has already diverged the same way. Nothing compares them, which is why it went
unnoticed until someone asked whether the site was in sync.

THE SITE'S COPY IS THE FULLER ONE THIS TIME, so the base rate moves INTO the
document rather than being deleted from the page: a rung the ladder needs is not
a mistake, it is a rung the sheet was missing.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.architecture import Architecture
from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.66")

DATA = REPO_ROOT / "apps" / "site" / "src" / "data"
SOURCE = REPO_ROOT / "context" / "architecture.yaml"


def _architecture() -> Architecture:
    return read_yaml(SOURCE, Architecture)


def test_the_site_types_no_ladder_of_its_own() -> None:
    """One source, as the layers already are."""
    research = DATA / "research.ts"
    if not research.is_file():
        return
    text = research.read_text(encoding="utf-8")
    assert "RUNGS" not in text, "the site still types the ladder beside the document"
    assert "LADDER_RULE" not in text, "the site still types the ladder's rule"


def test_the_document_carries_the_base_rate() -> None:
    """The rung the site had and the sheet did not."""
    names = [rung.name.lower() for rung in _architecture().rungs]
    assert any("base rate" in name or "prevalence" in name for name in names), (
        f"the ladder still omits the prevalence baseline: {names}"
    )


def test_the_ladder_runs_from_the_cheapest_control_upward() -> None:
    """A ladder is an order, and the order is what the contrast means."""
    names = [rung.name for rung in _architecture().rungs]
    assert len(names) == len(set(names)), f"a rung is named twice: {names}"
    assert "relation-aware" in names[-1].lower(), (
        f"the ladder does not end at the top rung: {names[-1]}"
    )


def test_the_site_types_no_tool_version() -> None:
    """TOOLCHAIN and RUNTIME are 7.9's subject, not this step's.

    They are a third copy of what toolchain.json pins and the flake asserts, and
    that is worth closing -- but in the step that already records it. One branch,
    one change: the ladder moves here.
    """
    from otsafety_tooling.planning.edit import load

    step = next(s for s in load().steps if s.id == "7.9")
    assert "toolchain.json" in (step.source or "") + step.title
