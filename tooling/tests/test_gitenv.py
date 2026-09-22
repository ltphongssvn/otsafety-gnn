# tooling/tests/test_gitenv.py
"""Git calls cannot be redirected by an inherited GIT_DIR.

THE TESTS DEMONSTRATE THE VULNERABILITY RATHER THAN ASSERTING IT: they set
GIT_DIR to a real second repository and show raw subprocess following it while
git() does not.

Ported from cscie103-olap-oltp (tests/test_gitenv.py).
"""

import os
import subprocess
from pathlib import Path

import pytest

from otsafety_tooling.git.env import git, routing_overrides_present, scrubbed_env


def _init_repo(path: Path) -> Path:
    """A real repository, because the behaviour under test is git's own."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    return path


def test_scrubbed_env_removes_git_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/somewhere/else/.git")
    assert "GIT_DIR" not in scrubbed_env()


def test_scrubbed_env_removes_git_work_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_WORK_TREE", "/somewhere/else")
    assert "GIT_WORK_TREE" not in scrubbed_env()


def test_scrubbed_env_keeps_unrelated_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over-scrubbing would break PATH and the toolchain with it."""
    monkeypatch.setenv("GIT_DIR", "/somewhere/else/.git")
    environment = scrubbed_env()
    assert "PATH" in environment
    assert environment["PATH"] == os.environ["PATH"]  # noqa: TID251 -- tests the scrubber against the real environment; registered by G.26


def test_raw_subprocess_is_hijacked_by_git_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEMONSTRATE THE VULNERABILITY, so a "simplification" dropping the guard fails."""
    other = _init_repo(tmp_path / "other")
    here = _init_repo(tmp_path / "here")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        cwd=here,
    )
    assert Path(result.stdout.strip()).name == "other"


def test_git_resists_the_hijack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The same call through git() resolves from cwd, as asked."""
    other = _init_repo(tmp_path / "other")
    here = _init_repo(tmp_path / "here")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))

    result = git("rev-parse", "--show-toplevel", cwd=here)
    assert Path(result.stdout.strip()).name == "here"


def test_routing_overrides_are_reported_for_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_DIR", "/somewhere/else/.git")
    assert routing_overrides_present()["GIT_DIR"] == "/somewhere/else/.git"


def test_git_prefix_is_scrubbed_but_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """git exports GIT_PREFIX on every hook run; announcing it would be noise."""
    monkeypatch.setenv("GIT_PREFIX", "")
    assert "GIT_PREFIX" not in scrubbed_env()
    assert "GIT_PREFIX" not in routing_overrides_present()


def test_no_overrides_reports_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(name, raising=False)
    assert routing_overrides_present() == {}


def test_a_poisoned_git_dir_cannot_retarget_a_fixture_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE REGRESSION THAT COST A COMMIT TO THE REAL REPOSITORY.

    RED BEFORE GREEN: the first half proves the poison WORKS, so a passing
    second half means the scrub defeated something real.
    """
    victim = tmp_path / "victim"
    victim.mkdir()
    subprocess.run(["git", "init", "-q", victim], check=True, capture_output=True)

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    subprocess.run(["git", "init", "-q", scratch], check=True, capture_output=True)

    monkeypatch.setenv("GIT_DIR", str(victim / ".git"))

    hijacked = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=scratch,
        env=dict(os.environ),  # noqa: TID251 -- tests the scrubber against the real environment; registered by G.26
        capture_output=True,
        text=True,
        check=True,
    )
    assert str(victim) in hijacked.stdout

    # THE SCRUBBED ENVIRONMENT AS IT IS, not one with GIT_DIR blanked, which
    # would pass even if scrubbed_env() did nothing.
    resolved = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=scratch,
        env=scrubbed_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert str(victim) not in resolved.stdout


def test_the_conftest_guard_removes_routing_variables() -> None:
    """THE ENFORCEMENT, ASSERTED RATHER THAN ASSUMED."""
    assert "GIT_DIR" not in os.environ  # noqa: TID251 -- tests the scrubber against the real environment; registered by G.26
    assert "GIT_WORK_TREE" not in os.environ  # noqa: TID251 -- tests the scrubber against the real environment; registered by G.26
    assert "GIT_INDEX_FILE" not in os.environ  # noqa: TID251 -- tests the scrubber against the real environment; registered by G.26
