# tooling/tests/test_commit.py
"""A commit contains exactly the named paths, with a conventional subject."""

from pathlib import Path

import pytest

from otsafety_tooling.git.commit import (
    commit,
    is_artifact,
    is_within,
    outsiders,
    undo_last,
    unstage,
    validate_subject,
)
from otsafety_tooling.git.env import git


def _git(*args: str, cwd: Path) -> None:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", "-b", "feature/x", cwd=root)
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)
    _git("config", "core.hooksPath", str(tmp_path / "no-hooks"), cwd=root)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    (root / "b.txt").write_text("b\n", encoding="utf-8")
    _git("add", "a.txt", "b.txt", cwd=root)
    _git("commit", "-qm", "chore: seed", cwd=root)
    return root


def _last(root: Path) -> tuple[str, list[str]]:
    subject = git("log", "-1", "--format=%s", cwd=root).stdout.strip()
    files = git("show", "--name-only", "--format=", "HEAD", cwd=root).stdout.split()
    return subject, files


@pytest.mark.parametrize(
    "subject",
    [
        "feat(tooling): add the commit task",
        "fix: prune every remote branch",
        "build(toolchain)!: drop the musl uv",
    ],
)
def test_conventional_subjects_are_accepted(subject: str) -> None:
    validate_subject(subject)


@pytest.mark.parametrize(
    "subject",
    ["added stuff", "feature(x): wrong type", "feat(Tooling): uppercase scope", "feat:", "x" * 101],
)
def test_other_subjects_are_refused(subject: str) -> None:
    with pytest.raises(SystemExit):
        validate_subject(subject)


def test_multiline_subject_is_refused() -> None:
    with pytest.raises(SystemExit, match="one line"):
        validate_subject("feat: one\ntwo")


def test_paths_inside_a_named_directory_are_covered() -> None:
    assert is_within("tooling/src/x.py", ["tooling"])
    assert is_within("mise.toml", ["mise.toml"])
    assert not is_within("tooling-extra/x.py", ["tooling"])


def test_outsiders_are_listed() -> None:
    assert outsiders(["a.txt", "tooling/x.py"], ["tooling"]) == ["a.txt"]


def test_only_named_paths_are_committed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    (root / "b.txt").write_text("b2\n", encoding="utf-8")
    assert commit("fix: change a", "why a changed", ["a.txt"], root) == 0
    subject, files = _last(root)
    assert subject == "fix: change a"
    assert files == ["a.txt"]
    assert "b.txt" in git("status", "--porcelain", cwd=root).stdout


def test_untracked_directories_are_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    (root / "pkg").mkdir()
    (root / "pkg" / "m.py").write_text("x = 1\n", encoding="utf-8")
    assert commit("feat(pkg): add module", "", ["pkg"], root) == 0
    assert _last(root)[1] == ["pkg/m.py"]


def test_something_already_staged_elsewhere_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    (root / "b.txt").write_text("b2\n", encoding="utf-8")
    _git("add", "b.txt", cwd=root)
    with pytest.raises(SystemExit, match=r"b\.txt"):
        commit("fix: change a", "", ["a.txt"], root)


def test_a_path_without_changes_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"no changes under b\.txt"):
        commit("fix: change both", "", ["a.txt", "b.txt"], root)


def test_a_path_outside_the_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    with pytest.raises(SystemExit, match="outside the repository"):
        commit("fix: x", "", [str(tmp_path)], root)


def test_a_hook_refusal_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text("#!/bin/sh\necho refused-by-hook\nexit 1\n")
    (hooks / "pre-commit").chmod(0o755)
    _git("config", "core.hooksPath", str(hooks), cwd=root)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    assert commit("fix: change a", "", ["a.txt"], root) != 0
    assert _last(root)[0] == "chore: seed"


@pytest.mark.parametrize(
    "path",
    [
        "tooling/src/pkg/__pycache__/m.cpython-313.pyc",
        "x.pyc",
        "a/.pytest_cache/v/cache/lastfailed",
        ".venv/bin/python",
        "docs/.DS_Store",
        "frontend/node_modules/x/index.js",
    ],
)
def test_build_artifacts_are_recognised(path: str) -> None:
    assert is_artifact(path)


@pytest.mark.parametrize("path", ["tooling/src/pkg/m.py", "pycache_notes.md", "cache/x.py"])
def test_source_files_are_not_artifacts(path: str) -> None:
    assert not is_artifact(path)


def test_bytecode_is_refused_even_when_not_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE INCIDENT: a directory commit swept in __pycache__ because no rule ignored it."""
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    (root / "pkg" / "__pycache__").mkdir(parents=True)
    (root / "pkg" / "m.py").write_text("x = 1\n", encoding="utf-8")
    (root / "pkg" / "__pycache__" / "m.cpython-313.pyc").write_bytes(b"\x00")
    with pytest.raises(SystemExit, match="build artifacts"):
        commit("feat(pkg): add module", "", ["pkg"], root)
    assert git("diff", "--cached", "--name-only", cwd=root).stdout == ""


def test_ignored_bytecode_does_not_block_the_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (root / "pkg" / "__pycache__").mkdir(parents=True)
    (root / "pkg" / "m.py").write_text("x = 1\n", encoding="utf-8")
    (root / "pkg" / "__pycache__" / "m.cpython-313.pyc").write_bytes(b"\x00")
    assert commit("feat(pkg): add module", "", ["pkg"], root) == 0
    assert _last(root)[1] == ["pkg/m.py"]


def _with_remote(tmp_path: Path) -> Path:
    root = _repo(tmp_path)
    remote = tmp_path / "remote.git"
    _git("init", "-q", "--bare", str(remote), cwd=tmp_path)
    _git("remote", "add", "origin", str(remote), cwd=root)
    _git("push", "-q", "-u", "origin", "feature/x", cwd=root)
    return root


def test_an_unpushed_commit_is_undone_and_its_changes_kept(tmp_path: Path) -> None:
    root = _with_remote(tmp_path)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    _git("commit", "-qam", "fix: local only", cwd=root)
    assert undo_last(root) == 0
    assert _last(root)[0] == "chore: seed"
    assert (root / "a.txt").read_text(encoding="utf-8") == "a2\n"
    assert git("diff", "--cached", "--name-only", cwd=root).stdout == ""


def test_a_pushed_commit_is_not_undone(tmp_path: Path) -> None:
    root = _with_remote(tmp_path)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    _git("commit", "-qam", "fix: shared", cwd=root)
    _git("push", "-q", cwd=root)
    with pytest.raises(SystemExit, match="already pushed"):
        undo_last(root)
    assert _last(root)[0] == "fix: shared"


def test_undo_is_refused_on_a_protected_branch(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git("switch", "-q", "-c", "develop", cwd=root)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    _git("commit", "-qam", "fix: on develop", cwd=root)
    with pytest.raises(SystemExit, match="protected"):
        undo_last(root)


def test_undo_is_refused_with_staged_changes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    _git("commit", "-qam", "fix: one", cwd=root)
    (root / "b.txt").write_text("b2\n", encoding="utf-8")
    _git("add", "b.txt", cwd=root)
    with pytest.raises(SystemExit, match="staged"):
        undo_last(root)


def test_the_first_commit_is_not_undone(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(SystemExit, match="first commit"):
        undo_last(root)


def test_unstage_removes_only_the_named_paths_from_the_index(tmp_path: Path) -> None:
    """THE INCIDENT: an IDE staged .idea/.gitignore, blocking every focused commit."""
    root = _repo(tmp_path)
    (root / ".idea").mkdir()
    (root / ".idea" / ".gitignore").write_text("x\n", encoding="utf-8")
    (root / "a.txt").write_text("a2\n", encoding="utf-8")
    _git("add", ".idea/.gitignore", "a.txt", cwd=root)
    assert unstage([str(root / ".idea")], root) == 0
    assert git("diff", "--cached", "--name-only", cwd=root).stdout.split() == ["a.txt"]
    assert (root / ".idea" / ".gitignore").exists()


def test_unstage_refuses_a_path_with_nothing_staged(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(SystemExit, match="nothing staged"):
        unstage([str(root / "a.txt")], root)
