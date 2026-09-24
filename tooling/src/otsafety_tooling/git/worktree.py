# tooling/src/otsafety_tooling/git/worktree.py
"""Manage linked worktrees: add, list, refresh, remove.

WHY A MODULE AND NOT `git worktree add` TYPED BY HAND
Every project operation is a task. A hand-typed worktree leaves no record of
where worktrees go, what they are named, or what setup they need -- and the
setup is what bites, because git copies none of it: a fresh worktree has no
.venv, an untrusted mise.toml and no hooks. `add` therefore runs setup.

LAYOUT: SIBLING DIRECTORIES, NAMED AFTER THE BRANCH
<repo>-<slug> beside the main checkout, on feature/<slug>. Siblings avoid
nested-.git problems and make active work visible from one `ls`.

REMOVAL IS DELIBERATELY UNFORGIVING
`git worktree remove` refuses on modified or untracked files and --force is
never passed; `git branch -d` refuses unmerged work, which doubles as proof the
merge happened.

Ported from cscie103-olap-oltp (src/cscie103_olap_oltp/git/worktree.py), with
two changes:
  - every command takes the repository root, and add takes the setup runner,
    so the behaviour is tested on real repositories without running mise;
  - refresh REFUSES A BRANCH THAT IS ALREADY PUSHED. A rebase rewrites its
    commits, the next push is rejected as non-fast-forward, and the only way
    through is a force push -- which this repository never performs.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from otsafety_tooling.git.env import git, scrubbed_env
from otsafety_tooling.paths import REPO_ROOT

INTEGRATION_BRANCH = "develop"

# THE ATTRIBUTES GIT CURRENTLY EMITS. An unknown one refuses the whole
# inventory: destructive verbs sit on this parser.
KNOWN_ATTRIBUTES = frozenset(
    {"worktree", "HEAD", "branch", "bare", "detached", "locked", "prunable"}
)

SetupRunner = Callable[[Path], int]


def validate_slug(slug: str) -> None:
    """A slug becomes both a branch name and a directory name."""
    if not slug or not all(ch.islower() or ch.isdigit() or ch == "-" for ch in slug):
        raise SystemExit(f"slug must be lowercase kebab-case: {slug!r}")


def sibling_name(main: Path, slug: str) -> Path:
    """<repo>-<slug>, beside the main checkout."""
    return main.parent / f"{main.name}-{slug}"


def parse_records(root: Path, _raw: bytes | None = None) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain -z`, failing closed.

    -z IS NOT OPTIONAL: porcelain does not quote paths, so a newline in a path
    corrupts a line-based parser. _raw exists only for the fail-closed tests.
    """
    if _raw is None:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain", "-z"],  # noqa: S607
            capture_output=True,
            check=False,
            cwd=root,
            env=scrubbed_env(),
        )
        if result.returncode != 0:
            print(result.stderr.decode(errors="replace").strip(), file=sys.stderr)
            raise SystemExit("git worktree list failed")
        _raw = result.stdout

    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for token in _raw.split(b"\0"):
        if token == b"":
            if current:
                records.append(current)
                current = {}
            continue
        try:
            text = token.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SystemExit(f"worktree path is not UTF-8: {error}") from error
        key, _, value = text.partition(" ")
        if key not in KNOWN_ATTRIBUTES:
            raise SystemExit(f"unrecognised worktree attribute {key!r}; refusing to continue")
        current[key] = value
    if current:
        records.append(current)

    if not records or "worktree" not in records[0]:
        raise SystemExit("no main worktree reported; is this a git repository?")
    return records


def main_path(root: Path) -> Path:
    """The first record is the main worktree, per git's documented ordering."""
    return Path(parse_records(root)[0]["worktree"])


def run_setup(path: Path) -> int:
    """Trust the new checkout's mise config and run its setup task."""
    # The NEW checkout's own environment: nothing of the one this ran in.
    environment = scrubbed_env()
    subprocess.run(
        ["mise", "trust"],  # noqa: S607
        cwd=path,
        check=False,
        capture_output=True,
        env=environment,
    )
    return subprocess.run(
        ["mise", "run", "setup"],  # noqa: S607
        cwd=path,
        check=False,
        env=environment,
    ).returncode


def cmd_list(root: Path) -> int:
    for record in parse_records(root):
        branch = record.get("branch", "").removeprefix("refs/heads/") or "(detached)"
        flags = [flag for flag in ("locked", "prunable") if flag in record]
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{record['worktree']}  {branch}{suffix}")
    return 0


def cmd_add(slug: str, root: Path, setup: SetupRunner = run_setup) -> int:
    validate_slug(slug)
    branch = f"feature/{slug}"
    path = sibling_name(main_path(root), slug)

    if path.exists():
        raise SystemExit(f"{path} already exists. Remove it first: mise run worktree:remove {slug}")

    # OFF origin/develop, FETCHED FIRST: a worktree cut from a stale develop
    # starts life behind.
    fetched = git("fetch", "origin", "--prune", "--quiet", cwd=root)
    if fetched.returncode != 0:
        print(fetched.stderr.strip(), file=sys.stderr)
        raise SystemExit("fetch failed")

    # --no-track, EXPLICITLY. Starting from a remote branch, git may set
    # origin/develop as the new branch's upstream, depending on each machine's
    # branch.autoSetupMerge. Such a branch never reads as [gone] after its
    # merge and looks "pushed" before it ever was. The only upstream a feature
    # branch gets is the one `pr` sets when it pushes.
    added = git(
        "worktree",
        "add",
        "--no-track",
        "-b",
        branch,
        str(path),
        f"origin/{INTEGRATION_BRANCH}",
        cwd=root,
    )
    if added.returncode != 0:
        print(added.stderr.strip(), file=sys.stderr)
        raise SystemExit("git worktree add failed")
    print(f"created {path} on {branch}\n")

    print("running setup in the new worktree...")
    if setup(path) != 0:
        print(
            f"\nsetup failed in {path}. The worktree exists but is not usable. "
            f"Fix setup there, or remove it:\n  mise run worktree:remove {slug}",
            file=sys.stderr,
        )
        return 1

    print(f"\nnext:\n  cd {path}")
    return 0


def cmd_refresh(slug: str, root: Path) -> int:
    """Rebase an UNPUSHED worktree branch onto current origin/develop."""
    validate_slug(slug)
    path = sibling_name(main_path(root), slug)
    if not path.exists():
        raise SystemExit(f"{path} does not exist")

    status = subprocess.run(
        ["git", "status", "--porcelain", "-z"],  # noqa: S607
        capture_output=True,
        check=False,
        cwd=path,
        env=scrubbed_env(),
    )
    if status.stdout.strip(b"\0"):
        raise SystemExit(
            f"refusing: {path} has uncommitted changes. Commit or discard them first; "
            "--autostash would hide the work in a stash nobody created."
        )

    fetched = git("fetch", "origin", "--prune", "--quiet", cwd=root)
    if fetched.returncode != 0:
        print(fetched.stderr.strip(), file=sys.stderr)
        raise SystemExit("fetch failed")

    # A PUSHED BRANCH IS NOT REBASED: rewriting published commits would make the
    # next push a non-fast-forward, and this repository never force-pushes.
    # `pr` always pushes with -u, so an upstream is the record of a push.
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", cwd=path)
    if upstream.returncode == 0:
        raise SystemExit(
            f"refusing: {path} tracks {upstream.stdout.strip()}, so it was pushed. "
            "Rebasing would rewrite published commits and need a force push; "
            "bring develop in through the pull request instead."
        )

    before = git("rev-parse", "HEAD", cwd=path).stdout.strip()
    rebased = git("rebase", f"origin/{INTEGRATION_BRANCH}", cwd=path)
    if rebased.returncode != 0:
        print((rebased.stdout + rebased.stderr).strip(), file=sys.stderr)
        raise SystemExit(
            f"rebase stopped in {path}. Resolve there and continue, or abort the rebase."
        )
    after = git("rev-parse", "HEAD", cwd=path).stdout.strip()
    target = git("rev-parse", f"origin/{INTEGRATION_BRANCH}", cwd=path).stdout.strip()

    # REPORT AN OBSERVED STATE CHANGE, NOT PARSED OUTPUT: rebase writes its
    # success message to stderr, and comparing SHAs cannot misreport.
    if before == after:
        print(f"{path} was already on origin/{INTEGRATION_BRANCH} ({target[:12]})")
    else:
        print(f"{path}: {before[:12]} -> {after[:12]} (onto {target[:12]})")
    return 0


def cmd_remove(slug: str, root: Path) -> int:
    validate_slug(slug)
    path = sibling_name(main_path(root), slug)
    branch = f"feature/{slug}"

    if not path.exists():
        raise SystemExit(f"{path} does not exist")

    # NO --force, EVER.
    removed = git("worktree", "remove", str(path), cwd=root)
    if removed.returncode != 0:
        print(removed.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"refused to remove {path}")
    print(f"removed {path}")

    # `-d`, NOT `-D`.
    deleted = git("branch", "-d", branch, cwd=root)
    if deleted.returncode != 0:
        detail = deleted.stderr.strip()
        # ALREADY GONE (usually removed by sync) is not "unmerged".
        if "not found" in detail:
            print(f"removed the worktree; branch {branch} was already gone")
            return 0
        print(
            f"worktree removed, but branch {branch} was NOT deleted:\n  {detail}\n"
            "That refusal means the branch is unmerged. Merge it first.",
            file=sys.stderr,
        )
        return 1

    print(f"deleted branch {branch}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    match args:
        case ["list"]:
            return cmd_list(REPO_ROOT)
        case ["add", slug]:
            return cmd_add(slug, REPO_ROOT)
        case ["refresh", slug]:
            return cmd_refresh(slug, REPO_ROOT)
        case ["remove", slug]:
            return cmd_remove(slug, REPO_ROOT)
        case other:
            raise SystemExit(
                "usage: python -m otsafety_tooling.git.worktree "
                f"add|list|refresh|remove [slug]  (got {other})"
            )


if __name__ == "__main__":
    raise SystemExit(main())
