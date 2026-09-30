# tooling/src/otsafety_tooling/git/freshness.py
"""Work built on a base that has moved does not push.

EVERY GATE HERE ANSWERS A QUESTION ABOUT A PARTICULAR DEVELOP. The plan's
status, the exemption register, the task inventory and the trailer rule are all
judged against the tree the branch forked from -- so a branch pushed behind its
base was verified against a question nobody asked, and its green is about a
repository that no longer exists.

THIS IS THE ENFORCEMENT HALF OF THE MERGE RULE. A dependency update that merges
itself moves develop; work cut before it and pushed after was written against a
tree that is gone. deps:merge is the other half.

AGAINST origin/develop, NEVER A LOCAL BRANCH. A local develop that nobody
updates is stale by construction, and comparing against it counts every commit
the real base gained as the branch's own -- a defect two projects filed within
one day of each other.

WHAT THIS CANNOT SEE: a base that moves AFTER the push. Both of another
project's pushes were clean when made, and the conflict came from the base
moving afterwards. This refuses work already known to be behind, and claims
nothing about later.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, NonNegativeInt

from otsafety_tooling.cli import CommandRefused, note, refusal
from otsafety_tooling.cli import result as emit_result
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

# THE REMOTE-TRACKING REF, so the comparison is against what origin holds
# rather than against whatever this checkout last pulled.
BASE = "origin/develop"

TAGS = "refs/tags/"


class Verdict(BaseModel):
    """Whether this branch may push, and the reason either way."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    why: str


def asks_about_freshness(refs: list[str]) -> bool:
    """Whether "is this behind the base" is the question being asked.

    A TAG NAMES A COMMIT THAT ALREADY EXISTS. Whether it contains the base is
    not the question, and asking it refused ninety-one tag pushes in one run
    elsewhere. A push of nothing asks nothing either.
    """
    return bool(refs) and not all(ref.startswith(TAGS) for ref in refs)


def behind_base(root: Path) -> Verdict:
    """Whether the branch has every commit the base holds."""
    counted = git("rev-list", "--count", f"HEAD..{BASE}", cwd=root)
    if counted.returncode != 0:
        # NO BASE TO COMPARE AGAINST IS NOT A REFUSAL. A fresh clone with no
        # remote-tracking ref yet, or a repository without origin, cannot be
        # judged -- and a gate that cannot see must not report success as
        # failure any more than the reverse.
        return Verdict(allowed=True, why=f"{BASE} is not there to compare against")

    behind = int(counted.stdout.strip())
    if not behind:
        return Verdict(allowed=True, why=f"this branch holds every commit {BASE} does")
    return Verdict(
        allowed=False,
        why=(
            f"refusing: this branch is {behind} commit(s) behind {BASE}, so every gate "
            f"it passed answered for a tree that has moved. Bring it forward with: "
            f"mise run worktree:refresh <slug>"
        ),
    )


class Freshness(BaseModel):
    """What the gate observed about this branch's base."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base: str
    behind: NonNegativeInt


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Refuse a branch whose base has moved; a refusal is an outcome.

    root IS AN ARGUMENT SO THE TESTS DRIVE IT against a real repository they
    built, rather than against whichever one the suite happens to run in.
    """
    try:
        return _dispatch(argv, root=root or REPO_ROOT)
    except CommandRefused as error:
        return refusal("start:fresh", error)


def _dispatch(argv: list[str] | None, *, root: Path) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        raise CommandRefused("usage", "usage: python -m otsafety_tooling.git.freshness")

    counted = git("rev-list", "--count", f"HEAD..{BASE}", cwd=root)
    behind = int(counted.stdout.strip()) if counted.returncode == 0 else 0
    verdict = behind_base(root)
    if not verdict.allowed:
        note(verdict.why)
        raise CommandRefused("base_moved", verdict.why, Freshness(base=BASE, behind=behind))
    return emit_result(
        "start:fresh", "success", "base_current", verdict.why, Freshness(base=BASE, behind=0)
    )


if __name__ == "__main__":
    raise SystemExit(main())
