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
    """NOTHING STORED CAN DRIFT (G.53).

    The facts were committed and went stale three times in one session, each
    time because the commit carrying them completed a step they count. A figure
    counting completed steps cannot be correct in the same commit as the work it
    counts -- structural, not a mistake, and a drift gate on a committed copy
    only reports it.

    This repository already answers this for requirement-matrix.json: derived
    from the plan, needed by a gate, written to a build directory and never
    committed. The sheet's facts are the same kind of artifact.
    """
    from otsafety_tooling.git.env import git
    from otsafety_tooling.planning.sheet import TARGET

    tracked = git("ls-files", str(TARGET)).stdout.strip()
    assert tracked == "", f"{TARGET} is committed; a derived file that is stored can drift"


def test_the_render_collects_the_facts_before_it_needs_them() -> None:
    """The renderer is handed a document it cannot produce itself."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig

    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["pdf:render"]
    body = task.run if isinstance(task.run, str) else "\n".join(task.run)
    assert "sheet:facts" in body, "pdf:render does not collect the facts it renders"
