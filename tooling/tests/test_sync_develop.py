# tooling/tests/test_sync_develop.py
"""Advancing develop works wherever develop happens to be checked out.

THE DEFECT. sync advanced develop with a refspec fetch, which git refuses when
that branch is checked out anywhere: "refusing to fetch into branch
'refs/heads/develop' checked out at ...". It then reported the branch as
DIVERGED, which is a different problem with a different fix -- while the branch
report, from the same facts, correctly said develop was three commits BEHIND.

The fix asks which worktree holds develop and acts accordingly, and reports
divergence only when it is real.

PRIVACY. A message names the other checkout by its folder name, never by its
absolute path, which contains the owner's name.
"""

from pathlib import Path

import pytest

from otsafety_tooling.git.env import git
from otsafety_tooling.git.sync import advance_develop


def _git(*args: str, cwd: Path) -> str:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _identity(root: Path) -> None:
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)


def _world(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin with develop, a writer, and a clone that has develop."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)
    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _identity(seed)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)
    repo = tmp_path / "repo"
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _identity(repo)
    return repo, seed


def _newer(seed: Path, subject: str = "newer") -> None:
    _git("commit", "-q", "--allow-empty", "-m", subject, cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)


def _at(root: Path, ref: str) -> str:
    return _git("rev-parse", ref, cwd=root).strip()


def test_develop_is_advanced_in_the_checkout_that_holds_it(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _newer(seed)

    advance_develop(repo)

    assert _at(repo, "develop") == _at(repo, "origin/develop")
    assert _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo).strip() == "develop"


def test_another_worktree_holding_develop_is_reported_not_fetched_into(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE DEFECT: git refuses a refspec fetch into a checked-out branch."""
    repo, seed = _world(tmp_path)
    linked = tmp_path / "repo-work"
    _git("worktree", "add", "-q", "--no-track", "-b", "feature/x", str(linked), "develop", cwd=repo)
    _newer(seed)

    advance_develop(linked)

    assert _at(linked, "origin/develop") == _at(seed, "HEAD")
    message = capsys.readouterr().out
    assert "repo" in message
    assert str(repo) not in message


def test_develop_is_advanced_when_no_worktree_holds_it(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("switch", "-q", "--no-track", "-c", "feature/y", "develop", cwd=repo)
    linked = tmp_path / "repo-other"
    _git("worktree", "add", "-q", "--no-track", "-b", "feature/z", str(linked), "develop", cwd=repo)
    _newer(seed)

    advance_develop(linked)

    assert _at(repo, "develop") == _at(seed, "HEAD")


def test_an_already_current_develop_is_left_alone(tmp_path: Path) -> None:
    repo, _ = _world(tmp_path)
    before = _at(repo, "develop")

    advance_develop(repo)

    assert _at(repo, "develop") == before


def test_real_divergence_is_refused_and_named(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "mine", cwd=repo)
    _newer(seed, "theirs")

    with pytest.raises(SystemExit, match="diverged"):
        advance_develop(repo)


def test_the_remote_ref_is_current_even_when_another_worktree_holds_develop(
    tmp_path: Path,
) -> None:
    """The cleanup plan reads origin/develop, so it must be fresh regardless."""
    repo, seed = _world(tmp_path)
    linked = tmp_path / "repo-work"
    _git("worktree", "add", "-q", "--no-track", "-b", "feature/x", str(linked), "develop", cwd=repo)
    _git("switch", "-q", "-c", "feature/done", cwd=seed)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=seed)
    _git("push", "-q", "origin", "feature/done", cwd=seed)

    advance_develop(linked)

    refs = _git("for-each-ref", "--format=%(refname)", "refs/remotes/origin", cwd=linked)
    assert "refs/remotes/origin/feature/done" in refs.split()
