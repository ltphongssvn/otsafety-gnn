# tooling/src/otsafety_tooling/git/sync.py
"""Advance develop wherever it is checked out, then remove finished branches.

STATE-DRIVEN, NOT A PIPELINE. The plan is computed BEFORE anything is deleted,
which makes it printable, testable without a repository, and impossible to
abort partway through with half the decisions unmade.

WHAT IT REFUSES TO DO SILENTLY: skip a branch. Every branch whose upstream
vanished but which cannot be removed is reported with the reason.

ADVANCING develop DEPENDS ON WHO HOLDS IT, and getting that wrong broke this
task the moment the main checkout sat on develop, which is its tidy state:

    held by THIS checkout    merge --ff-only origin/develop, in place
    held by ANOTHER worktree leave it; git refuses a refspec fetch into a
                             checked-out branch, and the cleanup plan reads
                             origin/develop, which the plain fetch refreshed
    held by NOBODY           advance the ref with a refspec fetch
    genuinely diverged       refuse, and say so with the counts

The old code always used the refspec fetch and reported every refusal as
divergence -- while the branch report, from the same facts, correctly said
develop was three commits BEHIND.

THE SAME TASK ON EVERY MACHINE. The laptop, Lightning AI and FAS OnDemand all
run `mise run sync`; only the transport to GitHub differs (SSH or HTTPS).

PRIVACY. Another checkout is named by its folder name, never its absolute path.

Ported from cscie103-olap-oltp (src/cscie103_olap_oltp/git/sync.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.git.env import git
from otsafety_tooling.git.state import (
    INTEGRATION_BRANCH,
    PROTECTED_BRANCHES,
    Branch,
    RepositoryState,
    gather,
)
from otsafety_tooling.paths import REPO_ROOT

REMOTE_INTEGRATION = f"origin/{INTEGRATION_BRANCH}"


class CleanupPlan(BaseModel):
    """What cleanup intends to do, decided before it does any of it."""

    model_config = ConfigDict(frozen=True)

    remove: tuple[Branch, ...]
    blocked: tuple[Branch, ...]


def plan_cleanup(state: RepositoryState, *, prune: bool = False) -> CleanupPlan:
    """Split branches into removable and blocked, leaving work in progress alone."""
    # Empty, never-pushed branches join only on request: start:here cuts empty ones.
    return CleanupPlan(
        remove=state.deletable + (state.prunable if prune else ()), blocked=state.blocked
    )


def is_linked_worktree(root: Path) -> bool:
    """Whether `root` is a linked worktree, by git's own comparison.

    Inside a linked worktree $GIT_DIR is a private directory while
    $GIT_COMMON_DIR points back at the main repository.
    """
    private = git("rev-parse", "--absolute-git-dir", cwd=root).stdout.strip()
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=root)
    return bool(private) and private != common.stdout.strip()


def develop_holder(state: RepositoryState) -> Path | None:
    """The checkout that holds develop, from the facts already gathered."""
    for worktree in state.worktrees:
        if worktree.branch == INTEGRATION_BRANCH:
            return worktree.path
    return None


def holder_of(state: RepositoryState, name: str) -> Path | None:
    """The checkout that holds a branch, from the facts already gathered."""
    for worktree in state.worktrees:
        if worktree.branch == name:
            return worktree.path
    return None


def _counts(root: Path, name: str, remote: str) -> tuple[int, int]:
    """(ahead, behind) of a branch against its remote counterpart."""
    result = git("rev-list", "--left-right", "--count", f"{name}...{remote}", cwd=root)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"could not compare {name} with {remote}")
    ahead, behind = result.stdout.split()
    return int(ahead), int(behind)


def _has(root: Path, ref: str) -> bool:
    return git("rev-parse", "--verify", "--quiet", ref, cwd=root).returncode == 0


def advance_protected(root: Path, name: str, *, fetch: bool = True) -> None:
    """Bring a protected branch up to its remote, in whatever way its checkout allows.

    EVERY PROTECTED BRANCH, NOT ONLY develop. Advancing develop alone left main 59
    commits behind origin/main across two promotions, and the branch report failed
    on B001 after every release. Git Town syncs every perennial branch; so does this,
    by one path, so main and develop can never be advanced by different rules.
    """
    remote = f"origin/{name}"
    if fetch:
        # --prune IS WHAT MAKES [gone] MEAN ANYTHING, and it must not be scoped to a
        # refspec: with one on the command line git prunes only what it covers, so
        # merged remote branches survived and cleanup found nothing to do.
        pruned = git("fetch", "origin", "--prune", cwd=root)
        if pruned.returncode != 0:
            print(pruned.stderr.strip(), file=sys.stderr)
            raise SystemExit("could not fetch from origin")
    if not _has(root, f"refs/heads/{name}") or not _has(root, f"refs/remotes/{remote}"):
        return

    ahead, behind = _counts(root, name, remote)
    if ahead and behind:
        raise SystemExit(
            f"{name} has diverged from {remote}: {ahead} ahead, {behind} behind. "
            "sync will not resolve that for you."
        )
    if not behind:
        print(f"{name} up to date")
        return

    holder = holder_of(gather(root), name)
    here = holder is not None and holder.resolve() == root.resolve()

    if here:
        merged = git("merge", "--ff-only", remote, cwd=root)
        if merged.returncode != 0:
            print(merged.stderr.strip(), file=sys.stderr)
            raise SystemExit(f"{name} could not fast-forward here")
        print(f"{name} advanced {behind} commit(s) in this checkout")
        return

    if holder is not None:
        # git REFUSES a refspec fetch into a branch that is checked out anywhere.
        print(
            f"{name} is {behind} commit(s) behind and is checked out in "
            f"{holder.name}; run sync there to advance it"
        )
        return

    fetched = git("fetch", "origin", f"{name}:{name}", cwd=root)
    if fetched.returncode != 0:
        print(fetched.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"{name} could not be advanced")
    print(f"{name} advanced {behind} commit(s)")


def advance_develop(root: Path) -> None:
    """Bring develop up to origin/develop; one caller of advance_protected."""
    advance_protected(root, INTEGRATION_BRANCH)


def switch_command(branch: str, state: RepositoryState, root: Path = REPO_ROOT) -> str:
    """The command that moves THIS shell to an existing branch, for eval.

    A task runs in a subshell and cannot change the caller's branch, so the
    command is printed, exactly as start:here prints the command that creates
    one. Freeing develop for sync left this checkout on an empty branch with no
    task able to leave it.

    REFUSES BEFORE git WOULD
      an unknown branch, named;
      one another worktree holds, since git allows one checkout per branch;
      a DIRTY tree -- git carries uncommitted changes across a switch, and the
      first use of this task moved four uncommitted files onto develop.
      worktree:refresh refuses a dirty tree for the same reason.

    The other checkout is named by its folder, never by its path.
    """
    if not branch:
        raise SystemExit("name the branch to switch to")

    known = {existing.name: existing for existing in state.branches}
    wanted = known.get(branch)
    if wanted is None:
        raise SystemExit(f"no local branch named {branch!r}; known: {', '.join(sorted(known))}")
    if wanted.held_by is not None:
        raise SystemExit(
            f"{branch} is checked out in the worktree {wanted.held_by.name}; "
            "git allows one checkout per branch"
        )

    here = root.resolve()
    for worktree in state.worktrees:
        if worktree.path.resolve() == here and worktree.is_dirty:
            raise SystemExit(
                f"refusing: this checkout has uncommitted changes, and git would carry "
                f"them onto {branch}. Commit them first, or start a branch for them with "
                "start:here."
            )
    return f"git switch {branch}"


def finished_branch_to_leave(state: RepositoryState, root: Path) -> Branch | None:
    """The branch this checkout is standing on, if it is finished and safe to leave.

    ADAPTED FOR A SINGLE-CLONE LAYOUT. cscie103-olap-oltp keeps every branch in
    a linked worktree, so cleanup never stands on what it removes. A plain
    clone (the usual layout on FAS OnDemand and Lightning) is still ON the
    feature branch after its pull request merges -- held by this very checkout,
    so it could never be removed.

    FINISHED MEANS ITS WORK IS IN develop, in either of two ways:
      - it was merged and its remote branch has since been deleted, or
      - it adds nothing to develop at all, which includes a branch created only
        to free develop and never pushed.
    Both are `is_merged`, so the check is merged-and-not-protected; a branch
    with commits of its own is not merged and is left alone.

    SWITCHING IS SAFE ONLY WHEN NOTHING CAN BE LOST, so a dirty tree is never
    left; it is reported by the plan instead.
    """
    here = root.resolve()
    for worktree in state.worktrees:
        if worktree.path.resolve() != here or worktree.is_dirty or worktree.is_bare:
            continue
        for branch in state.branches:
            if branch.name == worktree.branch and not branch.is_protected and branch.is_merged:
                return branch
    return None


def switch(branch: str) -> int:
    """Print the command that moves the caller's shell to an existing branch."""
    print(switch_command(branch, gather(REPO_ROOT)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    prune = "--prune" in args
    args = [arg for arg in args if arg != "--prune"]
    if args[:1] == ["switch"]:
        if len(args) != 2:
            raise SystemExit("usage: python -m otsafety_tooling.git.sync switch <branch>")
        return switch(args[1])
    if args:
        raise SystemExit("usage: python -m otsafety_tooling.git.sync [--prune | switch <branch>]")

    # EVERY PROTECTED BRANCH: develop first, which fetches once, then the rest.
    advance_develop(REPO_ROOT)
    for protected in sorted(PROTECTED_BRANCHES - {INTEGRATION_BRANCH}):
        advance_protected(REPO_ROOT, protected, fetch=False)

    if not is_linked_worktree(REPO_ROOT):
        leaving = finished_branch_to_leave(gather(REPO_ROOT), REPO_ROOT)
        if leaving is not None:
            switched = git("switch", INTEGRATION_BRANCH, cwd=REPO_ROOT)
            if switched.returncode != 0:
                print(switched.stderr.strip(), file=sys.stderr)
                raise SystemExit(f"could not leave {leaving.name} for {INTEGRATION_BRANCH}")
            print(f"left finished branch {leaving.name}; now on {INTEGRATION_BRANCH}")

    plan = plan_cleanup(gather(REPO_ROOT), prune=prune)

    for branch in plan.remove:
        # `-d`, NEVER `-D`: git independently confirms the merge happened.
        result = git("branch", "-d", branch.name, cwd=REPO_ROOT)
        if result.returncode == 0:
            print(f"removed {branch.name}")
        else:
            print(f"could not remove {branch.name}: {result.stderr.strip()}", file=sys.stderr)

    if plan.blocked:
        print("\nnot removed:")
        for branch in plan.blocked:
            print(f"  {branch.name}: {branch.blocked_because}")

    # KEPT, AND SAID SO: an empty branch that was never pushed waits for --prune,
    # because start:here cuts empty branches too. It is listed rather than hidden.
    waiting = () if prune else gather(REPO_ROOT).prunable
    if waiting:
        print("\nempty and never pushed, kept until asked:")
        for branch in waiting:
            print(f"  {branch.name}: {branch.blocked_because}")

    if not plan.remove and not plan.blocked and not waiting:
        print("nothing to clean up")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
