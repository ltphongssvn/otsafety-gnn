# tooling/tests/test_commit_cli_contract.py
"""The commit command speaks in envelopes, and its subject is a type (G.42).

OUTSIDE-IN, RED FIRST. These drive commit.main() at the boundary: stdout carries
exactly one command-outcome/v1 envelope, stderr carries the progress, a refusal
exits 2 with a machine code, and a success carries the commit it created. The
subject's invariants -- one line, not empty, at most a hundred characters -- are a
value object rather than three checks inside a command.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.outcome import CommandOutcome
from otsafety_tooling.git import commit as commit_module
from otsafety_tooling.git.commit_domain import CommitSubject
from otsafety_tooling.git.env import git


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    assert git("init", "-q", "-b", "develop", cwd=root).returncode == 0
    for name, value in (("user.email", "t@e.st"), ("user.name", "T")):
        assert git("config", name, value, cwd=root).returncode == 0
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    assert git("add", "seed.txt", cwd=root).returncode == 0
    assert git("commit", "-qm", "seed", cwd=root).returncode == 0
    monkeypatch.setattr(commit_module, "REPO_ROOT", root)
    monkeypatch.chdir(root)
    return root


def _envelope(out: str) -> CommandOutcome:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, f"stdout must carry exactly one envelope, got: {out!r}"
    return CommandOutcome.model_validate_json(lines[0])


def test_a_subject_is_one_line_and_bounded() -> None:
    assert CommitSubject(text="feat(x): a change").text == "feat(x): a change"
    for bad in ("", "two\nlines", "x" * 101):
        with pytest.raises(ValidationError):
            CommitSubject(text=bad)


def test_committing_nothing_is_refused_with_a_machine_code(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = commit_module.main(["-m", "feat(x): nothing staged", "--", "seed.txt"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2 and envelope.outcome == "refused"
    assert envelope.code == "no_changes" and envelope.command == "commit"


def test_a_commit_reports_the_commit_it_created(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "seed.txt").write_text("changed\n", encoding="utf-8")
    code = commit_module.main(["-m", "feat(x): change the seed", "--", "seed.txt"])
    envelope = _envelope(capsys.readouterr().out)
    head = git("rev-parse", "HEAD", cwd=repository).stdout.strip()
    assert code == 0 and envelope.code == "committed"
    assert envelope.data["commit"] == head
    assert envelope.data["paths"] == ["seed.txt"]


def test_a_subject_with_two_lines_is_refused_at_the_boundary(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = commit_module.main(["-m", "feat(x): one\ntwo", "--", "seed.txt"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2 and envelope.code == "subject_invalid"
