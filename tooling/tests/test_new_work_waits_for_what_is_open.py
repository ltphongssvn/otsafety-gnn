# tooling/tests/test_new_work_waits_for_what_is_open.py
"""A branch built on a base that has moved does not push (G.68).

WHY THIS IS THE SAME PROBLEM AS THE MERGE RULE. Every gate here is green
against the base a branch forked from and judged against the base it merges
into. A branch pushed behind its base was verified against a question nobody
asked -- its ratchets, its counts and its plan status all answered for a
develop that no longer exists.

AND IT IS WHAT MAKES THE FIRST CLAUSE MATTER. A dependency update that merges
itself moves develop; work cut before it and pushed after was written against
a tree that is gone. Refusing the push is the enforcement half of the rule
whose other half is deps:merge.

AGAINST origin/develop, NEVER THE LOCAL ONE. The local branch is stale in a
checkout that does not update it, and two projects filed this same defect in
the last day: every commit the base gained since then is counted as the
branch's own.

WHAT NO PRE-PUSH CHECK CAN SEE: a base that moves AFTER the push. This refuses
work already known to be behind, and claims nothing about later.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from otsafety_tooling.git.env import git

pytestmark = pytest.mark.requirement("G.68")


def _git(*args: str, cwd: Path) -> str:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _world(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin with develop, a writer and a clone, as the branch tests build one."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)
    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _git("config", "user.email", "test@example.invalid", cwd=seed)
    _git("config", "user.name", "Test", cwd=seed)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)

    repo = tmp_path / "repo"
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _git("config", "user.email", "test@example.invalid", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    return repo, seed


def test_a_branch_on_the_current_base_may_push(tmp_path: Path) -> None:
    """The control: refusing everything would pass the test below."""
    from otsafety_tooling.git.freshness import behind_base

    repo, _ = _world(tmp_path)
    _git("switch", "-q", "-c", "feature/work", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=repo)

    assert behind_base(repo).allowed


def test_a_branch_whose_base_has_moved_is_refused(tmp_path: Path) -> None:
    """THE RULE: develop advanced after this branch was cut."""
    from otsafety_tooling.git.freshness import behind_base

    repo, seed = _world(tmp_path)
    _git("switch", "-q", "-c", "feature/work", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "moved", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)
    _git("fetch", "-q", "origin", cwd=repo)

    verdict = behind_base(repo)
    assert not verdict.allowed
    assert "1 commit" in verdict.why
    assert "worktree:refresh" in verdict.why, "a refusal that names no remedy is half a message"


def test_the_base_is_the_remote_one_not_a_stale_local_branch(tmp_path: Path) -> None:
    """THE DEFECT TWO PROJECTS FILED IN ONE DAY.

    A local develop that nobody updates is stale by construction, and comparing
    against it counts every commit the real base gained as the branch's own.
    """
    from otsafety_tooling.git.freshness import BASE

    assert BASE.startswith("origin/"), f"{BASE} is a local ref, which goes stale"


def test_a_tag_push_is_not_asked_whether_it_is_behind() -> None:
    """A tag names a commit; whether it contains the base is not the question."""
    from otsafety_tooling.git.freshness import asks_about_freshness

    assert not asks_about_freshness(["refs/tags/v1.0.0"])
    assert asks_about_freshness(["refs/heads/feature/work"])
    assert not asks_about_freshness([])


def test_the_push_gate_asks_first() -> None:
    """THE ORDERING IS HELD, NOT THE CONTENTS.

    The hook names the aggregate and the aggregate names its gates: a
    hand-written list in the hook is what drifted once, losing eight gates. So
    freshness is check's FIRST gate, and this holds that position -- a new gate
    may join freely, and one that pushes freshness down fails here.
    """
    import ast as syntax

    from otsafety_tooling.paths import REPO_ROOT

    tree = syntax.parse((REPO_ROOT / "scripts" / "check_all.py").read_text(encoding="utf-8"))
    gates = next(
        node.value
        for node in tree.body
        if isinstance(node, syntax.AnnAssign)
        and isinstance(node.target, syntax.Name)
        and node.target.id == "GATES"
    )
    assert isinstance(gates, syntax.List)
    names = [
        entry.elts[0].value
        for entry in gates.elts
        if isinstance(entry, syntax.Tuple) and isinstance(entry.elts[0], syntax.Constant)
    ]
    assert names[0] == "start:fresh", f"freshness runs after {names[: names.index('start:fresh')]}"


def test_the_task_exists_and_calls_the_module() -> None:
    """Every operation is a task, including this one."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig
    from otsafety_tooling.paths import REPO_ROOT

    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    assert "start:fresh" in tasks, "asking whether the base moved needs a raw git command"
    assert "otsafety_tooling.git.freshness" in (tasks["start:fresh"].run or "")


def test_the_task_actually_judges_rather_than_exiting_quietly() -> None:
    """A GATE THAT PASSES WITHOUT LOOKING. `python -m` on a module with no
    __main__ guard defines its names and exits 0, so the hook I had just wired
    reported success having judged nothing -- the same failure
    assert_lefthook_installed exists to prevent two lines above it.
    """
    from otsafety_tooling.git import freshness

    assert hasattr(freshness, "main"), "the module has no entry point to run"
    assert callable(freshness.main)


def test_a_behind_branch_refuses_with_a_machine_code(tmp_path: Path) -> None:
    """The refusal is an outcome: exit 2 and a code, never a bare failure."""
    from otsafety_tooling.contracts.outcome import EXIT_CODES
    from otsafety_tooling.git import freshness

    repo, seed = _world(tmp_path)
    _git("switch", "-q", "-c", "feature/work", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "moved", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)
    _git("fetch", "-q", "origin", cwd=repo)

    assert freshness.main([], root=repo) == EXIT_CODES["refused"]


def test_a_current_branch_reports_success(tmp_path: Path) -> None:
    """The control: a gate that only ever refuses is no gate."""
    from otsafety_tooling.git import freshness

    repo, _ = _world(tmp_path)
    _git("switch", "-q", "-c", "feature/work", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=repo)

    assert freshness.main([], root=repo) == 0
