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
  - refresh MERGES rather than rebases. A rebase rewrites the branch's commits,
    so the next push is rejected as non-fast-forward and only a force push gets
    through -- which this repository never performs. A merge keeps every commit
    reachable, so refresh treats a pushed branch and a local one alike.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.cli import CommandRefused, note, refusal, result
from otsafety_tooling.git.env import git, scrubbed_env
from otsafety_tooling.paths import REPO_ROOT

INTEGRATION_BRANCH = "develop"

# THE ATTRIBUTES GIT CURRENTLY EMITS. An unknown one refuses the whole
# inventory: destructive verbs sit on this parser.
KNOWN_ATTRIBUTES = frozenset(
    {"worktree", "HEAD", "branch", "bare", "detached", "locked", "prunable"}
)

SetupRunner = Callable[[Path], int]


class _Payload(BaseModel):
    """A command's payload: named fields, checked where they are written.

    **kwargs cannot be checked -- a misspelt field would ship -- so each command
    declares what it carries, and a list stays a list because the model says so.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class WorktreeRow(_Payload):
    worktree: str
    branch: str | None
    flags: list[str]


class WorktreeList(_Payload):
    worktrees: list[WorktreeRow]


class WorktreeCreated(_Payload):
    worktree: str
    branch: str
    base_ref: str
    commit: str


class WorktreeRefreshed(_Payload):
    worktree: str
    before: str
    after: str
    base_ref: str
    target: str


class WorktreeRemoved(_Payload):
    worktree: str
    branch: str
    branch_deleted: bool


def validate_slug(slug: str) -> None:
    """A slug becomes both a branch name and a directory name."""
    if not slug or not all(ch.islower() or ch.isdigit() or ch == "-" for ch in slug):
        raise CommandRefused("slug_invalid", f"slug must be lowercase kebab-case: {slug!r}")


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
            note(result.stderr.decode(errors="replace").strip())
            raise CommandRefused("worktree_list_failed", "git worktree list failed")
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
            raise CommandRefused("path_not_utf8", f"worktree path is not UTF-8: {error}") from error
        key, _, value = text.partition(" ")
        if key not in KNOWN_ATTRIBUTES:
            raise CommandRefused(
                "unknown_attribute",
                f"unrecognised worktree attribute {key!r}; refusing to continue",
            )
        current[key] = value
    if current:
        records.append(current)

    if not records or "worktree" not in records[0]:
        raise CommandRefused(
            "not_a_repository", "no main worktree reported; is this a git repository?"
        )
    return records


def main_path(root: Path) -> Path:
    """The first record is the main worktree, per git's documented ordering."""
    return Path(parse_records(root)[0]["worktree"])


def run_setup(path: Path) -> int:
    """Trust the new checkout's mise config and run its setup task."""
    subprocess.run(["mise", "trust"], cwd=path, check=False, capture_output=True)  # noqa: S607
    return subprocess.run(["mise", "run", "setup"], cwd=path, check=False).returncode  # noqa: S607


def cmd_list(root: Path) -> int:
    worktrees = [
        WorktreeRow(
            worktree=record["worktree"],
            branch=record.get("branch", "").removeprefix("refs/heads/") or None,
            flags=[flag for flag in ("locked", "prunable") if flag in record],
        )
        for record in parse_records(root)
    ]
    for entry in worktrees:
        note(f"{entry.worktree}  {entry.branch or '(detached)'}")
    return result(
        "worktree:list",
        "success",
        "worktrees_listed",
        f"{len(worktrees)} worktrees",
        WorktreeList(worktrees=worktrees),
    )


def cmd_add(slug: str, root: Path, setup: SetupRunner = run_setup) -> int:
    validate_slug(slug)
    branch = f"feature/{slug}"
    path = sibling_name(main_path(root), slug)

    if path.exists():
        raise CommandRefused(
            "worktree_exists",
            f"{path} already exists. Remove it first: mise run worktree:remove {slug}",
        )

    # OFF origin/develop, FETCHED FIRST: a worktree cut from a stale develop
    # starts life behind.
    fetched = git("fetch", "origin", "--prune", "--quiet", cwd=root)
    if fetched.returncode != 0:
        note(fetched.stderr.strip())
        raise CommandRefused("fetch_failed", "fetch failed")

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
        note(added.stderr.strip())
        raise CommandRefused("worktree_add_failed", "git worktree add failed")
    note(f"created {path} on {branch}")
    note("running setup in the new worktree...")
    base = git("rev-parse", f"origin/{INTEGRATION_BRANCH}", cwd=root).stdout.strip()
    facts = WorktreeCreated(
        worktree=str(path),
        branch=branch,
        base_ref=f"origin/{INTEGRATION_BRANCH}",
        commit=base,
    )
    if setup(path) != 0:
        return result(
            "worktree:add",
            "failed",
            "setup_failed",
            f"setup failed in {path}: the worktree exists but is not usable. "
            f"Fix setup there, or remove it: mise run worktree:remove {slug}",
            facts,
        )
    note(f"next:\n  cd {path}")
    return result(
        "worktree:add", "success", "worktree_created", f"{path} created on {branch}", facts
    )


def cmd_refresh(slug: str, root: Path) -> int:
    """Merge current origin/develop into a worktree branch.

    A MERGE, NEVER A REBASE. Rebasing rewrites the branch's commits: measured here,
    a branch's own commit stopped being reachable from its own HEAD after a refresh
    that reported success. The next push is then a non-fast-forward, and only a
    force push resolves it -- which this repository never performs. A merge keeps
    every commit reachable, so it is safe whether or not the branch was pushed.
    """
    validate_slug(slug)
    path = sibling_name(main_path(root), slug)
    if not path.exists():
        raise CommandRefused("worktree_missing", f"{path} does not exist")

    status = subprocess.run(
        ["git", "status", "--porcelain", "-z"],  # noqa: S607
        capture_output=True,
        check=False,
        cwd=path,
        env=scrubbed_env(),
    )
    if status.stdout.strip(b"\0"):
        raise CommandRefused(
            "worktree_dirty",
            f"refusing: {path} has uncommitted changes. Commit or discard them first; "
            "--autostash would hide the work in a stash nobody created.",
        )

    fetched = git("fetch", "origin", "--prune", "--quiet", cwd=root)
    if fetched.returncode != 0:
        note(fetched.stderr.strip())
        raise CommandRefused("fetch_failed", "fetch failed")

    # NO PUSHED-BRANCH REFUSAL: it existed only because a rebase would have needed a
    # force push. A merge adds a commit and rewrites none, so a pushed branch is
    # refreshed exactly like a local one.
    before = git("rev-parse", "HEAD", cwd=path).stdout.strip()
    merged = git("merge", "--no-edit", f"origin/{INTEGRATION_BRANCH}", cwd=path)
    if merged.returncode != 0:
        note((merged.stdout + merged.stderr).strip())
        raise CommandRefused(
            "merge_stopped",
            f"the merge stopped in {path}. Resolve the conflicts there and commit, "
            "or abort it with git merge --abort.",
        )
    after = git("rev-parse", "HEAD", cwd=path).stdout.strip()
    target = git("rev-parse", f"origin/{INTEGRATION_BRANCH}", cwd=path).stdout.strip()

    # REPORT AN OBSERVED STATE CHANGE, NOT PARSED OUTPUT: git writes its success
    # message to stderr, and comparing SHAs cannot misreport.
    return result(
        "worktree:refresh",
        "success",
        "already_current" if before == after else "branch_moved",
        f"{path} was already on origin/{INTEGRATION_BRANCH} ({target[:12]})"
        if before == after
        else f"{path}: {before[:12]} -> {after[:12]} (onto {target[:12]})",
        WorktreeRefreshed(
            worktree=str(path),
            before=before,
            after=after,
            base_ref=f"origin/{INTEGRATION_BRANCH}",
            target=target,
        ),
    )


def cmd_remove(slug: str, root: Path) -> int:
    validate_slug(slug)
    path = sibling_name(main_path(root), slug)
    branch = f"feature/{slug}"

    if not path.exists():
        raise CommandRefused("worktree_missing", f"{path} does not exist")

    # NO --force, EVER.
    removed = git("worktree", "remove", str(path), cwd=root)
    if removed.returncode != 0:
        note(removed.stderr.strip())
        raise CommandRefused("remove_refused", f"refused to remove {path}")
    note(f"removed {path}")

    # `-d`, NOT `-D`.
    deleted = git("branch", "-d", branch, cwd=root)
    if deleted.returncode != 0:
        detail = deleted.stderr.strip()
        # ALREADY GONE (usually removed by sync) is not "unmerged".
        if "not found" in detail:
            return result(
                "worktree:remove",
                "success",
                "worktree_removed_branch_gone",
                f"removed the worktree; branch {branch} was already gone",
                WorktreeRemoved(worktree=str(path), branch=branch, branch_deleted=False),
            )
        return result(
            "worktree:remove",
            "refused",
            "branch_unmerged",
            f"worktree removed, but branch {branch} was NOT deleted: {detail}. "
            "That refusal means the branch is unmerged. Merge it first.",
            WorktreeRemoved(worktree=str(path), branch=branch, branch_deleted=False),
        )

    return result(
        "worktree:remove",
        "success",
        "worktree_removed",
        f"removed {path} and deleted {branch}",
        WorktreeRemoved(worktree=str(path), branch=branch, branch_deleted=True),
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    verb = args[0] if args else "usage"
    try:
        return _dispatch(args)
    except CommandRefused as error:
        # A REFUSAL IS AN OUTCOME, not a crash: exit 2, with its machine code.
        return refusal(f"worktree:{verb}", error)


def _dispatch(args: list[str]) -> int:
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
            raise CommandRefused(
                "usage",
                "usage: python -m otsafety_tooling.git.worktree "
                f"add|list|refresh|remove [slug]  (got {other})",
            )


if __name__ == "__main__":
    raise SystemExit(main())
