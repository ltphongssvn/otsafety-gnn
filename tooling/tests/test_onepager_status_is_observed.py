# tooling/tests/test_onepager_status_is_observed.py
"""The sheet's status is observed at render time, never typed (G.53).

WHAT WENT WRONG. The rendered sheet claimed 383 tests and 11 pull requests
against a repository with 774 tests and 72 merges. The line was true when it was
typed and has been wrong ever since, which is precisely the drift plan-as-data
exists to end -- the plan's own contract names this sheet as the example.

A NUMBER IN MARKUP IS A CLAIM NOBODY RE-CHECKS. So the generator counts what it
reports, from the plan, the ledger, the matrix and the commit graph, and a test
refuses a digit typed into the template.
"""

from __future__ import annotations

import re

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.53")

GENERATOR = REPO_ROOT / "scripts" / "build_arch_onepager.py"


def test_the_status_line_is_built_from_observation() -> None:
    """The generator computes its status rather than quoting one."""
    from importlib import util

    spec = util.spec_from_file_location("build_arch_onepager", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    status = module.status_line()
    assert status, "the sheet reports no status at all"
    for named in ("plan steps", "requirement ids", "test functions", "pull requests"):
        assert named in status, f"the status does not report {named}"


def test_no_count_is_typed_into_the_markup() -> None:
    """A literal count in the template is the defect this closes."""
    text = GENERATOR.read_text(encoding="utf-8")
    markup = "\n".join(line for line in text.splitlines() if "<div" in line or "hstat" in line)
    typed = re.findall(r"\b\d{2,}\s+(?:tests|pull requests|steps|commits)\b", markup)
    assert typed == [], f"the markup states counts of its own: {typed}"


def test_the_reported_counts_match_the_repository() -> None:
    """The point of collecting: the number is right because it was measured.

    THE FIELDS ARE THE CONTRACT'S. observed_status returns sheet-facts/v1 now,
    collected by the tooling rather than gathered by the renderer, so the names
    are the contract's own -- test_functions, not tests.
    """
    from importlib import util

    from otsafety_tooling.planning.edit import load
    from otsafety_tooling.planning.ledger import load_ledger

    spec = util.spec_from_file_location("build_arch_onepager", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observed = module.observed_status()

    assert observed["steps"] == len(load().steps)
    assert observed["ids"] == len(load_ledger().issued)
    assert int(str(observed["test_functions"])) > 500
    assert int(str(observed["merged_prs"])) > 60


def test_the_committed_facts_are_what_the_repository_holds() -> None:
    """THE DRIFT GATE, for the reason the typed status needed replacing.

    A collected figure goes stale the moment the plan changes, exactly as a typed
    one does; the only difference is that this one can be regenerated and
    compared. A hand-edited or forgotten sheet-facts.json fails here.
    """
    from otsafety_tooling.planning.sheet import TARGET, export

    committed = (REPO_ROOT / TARGET).read_text(encoding="utf-8")
    assert committed == export(), "sheet-facts.json differs; run mise run contracts:generate"
