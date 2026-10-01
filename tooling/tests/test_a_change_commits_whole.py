# tooling/tests/test_a_change_commits_whole.py
"""A change to several files is validated whole and published together (G.88).

EACH FILE WAS ATOMIC; THE CHANGE WAS NOT. Every multi-file edit this session
went through a script that edited and wrote one file at a time, validating
whatever was remembered that turn. A refusal on the last file left the earlier
ones written -- the repository describing a state no step had authorised.

THE ORDER, from the practice this is built on: check every file is still what
was read; validate every candidate through its own contract; check the
invariants that span files; stage everything; re-check; then publish -- and if
a publish fails after another landed, put back what landed.

WHAT THIS CANNOT PROMISE. POSIX has no transaction across paths: each replace
is atomic and the set is not. A process killed between two publishes leaves a
prefix, and nothing here can prevent that -- in a git working tree, the diff is
the journal that shows it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from otsafety_tooling.changeset import Change

pytestmark = pytest.mark.requirement("G.88")


class _Doc(BaseModel):
    """A stand-in contract: a file must name a version and nothing else."""

    model_config = ConfigDict(extra="forbid")
    version: int


def _files(tmp_path: Path) -> tuple[Path, Path]:
    first, second = tmp_path / "a.toml", tmp_path / "b.toml"
    first.write_text("version = 1\n", encoding="utf-8")
    second.write_text("version = 1\n", encoding="utf-8")
    return first, second


def _change(path: Path, content: str) -> Change:
    from otsafety_tooling.changeset import Change, digest, toml_contract

    return Change(
        path=path,
        expected=digest(path.read_text(encoding="utf-8")),
        content=content,
        validate=toml_contract(_Doc),
    )


def test_a_valid_change_publishes_every_file(tmp_path: Path) -> None:
    """THE CONTROL: a transaction that refused everything would pass the rest."""
    from otsafety_tooling.changeset import apply

    first, second = _files(tmp_path)
    apply([_change(first, "version = 2\n"), _change(second, "version = 3\n")])
    assert first.read_text(encoding="utf-8") == "version = 2\n"
    assert second.read_text(encoding="utf-8") == "version = 3\n"


def test_one_invalid_file_writes_nothing(tmp_path: Path) -> None:
    """THE RULE: the second file breaks its contract, so the first is not written."""
    from otsafety_tooling.changeset import ChangeRefusedError, apply

    first, second = _files(tmp_path)
    with pytest.raises(ChangeRefusedError):
        apply([_change(first, "version = 2\n"), _change(second, "version = 'two'\n")])
    assert first.read_text(encoding="utf-8") == "version = 1\n", (
        "a file was written before the refusal"
    )


def test_text_that_does_not_parse_writes_nothing(tmp_path: Path) -> None:
    """The case my script skipped for the workflow: not even syntactically valid."""
    from otsafety_tooling.changeset import ChangeRefusedError, apply

    first, second = _files(tmp_path)
    with pytest.raises(ChangeRefusedError):
        apply([_change(first, "version = 2\n"), _change(second, "version = = 3\n")])
    assert first.read_text(encoding="utf-8") == "version = 1\n"


def test_a_file_changed_since_it_was_read_writes_nothing(tmp_path: Path) -> None:
    """OPTIMISTIC CONCURRENCY: an edit computed from stale content is refused."""
    from otsafety_tooling.changeset import ChangeRefusedError, apply

    first, second = _files(tmp_path)
    changes = [_change(first, "version = 2\n"), _change(second, "version = 3\n")]
    second.write_text("version = 9\n", encoding="utf-8")

    with pytest.raises(ChangeRefusedError):
        apply(changes)
    assert first.read_text(encoding="utf-8") == "version = 1\n"
    assert second.read_text(encoding="utf-8") == "version = 9\n", (
        "someone else's edit was overwritten"
    )


def test_a_broken_invariant_across_files_writes_nothing(tmp_path: Path) -> None:
    """Each file valid alone, the pair not: checked over the candidates, before staging."""
    from collections.abc import Mapping

    from otsafety_tooling.changeset import ChangeRefusedError, apply

    first, second = _files(tmp_path)

    def versions_agree(world: Mapping[Path, str]) -> None:
        if len(set(world.values())) != 1:
            raise ValueError("the two files must name the same version")

    with pytest.raises(ChangeRefusedError):
        apply(
            [_change(first, "version = 2\n"), _change(second, "version = 3\n")],
            invariants=(versions_agree,),
        )
    assert first.read_text(encoding="utf-8") == "version = 1\n"


def test_a_failed_publish_puts_back_what_already_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FAILURE INJECTION, the one case validation cannot prevent: the disk
    refuses the second replace after the first has landed."""
    from otsafety_tooling import changeset
    from otsafety_tooling.changeset import ChangeRefusedError, apply

    first, second = _files(tmp_path)
    real = os.replace
    calls: list[str] = []

    def failing_second(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        calls.append(str(target))
        if len(calls) == 2:
            raise OSError("injected: the disk refused the second publish")
        real(source, target)

    monkeypatch.setattr(changeset, "_publish", failing_second)
    with pytest.raises(ChangeRefusedError):
        apply([_change(first, "version = 2\n"), _change(second, "version = 3\n")])

    assert first.read_text(encoding="utf-8") == "version = 1\n", (
        "the landed prefix was not put back"
    )
    assert second.read_text(encoding="utf-8") == "version = 1\n"


def test_no_staged_file_survives_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed change leaves the directory as it found it."""
    from otsafety_tooling import changeset
    from otsafety_tooling.changeset import ChangeRefusedError, apply

    first, second = _files(tmp_path)

    def refuse(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("injected")

    monkeypatch.setattr(changeset, "_publish", refuse)
    with pytest.raises(ChangeRefusedError):
        apply([_change(first, "version = 2\n"), _change(second, "version = 3\n")])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.toml", "b.toml"]


def test_a_retry_after_success_is_harmless(tmp_path: Path) -> None:
    """A file already at its desired content counts as done, not as stale."""
    from otsafety_tooling.changeset import apply

    first, second = _files(tmp_path)
    changes = [_change(first, "version = 2\n"), _change(second, "version = 3\n")]
    apply(changes)
    apply(changes)
    assert second.read_text(encoding="utf-8") == "version = 3\n"


def test_the_same_path_twice_is_refused(tmp_path: Path) -> None:
    """Two candidates for one file: whichever won would be an accident."""
    from otsafety_tooling.changeset import ChangeRefusedError, apply

    first, _ = _files(tmp_path)
    with pytest.raises(ChangeRefusedError):
        apply([_change(first, "version = 2\n"), _change(first, "version = 3\n")])


def test_a_new_file_must_not_already_exist(tmp_path: Path) -> None:
    """expected=None means absent: creating over an existing file is refused."""
    from otsafety_tooling.changeset import Change, ChangeRefusedError, apply, toml_contract

    first, _ = _files(tmp_path)
    with pytest.raises(ChangeRefusedError):
        apply(
            [
                Change(
                    path=first, expected=None, content="version = 2\n", validate=toml_contract(_Doc)
                )
            ]
        )
    assert first.read_text(encoding="utf-8") == "version = 1\n"


def test_yaml_that_does_not_parse_is_refused(tmp_path: Path) -> None:
    """THE WORKFLOW CASE. YAML's parser raises its own error type, not
    ValueError, so the YAML contract must translate it -- or a malformed
    workflow would escape as an unexplained crash instead of a refusal."""
    from otsafety_tooling.changeset import Change, ChangeRefusedError, apply, yaml_contract

    target = tmp_path / "flow.yml"
    target.write_text("version: 1\n", encoding="utf-8")
    from otsafety_tooling.changeset import digest

    with pytest.raises(ChangeRefusedError):
        apply(
            [
                Change(
                    path=target,
                    expected=digest("version: 1\n"),
                    content="version: [1\n",
                    validate=yaml_contract(_Doc),
                )
            ]
        )
    assert target.read_text(encoding="utf-8") == "version: 1\n"


def test_a_bug_in_a_validator_is_not_blamed_on_the_file(tmp_path: Path) -> None:
    """A validator's own defect propagates as itself. Catching every exception
    would report "this file breaks its contract" for an error in my code."""
    from otsafety_tooling.changeset import Change, apply, digest

    first, _ = _files(tmp_path)

    def broken(text: str) -> object:
        raise AttributeError("a defect in the validator, not in the file")

    with pytest.raises(AttributeError):
        apply(
            [
                Change(
                    path=first,
                    expected=digest("version = 1\n"),
                    content="version = 2\n",
                    validate=broken,
                )
            ]
        )
    assert first.read_text(encoding="utf-8") == "version = 1\n", (
        "a file was written before the defect"
    )
