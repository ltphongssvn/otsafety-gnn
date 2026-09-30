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
import sys
from collections.abc import Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, JsonValue, PositiveInt

from otsafety_tooling.cli import CommandRefused, note, refusal
from otsafety_tooling.cli import result as emit_result
from otsafety_tooling.git.pr import gh, merge_existing

# ONE ACTOR, TWO IDENTIFIERS. gh reports a pull request's author as
# "app/dependabot"; a commit carries "49699333+dependabot[bot]@users.noreply
# .github.com". Neither string contains the other, so a rule written against one
# cannot recognise the other -- and the trailer policy learned the address form
# first, separately. Both are declared here, and that policy reads this set.
UpdateKind = Literal["patch", "minor", "major"]

BOT = "app/dependabot"
BOT_COMMIT_ADDRESSES = frozenset({"49699333+dependabot[bot]@users.noreply.github.com"})


def is_the_bot(author: str) -> bool:
    """Whether a pull request's author is the dependency bot, as gh names it."""
    return author.strip() == BOT


class UpdateUnreadableError(RuntimeError):
    """The update's size could not be established, so nothing may be assumed."""


_STATED = re.compile(r"update-type:\s*version-update:semver-(patch|minor|major)")
_VERSION = re.compile(r"dependency-version:\s*([0-9]+)")


def kind_of(commit_body: str, previous: str | None = None) -> UpdateKind:
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
    # THE REGEX CAPTURES EXACTLY THE THREE, so the cast states what the
    # pattern already guarantees rather than widening the return to str.
    stated: UpdateKind = cast("UpdateKind", found.group(1))

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


class _Author(_Strict):
    login: str


class _ChangedFile(_Strict):
    path: str


class PullRequestShape(BaseModel):
    """What gh --json reports, as much of it as this rule reads.

    extra="ignore": gh returns many fields beyond these three, and forbidding
    them would refuse a pull request for carrying information we do not need.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    number: PositiveInt
    author: _Author
    files: tuple[_ChangedFile, ...] = ()


class Update(_Strict):
    """One open dependency pull request, as the verdict needs to see it.

    kind IS A CLOSED SET, so an update whose size could not be read fails
    validation rather than arriving as something small by default.
    """

    number: PositiveInt
    kind: UpdateKind
    touches_workflows: bool


class Verdict(_Strict):
    """Whether this update may merge unattended, and the reason either way."""

    allowed: bool
    why: str


class NotTheBotError(RuntimeError):
    """This pull request is not a dependency update, so no verdict applies."""


WORKFLOWS = ".github/workflows/"


def read_update(reported: JsonValue, *, commit_body: str, previous: str | None = None) -> Update:
    """One open pull request as gh reports it, read into the shape a verdict needs.

    FROM THE JSON, NOT THE HUMAN OUTPUT. gh --json gives the author's login, the
    number and the changed paths; its default rendering is for a terminal and
    changes with the tool.

    THE AUTHOR IS CHECKED FIRST, and a person's pull request raises rather than
    returning "not allowed": a verdict about whether a dependency update may
    merge says nothing about work somebody wrote.
    """
    shape = PullRequestShape.model_validate(reported)
    if not is_the_bot(shape.author.login):
        raise NotTheBotError(
            f"PR #{shape.number} is by {shape.author.login}, not {BOT}: "
            "this rule judges dependency updates and nothing else"
        )
    return Update(
        number=shape.number,
        kind=kind_of(commit_body, previous=previous),
        touches_workflows=any(f.path.startswith(WORKFLOWS) for f in shape.files),
    )


class Held(_Strict):
    """An update left for a person, with the reason it was left."""

    number: PositiveInt
    why: str


class Decided(_Strict):
    """Every open update, split by what the rule allows.

    BOTH SIDES ARE CARRIED. A command reporting only what it merged hides what
    it left, which is how a major bump sits for weeks with nobody reminded that
    it is waiting. The envelope names the ones held back and why.
    """

    merging: tuple[Update, ...] = ()
    waiting: tuple[Held, ...] = ()


def decide_all(updates: Sequence[Update]) -> Decided:
    """Judge every open update; nothing to merge is an outcome, not a failure."""
    merging: list[Update] = []
    waiting: list[Held] = []
    for update in updates:
        verdict = may_merge(update)
        if verdict.allowed:
            merging.append(update)
        else:
            waiting.append(Held(number=update.number, why=verdict.why))
    return Decided(merging=tuple(merging), waiting=tuple(waiting))


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


class UpdatesDecided(_Strict):
    """What the run merged and what it left, both named."""

    merged: tuple[int, ...]
    waiting: tuple[Held, ...]


OPEN_FIELDS = "number,author,files"


class _OpenList(BaseModel):
    """gh returns a JSON ARRAY; a model parses it, because raw parsing is banned.

    RootModel IS THE SHAPE FOR A TOP-LEVEL ARRAY. files.py reads paths and YAML
    strings and has no reader for a JSON string, and pr.py meets the same
    boundary with model_validate_json on the model itself.
    """

    model_config = ConfigDict(frozen=True)

    entries: tuple[PullRequestShape, ...]


def open_updates() -> tuple[Update, ...]:
    """Every open pull request the bot opened, read through the model.

    THE COMMIT BODY CARRIES THE UPDATE TYPE, so each pull request is asked for
    its commits as well: gh does not put the trailer in the pull request's own
    fields, and the body's prose is for people.
    """
    listed = _OpenList.model_validate_json(
        '{"entries": ' + gh("pr", "list", "--state", "open", "--json", OPEN_FIELDS) + "}"
    )
    out: list[Update] = []
    for shape in listed.entries:
        if not is_the_bot(shape.author.login):
            continue
        body = gh(
            "pr", "view", str(shape.number), "--json", "commits", "--jq", ".commits[].messageBody"
        )
        out.append(
            Update(
                number=shape.number,
                kind=kind_of(body),
                touches_workflows=any(f.path.startswith(WORKFLOWS) for f in shape.files),
            )
        )
    return tuple(out)


def main(argv: list[str] | None = None) -> int:
    """Judge every open update, merge what the rule allows, and say what waits."""
    try:
        return _dispatch(argv)
    except CommandRefused as error:
        return refusal("deps:merge", error)


def _dispatch(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        raise CommandRefused("usage", "usage: python -m otsafety_tooling.git.deps")

    decided = decide_all(open_updates())
    for update in decided.merging:
        note(f"merging PR #{update.number}: a {update.kind} bump touching no workflow")
        merge_existing(update.number)
    for held in decided.waiting:
        note(f"waiting: {held.why}")

    merged = tuple(u.number for u in decided.merging)
    return emit_result(
        "deps:merge",
        "success",
        "updates_decided",
        f"{len(merged)} merged, {len(decided.waiting)} waiting for a person",
        UpdatesDecided(merged=merged, waiting=decided.waiting),
    )


if __name__ == "__main__":
    raise SystemExit(main())
