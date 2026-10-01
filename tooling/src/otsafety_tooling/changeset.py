# tooling/src/otsafety_tooling/changeset.py
# G.88: proves this step of the plan.
"""A change to several files: validated whole, published together, or not at all.

EACH FILE WAS ATOMIC; THE CHANGE WAS NOT. Every multi-file edit in this
repository's history went through a script that edited and wrote one file at a
time, validating whatever was remembered that turn -- one parsed the TOML it
changed and wrote the workflow YAML unchecked, though a contract for workflows
existed. A refusal on the last file left the earlier ones written.

THE ORDER, AND WHAT EACH STEP REFUSES:

  no path twice              whichever candidate won would be an accident;
  every file as it was read  a change computed from stale content is refused,
                             never written over someone else's edit;
  every candidate valid      each through ITS OWN contract, by the sanctioned
                             parsers -- a file that parses and breaks its
                             contract is exactly as broken as one that does not;
  every invariant held       checked over the candidates together, because two
                             files can each be valid and wrong as a pair;
  every file staged          beside its target, flushed and synced;
  nothing moved meanwhile    re-checked immediately before the first publish;
  then published, in order   and if one fails, what already landed goes back.

Everything up to the first publish touches no target, so every refusal there
leaves the repository exactly as it was.

WHAT THIS CANNOT PROMISE, stated rather than implied. POSIX offers no
transaction across paths: each replace is atomic, the set is not. Putting back
a landed prefix is best effort, and a process killed between two publishes
leaves that prefix in place. In a git working tree the diff is the journal that
shows it; this module does not pretend to be one.

A RETRY IS SAFE. A file already holding its desired content counts as done
rather than as stale, so running the same change again after it succeeded
changes nothing and refuses nothing.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from otsafety_tooling import atomic
from otsafety_tooling.contracts.files import parse_toml, parse_yaml

# AN INVARIANT RAISES ValueError when the candidates break it, as a validator does.
Invariant = Callable[[Mapping[Path, str]], None]


class ChangeRefusedError(Exception):
    """The change was not made, and why; which files, if any, may differ."""


@dataclass(frozen=True)
class Change:
    """One file's part of a change: what it was, what it becomes, how to judge it."""

    path: Path
    # THE SHA-256 OF THE TEXT THE CHANGE WAS COMPUTED FROM, or None when the
    # file must not exist yet.
    expected: str | None
    content: str
    # PARSES THE CANDIDATE THROUGH ITS CONTRACT, raising ValueError if it is
    # not one. ONLY ValueError: any other exception is a defect in the
    # validator, and it propagates as itself rather than being blamed on the
    # file -- catching everything reported my code's error as the file's.
    validate: Callable[[str], object]


def digest(text: str) -> str:
    """The identity of a file's content, as a change records it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def toml_contract[M: BaseModel](model: type[M]) -> Callable[[str], M]:
    """Judge candidate TOML by its model, through the sanctioned parser."""
    return lambda text: parse_toml(text, model)


def yaml_contract[M: BaseModel](model: type[M]) -> Callable[[str], M]:
    """Judge candidate YAML by its model, through the sanctioned parser.

    YAML'S PARSER RAISES ITS OWN ERROR, which is not a ValueError, so it is
    translated here -- the one place it can arise -- and a malformed workflow
    is refused like any other invalid candidate rather than escaping as a crash.
    """

    def judged(text: str) -> M:
        try:
            return parse_yaml(text, model)
        except yaml.YAMLError as error:
            raise ValueError(f"not valid YAML: {error}") from error

    return judged


def _current(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _publish(staged: Path, target: Path) -> None:
    """THE ONE STEP THAT TOUCHES A TARGET, and the seam tests inject failures at."""
    os.replace(staged, target)


def _pending(changes: Sequence[Change]) -> list[tuple[Change, str | None]]:
    """Each change still to make, with the text it was found holding."""
    seen: set[Path] = set()
    pending: list[tuple[Change, str | None]] = []
    for change in changes:
        where = change.path.resolve()
        if where in seen:
            raise ChangeRefusedError(f"{change.path} appears twice in one change")
        seen.add(where)

        found = _current(change.path)
        if found is not None and digest(found) == digest(change.content):
            continue  # ALREADY DONE: a retry after success changes nothing
        if change.expected is None and found is not None:
            raise ChangeRefusedError(f"{change.path} already exists; it was meant to be new")
        if change.expected is not None and (found is None or digest(found) != change.expected):
            raise ChangeRefusedError(
                f"{change.path} changed since the change was computed; nothing was written"
            )
        pending.append((change, found))
    return pending


def apply(changes: Sequence[Change], *, invariants: Sequence[Invariant] = ()) -> None:
    """Make every change, or none of them."""
    pending = _pending(changes)

    for change, _ in pending:
        try:
            change.validate(change.content)
        except ValueError as error:
            raise ChangeRefusedError(f"{change.path} would break its contract: {error}") from error

    world = {change.path: change.content for change in changes}
    for invariant in invariants:
        try:
            invariant(world)
        except ValueError as error:
            raise ChangeRefusedError(
                f"the change breaks an invariant across files: {error}"
            ) from error

    staged: list[tuple[Change, str | None, Path]] = []
    try:
        for change, found in pending:
            staged.append(
                (change, found, atomic.stage(change.path, change.content.encode("utf-8")))
            )

        # NOTHING MOVED MEANWHILE. Validation took time, and another writer may
        # have changed a target since it was read.
        for change, found, _ in staged:
            if _current(change.path) != found:
                raise ChangeRefusedError(f"{change.path} changed while the change was staged")
    except BaseException:
        for _, _, file in staged:
            file.unlink(missing_ok=True)
        raise

    published: list[tuple[Change, str | None]] = []
    for index, (change, found, file) in enumerate(staged):
        try:
            _publish(file, change.path)
        except OSError as error:
            for _, _, waiting in staged[index:]:
                waiting.unlink(missing_ok=True)
            unrestored = _put_back(published)
            detail = f"; NOT restored: {', '.join(unrestored)}" if unrestored else ""
            raise ChangeRefusedError(
                f"publishing {change.path} failed, and what had landed was put back"
                f"{detail}: {error}"
            ) from error
        published.append((change, found))

    for folder in {change.path.parent for change, _ in published}:
        atomic.sync_directory(folder)


def _put_back(published: Sequence[tuple[Change, str | None]]) -> list[str]:
    """Restore each file that landed, newest first; name any that could not be."""
    failed: list[str] = []
    for change, found in reversed(published):
        try:
            if found is None:
                change.path.unlink(missing_ok=True)
            else:
                atomic.write_text(change.path, found)
        except OSError:
            failed.append(str(change.path))
    return failed
