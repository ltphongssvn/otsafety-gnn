# tooling/src/otsafety_tooling/git/deps.py
"""Which dependency updates merge themselves, and which wait for a person.

MERGED HERE, NOT ON THE SERVER. GitHub's auto-merge arms only while a pull
request is blocked and then merges with no record in this repository. Every
merge here goes through pr.py, which observes the checks, verifies that every
required one reported, acts, and observes the result -- and merge_existing is
already written for a pull request nobody has checked out.

A MAJOR BUMP IS NOT AN UPDATE, IT IS A CHANGE OF BEHAVIOUR. The open case as
this was written: actions/upload-artifact 4.6.2 to 7.0.1, three majors, which
alters artifact merge semantics and raises the minimum runner version. 2026
practice groups patch and minor into one pull request and leaves majors
standalone precisely so that review is honest.

AND AN UPDATE THAT TOUCHES A WORKFLOW WAITS WHATEVER ITS SIZE. A green suite
proves the tests still ran; it does not prove the new action is safe. That
distinction is why supply-chain guidance treats action bumps apart from library
bumps, and why this repository pins every action to a commit SHA.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, PositiveInt

# ONE ACTOR, TWO IDENTIFIERS. gh reports a pull request's author as
# "app/dependabot"; a commit carries "49699333+dependabot[bot]@users.noreply
# .github.com". Neither string contains the other, so a rule written against one
# cannot recognise the other -- and the trailer policy learned the address form
# first, separately. Both are declared here, and that policy reads this set.
BOT = "app/dependabot"
BOT_COMMIT_ADDRESSES = frozenset({"49699333+dependabot[bot]@users.noreply.github.com"})


def is_the_bot(author: str) -> bool:
    """Whether a pull request's author is the dependency bot, as gh names it."""
    return author.strip() == BOT


class UpdateUnreadableError(RuntimeError):
    """The update's size could not be established, so nothing may be assumed."""


_STATED = re.compile(r"update-type:\s*version-update:semver-(patch|minor|major)")
_VERSION = re.compile(r"dependency-version:\s*([0-9]+)")


def kind_of(commit_body: str, previous: str | None = None) -> str:
    """The update's size, taken from the trailer Dependabot writes.

    NOTHING PARSES THE PROSE. Dependabot states the type in a machine-readable
    trailer, which is what GitHub's own fetch-metadata reads; the body's
    sentence about versions is for people.

    AND A SECOND READING CHECKS THE FIRST when the previous version is known.
    G.80's lesson: one stated string is checked by nothing. Comparing the major
    components catches a trailer that disagrees with its own versions, and the
    disagreement is refused rather than resolved in either direction.
    """
    found = _STATED.search(commit_body)
    if found is None:
        raise UpdateUnreadableError(
            "no update-type trailer: the size of this update is unstated, and an "
            "unstated update is not a patch"
        )
    stated = found.group(1)

    if previous is None:
        return stated

    to = _VERSION.search(commit_body)
    if to is None:
        raise UpdateUnreadableError("the trailer names a type but no dependency-version")
    crossed_a_major = int(to.group(1)) != int(previous.split(".")[0])
    if crossed_a_major != (stated == "major"):
        raise UpdateUnreadableError(
            f"the trailer says {stated} while the versions go {previous} -> {to.group(1)}; "
            "the two readings disagree, so neither is trusted"
        )
    return stated


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Update(_Strict):
    """One open dependency pull request, as the verdict needs to see it.

    kind IS A CLOSED SET, so an update whose size could not be read fails
    validation rather than arriving as something small by default.
    """

    number: PositiveInt
    kind: Literal["patch", "minor", "major"]
    touches_workflows: bool


class Verdict(_Strict):
    """Whether this update may merge unattended, and the reason either way."""

    allowed: bool
    why: str


def may_merge(update: Update) -> Verdict:
    """Patch and minor merge themselves; a major, or a workflow change, waits."""
    if update.kind == "major":
        return Verdict(
            allowed=False,
            why=(
                f"PR #{update.number} is a major bump: a change of behaviour rather than "
                "an update, so it waits for a person to read what changed"
            ),
        )
    if update.touches_workflows:
        return Verdict(
            allowed=False,
            why=(
                f"PR #{update.number} changes a workflow: a green suite proves the tests "
                "ran, not that the new action is safe"
            ),
        )
    return Verdict(
        allowed=True,
        why=f"PR #{update.number} is a {update.kind} bump touching no workflow",
    )
