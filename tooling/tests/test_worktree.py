# tooling/tests/test_worktree.py
"""Worktrees are created, refreshed and removed safely, on real repositories.

setup is injected, so these tests exercise git's behaviour without running mise.
"""

from pathlib import Path

import pytest

from otsafety_tooling.contracts.outcome import EXIT_CODES
from otsafety_tooling.git.env import git
from otsafety_tooling.git.worktree import (
    cmd_add,
    cmd_refresh,
    cmd_remove,
    main_path,
    parse_records,
    sibling_name,
    validate_slug,
)


def _git(*args: str, cwd: Path) -> str:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _identity(root: Path) -> None:
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)


def _clone(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin with develop, and a clone of it named `repo`."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)
    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _identity(seed)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)
    repo = tmp_path / "work" / "repo"
    repo.parent.mkdir()
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _identity(repo)
    return repo, seed


def _ok(_: Path) -> int:
    return 0


def _broken(_: Path) -> int:
    return 1


@pytest.mark.parametrize("slug", ["run-records", "x", "v2-fix"])
def test_kebab_case_slugs_are_accepted(slug: str) -> None:
    validate_slug(slug)


@pytest.mark.parametrize("slug", ["", "Run", "a_b", "a/b", "a b", "../x"])
def test_other_slugs_are_refused(slug: str) -> None:
    with pytest.raises(SystemExit, match="kebab-case"):
        validate_slug(slug)


def test_sibling_is_named_after_repo_and_slug() -> None:
    assert sibling_name(Path("/w/repo"), "run-records") == Path("/w/repo-run-records")


def test_unknown_attribute_refuses_the_inventory(tmp_path: Path) -> None:
    raw = b"worktree /w/repo\0HEAD abc\0surprise x\0\0"
    with pytest.raises(SystemExit, match="surprise"):
        parse_records(tmp_path, _raw=raw)


def test_empty_listing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no main worktree"):
        parse_records(tmp_path, _raw=b"")


def test_a_newline_in_a_path_is_parsed_intact(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    odd = tmp_path / "work" / "odd\nname"
    _git("worktree", "add", "-q", "-b", "feature/odd", str(odd), cwd=repo)
    paths = [Path(r["worktree"]) for r in parse_records(repo)]
    assert odd.resolve() in [p.resolve() for p in paths]


def test_add_creates_a_sibling_on_a_feature_branch_from_origin_develop(tmp_path: Path) -> None:
    repo, seed = _clone(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "newer", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)

    assert cmd_add("run-records", repo, setup=_ok) == 0
    sibling = tmp_path / "work" / "repo-run-records"
    assert _git("rev-parse", "--abbrev-ref", "HEAD", cwd=sibling).strip() == "feature/run-records"
    # Cut from the FETCHED origin/develop, not the clone's stale local copy.
    assert _git("log", "-1", "--format=%s", cwd=sibling).strip() == "newer"
    assert main_path(sibling).resolve() == repo.resolve()


def test_add_refuses_an_existing_path(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    (tmp_path / "work" / "repo-taken").mkdir()
    with pytest.raises(SystemExit, match="already exists"):
        cmd_add("taken", repo, setup=_ok)


def test_add_reports_a_failed_setup(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    assert cmd_add("half", repo, setup=_broken) == 1
    assert (tmp_path / "work" / "repo-half").is_dir()


def test_refresh_rebases_an_unpushed_branch(tmp_path: Path) -> None:
    repo, seed = _clone(tmp_path)
    cmd_add("work", repo, setup=_ok)
    sibling = tmp_path / "work" / "repo-work"
    _git("commit", "-q", "--allow-empty", "-m", "mine", cwd=sibling)
    _git("commit", "-q", "--allow-empty", "-m", "theirs", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)

    assert cmd_refresh("work", repo) == 0
    subjects = _git("log", "--format=%s", "-3", cwd=sibling).split("\n")
    assert subjects[:2] == ["mine", "theirs"]


def test_refresh_refuses_a_pushed_branch(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    cmd_add("shared", repo, setup=_ok)
    sibling = tmp_path / "work" / "repo-shared"
    _git("commit", "-q", "--allow-empty", "-m", "published", cwd=sibling)
    _git("push", "-q", "-u", "origin", "feature/shared", cwd=sibling)
    with pytest.raises(SystemExit, match="pushed"):
        cmd_refresh("shared", repo)


def test_refresh_refuses_a_dirty_tree(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    cmd_add("dirty", repo, setup=_ok)
    (tmp_path / "work" / "repo-dirty" / "scratch.txt").write_text("x\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="uncommitted"):
        cmd_refresh("dirty", repo)


def test_remove_deletes_a_merged_worktree_and_branch(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    cmd_add("done", repo, setup=_ok)
    assert cmd_remove("done", repo) == 0
    assert not (tmp_path / "work" / "repo-done").exists()
    assert "feature/done" not in _git("branch", "--list", cwd=repo)


def test_remove_refuses_uncommitted_work(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    cmd_add("wip", repo, setup=_ok)
    (tmp_path / "work" / "repo-wip" / "scratch.txt").write_text("x\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="refused"):
        cmd_remove("wip", repo)
    assert (tmp_path / "work" / "repo-wip" / "scratch.txt").exists()


def test_remove_keeps_an_unmerged_branch(tmp_path: Path) -> None:
    repo, _ = _clone(tmp_path)
    cmd_add("unmerged", repo, setup=_ok)
    _git(
        "commit", "-q", "--allow-empty", "-m", "not merged", cwd=tmp_path / "work" / "repo-unmerged"
    )
    # A REFUSAL, NOT A CRASH: the repository state was wrong, so the outcome is
    # refused -- exit 2 with a machine code -- where it used to be a bare 1.
    assert cmd_remove("unmerged", repo) == EXIT_CODES["refused"]
    assert "feature/unmerged" in _git("branch", "--list", cwd=repo)


def test_a_new_worktree_branch_has_no_upstream_whatever_git_config_says(
    tmp_path: Path,
) -> None:
    """THE MACHINE-DEPENDENT BUG. With autoSetupMerge enabled, git made
    origin/develop the new branch's upstream, so it looked pushed at birth."""
    repo, _ = _clone(tmp_path)
    _git("config", "branch.autoSetupMerge", "always", cwd=repo)
    cmd_add("fresh", repo, setup=_ok)
    upstream = git(
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        cwd=tmp_path / "work" / "repo-fresh",
    )
    assert upstream.returncode != 0
