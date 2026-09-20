# tooling/tests/test_artifacts.py
"""Evidence lives in one place per clone, so removing a worktree never loses it.

THE RISK, OBSERVED RATHER THAN ASSUMED. git documents that `worktree remove`
refuses only for untracked or modified tracked files, then deletes the whole
directory. Ignored files are neither, so an ignored .artifacts/ inside a linked
worktree -- its reports and gate logs -- is deleted with it. The first test
runs git and records that behaviour; the rest prove the shared root survives.

THE SHARED ROOT is the MAIN checkout's .artifacts/, found through git's own
worktree list, whose first entry is always the main checkout. `main` prints it,
so shell commands in any worktree can write logs there.
"""

from pathlib import Path

import pytest

from otsafety_tooling import artifacts
from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.git.branches import default_artifacts
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT


def _git(*args: str, cwd: Path) -> str:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _main_with_linked(tmp_path: Path) -> tuple[Path, Path]:
    """A main checkout that ignores .artifacts/, and one linked worktree."""
    main = tmp_path / "repo"
    main.mkdir()
    _git("init", "-q", "-b", "develop", cwd=main)
    _git("config", "user.email", "test@example.invalid", cwd=main)
    _git("config", "user.name", "Test", cwd=main)
    (main / ".gitignore").write_text(".artifacts/\n", encoding="utf-8")
    _git("add", ".gitignore", cwd=main)
    _git("commit", "-q", "-m", "ignore artifacts", cwd=main)
    linked = tmp_path / "repo-linked"
    _git("worktree", "add", "-q", "-b", "feature/linked", str(linked), cwd=main)
    return main, linked


def _remove(main: Path, linked: Path) -> None:
    _git("worktree", "remove", str(linked), cwd=main)


def test_git_deletes_ignored_evidence_inside_a_removed_worktree(tmp_path: Path) -> None:
    """The behaviour that makes a per-worktree evidence folder unsafe."""
    main, linked = _main_with_linked(tmp_path)
    local = linked / ".artifacts" / "report.json"
    local.parent.mkdir(parents=True)
    local.write_text("{}\n", encoding="utf-8")

    _remove(main, linked)

    assert not local.exists()
    assert not linked.exists()


def test_every_worktree_resolves_to_the_main_checkouts_evidence(tmp_path: Path) -> None:
    main, linked = _main_with_linked(tmp_path)
    expected = main.resolve() / ".artifacts"
    assert artifacts_root(main) == expected
    assert artifacts_root(linked) == expected


def test_evidence_written_through_the_shared_root_survives_removal(tmp_path: Path) -> None:
    main, linked = _main_with_linked(tmp_path)
    shared = artifacts_root(linked) / "branch-report" / "report.json"
    shared.parent.mkdir(parents=True)
    shared.write_text("{}\n", encoding="utf-8")

    _remove(main, linked)

    assert shared.read_text(encoding="utf-8") == "{}\n"


def test_branch_reports_are_recorded_under_the_shared_root() -> None:
    assert default_artifacts() == artifacts_root(REPO_ROOT) / "branch-report"


def test_main_prints_only_the_shared_root(capsys: pytest.CaptureFixture[str]) -> None:
    """One line, nothing else, so `$(mise run -q artifacts:path)` is the path."""
    assert artifacts.main() == 0
    assert capsys.readouterr().out == f"{artifacts_root(REPO_ROOT)}\n"
