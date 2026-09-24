# tooling/tests/test_sync_perennial.py
"""sync keeps every protected branch current, and prunes empty branches only on request.

THE DEFECTS. sync advanced develop alone, so local main fell 59 commits behind
origin/main across two promotions and the branch report failed on B001 after
every release. And an empty branch that was never pushed could not be removed at
all: cleanup reads [gone], and a branch that never had an upstream has none to
lose. The model could not even say so -- it told that branch its "upstream still
exists".

2026 PRACTICE, applied. Git Town syncs every perennial branch and prunes empty
branches only behind an explicit --prune, since a branch just cut by start:here
is empty too. Whether a branch was ever pushed is read from git with
%(upstream:short), not inferred. Merged is judged against the remote integration
branch, so a stale local develop cannot decide it. And the protected guard holds
in the prune pass as well: a 2026 cleanup tool deleted main because only one of
its two passes checked.
"""

from pathlib import Path

import pytest

from otsafety_tooling.git.env import git as _run_git
from otsafety_tooling.git.state import Branch, RepositoryState, Worktree, gather
from otsafety_tooling.git.sync import advance_protected, plan_cleanup

pytestmark = pytest.mark.requirement("G.11")

MAIN_CHECKOUT = Path("/nonexistent/repo")


def _state(*branches: Branch) -> RepositoryState:
    main = Worktree(path=MAIN_CHECKOUT, branch="develop", is_main=True, is_dirty=False)
    return RepositoryState(worktrees=(main,), branches=branches)


def _branch(**overrides: object) -> Branch:
    payload: dict[str, object] = {
        "name": "feature/abandoned",
        "upstream": None,
        "upstream_gone": False,
        "is_merged": True,
        "held_by": None,
    }
    payload.update(overrides)
    return Branch.model_validate(payload)


def test_an_empty_never_pushed_branch_is_pruned_only_on_request() -> None:
    branch = _branch()
    assert branch not in plan_cleanup(_state(branch)).remove
    assert branch in plan_cleanup(_state(branch), prune=True).remove


@pytest.mark.parametrize(
    ("case", "overrides"),
    [
        ("it has commits of its own", {"is_merged": False}),
        ("it was pushed and its upstream still exists", {"upstream": "origin/feature/abandoned"}),
        ("it is main", {"name": "main"}),
        ("it is develop", {"name": "develop"}),
        ("a worktree holds it", {"held_by": Path("/nonexistent/worktrees/x")}),
    ],
)
def test_a_branch_is_never_pruned_when(case: str, overrides: dict[str, object]) -> None:
    branch = _branch(**overrides)
    assert branch not in plan_cleanup(_state(branch), prune=True).remove, case


def test_a_never_pushed_branch_is_described_truthfully() -> None:
    reason = _branch(is_merged=False).blocked_because or ""
    assert "never pushed" in reason
    assert "upstream still exists" not in reason


def _git(*args: str, cwd: Path) -> str:
    result = _run_git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _identity(root: Path) -> None:
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)


def _world(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin with develop and main, a writer, and a clone holding both."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)
    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _identity(seed)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", "HEAD:main", cwd=seed)
    repo = tmp_path / "repo"
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _identity(repo)
    _git("branch", "main", "origin/main", cwd=repo)
    return repo, seed


def _at(root: Path, ref: str) -> str:
    return _git("rev-parse", ref, cwd=root).strip()


def _branches(root: Path) -> dict[str, Branch]:
    return {b.name: b for b in gather(root).branches}


def test_gather_reads_whether_a_branch_was_ever_pushed(tmp_path: Path) -> None:
    repo, _ = _world(tmp_path)
    _git("branch", "feature/local", cwd=repo)
    _git("branch", "feature/pushed", cwd=repo)
    _git("push", "-q", "-u", "origin", "feature/pushed", cwd=repo)
    found = _branches(repo)
    assert found["feature/local"].upstream is None
    assert found["feature/pushed"].upstream == "origin/feature/pushed"


def test_merged_is_judged_against_origin_develop_not_a_stale_local_one(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "merged upstream", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)
    _git("fetch", "-q", "origin", cwd=repo)
    _git("branch", "feature/landed", "origin/develop", cwd=repo)
    assert _at(repo, "develop") != _at(repo, "origin/develop"), "local develop must be stale here"
    assert _branches(repo)["feature/landed"].is_merged


def test_main_is_advanced_like_develop(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "released", cwd=seed)
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)
    advance_protected(repo, "main")
    assert _at(repo, "main") == _at(repo, "origin/main")


def test_a_diverged_main_is_refused_and_named(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "released", cwd=seed)
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)
    _git("switch", "-q", "main", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "local only", cwd=repo)
    _git("switch", "-q", "develop", cwd=repo)
    with pytest.raises(SystemExit, match="main has diverged"):
        advance_protected(repo, "main")


def test_an_unknown_argument_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """A REFUSAL IS AN OUTCOME: exit 2 with a machine code, where it used to raise."""
    from otsafety_tooling.contracts.outcome import CommandOutcome
    from otsafety_tooling.git.sync import main

    assert main(["--nonsense"]) == 2
    envelope = CommandOutcome.model_validate_json(capsys.readouterr().out)
    assert envelope.code == "usage" and "--prune" in envelope.message


def test_sync_prunes_only_when_asked_and_advances_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole task, end to end: main advanced, an empty branch reported, then removed."""
    from otsafety_tooling.git import sync

    repo, seed = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "released", cwd=seed)
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)
    _git("branch", "feature/abandoned", cwd=repo)
    monkeypatch.setattr(sync, "REPO_ROOT", repo)

    assert sync.main([]) == 0
    first = capsys.readouterr().out
    assert _at(repo, "main") == _at(repo, "origin/main"), "main was not advanced"
    assert "feature/abandoned" in _branches(repo), "an empty branch was removed without --prune"
    assert "feature/abandoned" in first and "--prune" in first, (
        "a kept empty branch must be reported"
    )

    assert sync.main(["--prune"]) == 0
    assert "feature/abandoned" not in _branches(repo)
    assert "main" in _branches(repo) and "develop" in _branches(repo)


def test_the_task_forwards_prune_to_the_module() -> None:
    """main() accepting --prune proves nothing if the task never passes it.

    The first wiring edited sync.py and refused on mise.toml, and every test still
    passed, because they all call main() directly.
    """
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig
    from otsafety_tooling.paths import REPO_ROOT

    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["sync"]
    assert task.usage is not None and 'flag "--prune"' in task.usage
    assert "otsafety_tooling.git.sync --prune" in "\n".join(task.scripts)
