# tooling/tests/test_plan_done.py
"""A step claimed done is proved done: when the claim is made, and ever after.

WHY THIS EXISTS. G.25 was merged, yet plan:status reported it unfinished: its
evidence named a test file never written under that name. The commit carried
Plan-Step: G.25, which only references a step, so there was no claim of
completion to check. 2026 practice separates the two -- Refs and Closes -- and
gates the claim: "implemented with no verifier is a claim with no evidence".
Plan-Done: <step> claims completion. The commit-msg hook refuses it unless the
step's evidence holds in the commit being made; this test, run in CI, refuses
any past claim whose evidence no longer holds.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from otsafety_tooling.contracts.files import parse_yaml
from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.status import Facts, gather_facts, staged_facts, unmet
from otsafety_tooling.policy.trailers import claimed_done, commits_since_cutoff, problems

# THIS FILE PROVES G.36: the claim the requirement matrix joins on.
pytestmark = pytest.mark.requirement("G.36")

IDS = frozenset({"G.25", "G.29", "X.README"})
PLAN = ProjectPlan.model_validate(
    {
        "contract": "project-plan/v1",
        "threads": [{"id": "G", "title": "Policy"}],
        "phases": [{"id": "8G", "title": "Policy"}],
        "loops": [{"id": "constrain", "code": "c", "data": "d"}],
        "steps": [
            {
                "id": "G.25",
                "title": "x",
                "thread": "G",
                "phase": "8G",
                "serves": [{"loop": "constrain", "side": "code"}],
                "done_when": [{"kind": "path", "path": "a.py"}, {"kind": "task", "name": "t"}],
            }
        ],
    }
)


def _facts(**overrides: frozenset[str]) -> Facts:
    base: dict[str, object] = {
        "ref": "x",
        "paths": frozenset(),
        "tasks": frozenset(),
        "merged_prs": frozenset(),
        "tags": frozenset(),
        "branches_with_work": frozenset(),
    }
    base.update(overrides)
    return Facts.model_validate(base)


def test_a_done_claim_names_the_step_on_its_own() -> None:
    assert problems("feat: x\n\nbody\n\nPlan-Done: G.29\n", IDS) == []


def test_a_done_claim_on_an_unknown_step_is_refused() -> None:
    assert any("G.99" in p for p in problems("feat: x\n\nbody\n\nPlan-Done: G.99\n", IDS))


def test_a_done_claim_whose_evidence_fails_is_refused_with_the_reason() -> None:
    found = problems(
        "feat: x\n\nbody\n\nPlan-Done: G.25\n",
        IDS,
        holds=lambda step: "path a.py is not in the tree",
    )
    assert any("G.25" in p and "a.py" in p for p in found)


def test_unmet_says_what_is_missing() -> None:
    assert unmet(PLAN, _facts(paths=frozenset({"a.py"})), "G.25") == ["task t is not in mise.toml"]
    assert unmet(PLAN, _facts(paths=frozenset({"a.py"}), tasks=frozenset({"t"})), "G.25") == []


def test_staged_facts_read_the_index_not_the_disk(tmp_path: Path) -> None:
    assert git("init", "-q", cwd=tmp_path).returncode == 0
    (tmp_path / "staged.py").write_text("", encoding="utf-8")
    (tmp_path / "unstaged.py").write_text("", encoding="utf-8")
    assert git("add", "staged.py", cwd=tmp_path).returncode == 0
    paths = staged_facts(tmp_path).paths
    assert "staged.py" in paths and "unstaged.py" not in paths


def test_every_step_claimed_done_still_holds() -> None:
    """The ceiling: a closed step whose evidence later disappears fails the build."""
    shown = subprocess.run(
        ["git", "show", "HEAD:context/plan.yaml"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    plan = parse_yaml(shown.stdout, ProjectPlan)
    facts = gather_facts(REPO_ROOT, "HEAD", merged_prs=frozenset)
    failures = {
        f"{sha[:9]} {step}": gaps
        for sha, message, _, _author in commits_since_cutoff(REPO_ROOT)
        for step in claimed_done(message)
        if (gaps := unmet(plan, facts, step))
    }
    assert failures == {}
