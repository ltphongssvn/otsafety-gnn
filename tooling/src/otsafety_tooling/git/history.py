# tooling/src/otsafety_tooling/git/history.py
"""The repository's history, read as records rather than parsed as text.

WHY THIS EXISTS. Reading history was the one operation with no task, so every
question about what the repository had already solved was answered with a raw
`git log | grep` -- a throw-away command, run differently each time, recorded
nowhere. The rule here is that every operation is a task.

THE FRAMING IS NUL, AND ONLY NUL. A parser that separates records with the
ASCII record separator assumes that byte never appears in commit metadata. A
commit message is arbitrary bytes: anyone who can write a commit can write
\\x1e, and the reader then sees one commit as two. NUL is the one byte a commit
message cannot hold, because git itself refuses it.

AND THE FIELD COUNT IS THE FRAME. Every record is exactly as many fields as the
format declares, so a record with the wrong number -- output cut short, or a
forged boundary -- is discarded rather than read as a half-commit. Validating
the shape IS the framing, not a check bolted on after it.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.cli import CommandRefused, note, refusal
from otsafety_tooling.cli import result as emit_result
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

# EVERY FIELD IS NUL-TERMINATED, INCLUDING THE LAST. A trailing terminator means
# the final record is closed rather than merely ended, so a truncated read is
# visible as a short record instead of a complete-looking one.
FIELDS = ("sha", "parents", "author", "message")
LOG_FORMAT = "%H%x00%P%x00%ae%x00%B%x00"


class Commit(BaseModel):
    """One commit, as the history reads it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sha: str
    parents: str
    author: str
    message: str

    @property
    def is_merge(self) -> bool:
        """Two parents or more. Read from the parents, never from the subject."""
        return len(self.parents.split()) > 1

    @property
    def subject(self) -> str:
        """The first line, which is what a listing shows."""
        return self.message.splitlines()[0] if self.message else ""


def parse_log(output: str) -> tuple[Commit, ...]:
    """Every whole record in `output`; a short or forged one is discarded.

    git log ENDS EACH RECORD WITH A NEWLINE, which belongs to no field: the
    format's last terminator closes the message, then git writes the separator
    it always writes between entries. Splitting on NUL alone therefore left
    that newline at the FRONT of the next record's sha, and the trailer policy
    -- looking up a plan at ref "\n009e9d31" -- reported 107 good commits as
    naming no step.

    IT IS STRIPPED FROM THE SHA ALONE. lstrip on every field would eat a body's
    own leading blank line, which is content; only the first field of a record
    can carry the separator git inserted.
    """
    pieces = output.split("\x00")
    width = len(FIELDS)
    whole = len(pieces) // width
    out: list[Commit] = []
    for index in range(whole):
        record = pieces[index * width : (index + 1) * width]
        record[0] = record[0].lstrip("\n")
        out.append(Commit(**dict(zip(FIELDS, record, strict=True))))
    return tuple(out)


def read_history(root: Path, since: str | None = None) -> tuple[Commit, ...]:
    """Every commit from `since` to HEAD, or the whole history."""
    span = [f"{since}..HEAD"] if since else []
    shown = git("log", f"--format={LOG_FORMAT}", *span, cwd=root)
    if shown.returncode != 0:
        raise CommandRefused("history_unreadable", f"cannot read history: {shown.stderr.strip()}")
    return parse_log(shown.stdout)


def matching(commits: Sequence[Commit], text: str) -> tuple[Commit, ...]:
    """Commits whose MESSAGE contains `text`, case-insensitively.

    THE MESSAGE, NOT THE RENDERED LINE. A grep over raw log output matches a
    sha or an author as readily as a subject, so it answers a different
    question from the one being asked: what has this repository already said
    about a thing.
    """
    wanted = text.casefold()
    return tuple(commit for commit in commits if wanted in commit.message.casefold())


class Match(BaseModel):
    """One commit a search named: enough to choose it, not its whole message.

    A SEARCH NAMES WHICH; A READ FETCHES ONE. Carrying every matched body put
    83,525 bytes in one envelope here -- past the 64 KiB this repository's own
    run records hold themselves to -- and a caller almost never wants them all.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sha: str
    subject: str


def found_in(root: Path, text: str) -> tuple[Match, ...]:
    """Which commits say `text`, as identifiers and subjects."""
    return tuple(
        Match(sha=commit.sha, subject=commit.subject)
        for commit in matching(read_history(root), text)
    )


def read_one(root: Path, sha: str) -> Commit:
    """One commit, whole, for a sha a search named."""
    shown = git("log", "-1", f"--format={LOG_FORMAT}", sha, cwd=root)
    if shown.returncode != 0:
        raise CommandRefused("no_such_commit", f"{sha} names no commit here")
    read = parse_log(shown.stdout)
    if not read:
        raise CommandRefused("no_such_commit", f"{sha} names no commit here")
    return read[0]


class Found(BaseModel):
    """What the search found, as data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    searched: str
    commits: tuple[Match, ...]


def main(argv: list[str] | None = None) -> int:
    """A refusal is an outcome: exit 2 with a machine code, never a crash."""
    try:
        return _dispatch(argv)
    except CommandRefused as error:
        return refusal("history:log", error)


def _dispatch(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["show"] and len(args) == 2:
        commit = read_one(REPO_ROOT, args[1])
        note(commit.message)
        return emit_result(
            "history:log",
            "success",
            "commit_read",
            f"{commit.sha[:9]} {commit.subject}",
            commit,
        )
    if len(args) != 1 or not args[0].strip():
        raise CommandRefused(
            "usage",
            "usage: python -m otsafety_tooling.git.history <text> | show <sha>",
        )

    text = args[0]
    found = found_in(REPO_ROOT, text)
    for match in found:
        note(f"{match.sha[:9]} {match.subject}")
    return emit_result(
        "history:log",
        "success",
        "history_read",
        f"{len(found)} commit(s) say {text!r}; read one with: mise run history:log show <sha>",
        Found(searched=text, commits=found),
    )


if __name__ == "__main__":
    raise SystemExit(main())
