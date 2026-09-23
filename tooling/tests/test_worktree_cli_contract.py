# tooling/tests/test_worktree_cli_contract.py
"""The worktree command speaks in envelopes, not prose (G.42).

OUTSIDE-IN. These drive main() at the command boundary, the way a caller or an
agent invokes it: stdout carries exactly one command-outcome/v1 envelope and
nothing else, stderr carries the human progress, and the exit code follows the
outcome -- 0 for success, 2 for a refusal that names a machine code. A caller
parses stdout unconditionally; reading it with grep is presentation filtering,
not evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from otsafety_tooling.contracts.outcome import CommandOutcome
from otsafety_tooling.git import worktree
from otsafety_tooling.git.env import git
from otsafety_tooling.git.worktree_domain import WorktreeRef


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    assert git("init", "-q", "-b", "develop", cwd=root).returncode == 0
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    assert git("add", "seed.txt", cwd=root).returncode == 0
    assert (
        git(
            "-c", "user.email=t@e.st", "-c", "user.name=T", "commit", "-qm", "seed", cwd=root
        ).returncode
        == 0
    )
    monkeypatch.setattr(worktree, "REPO_ROOT", root)
    return root


def _envelope(out: str) -> CommandOutcome:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, f"stdout must carry exactly one envelope, got: {out!r}"
    return CommandOutcome.model_validate_json(lines[0])


def test_listing_emits_one_envelope_carrying_the_worktrees(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = worktree.main(["list"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 0
    assert envelope.command == "worktree:list" and envelope.outcome == "success"
    assert envelope.data["worktrees"], "the listing must carry the worktrees as data"


def test_a_bad_slug_is_a_refusal_with_a_machine_code(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = worktree.main(["add", "Not A Slug"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2, "a refusal exits 2, never 1: it is not a crash"
    assert envelope.outcome == "refused" and envelope.code == "slug_invalid"


def test_removing_a_worktree_that_does_not_exist_is_refused(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = worktree.main(["remove", "absent"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2 and envelope.code == "worktree_missing"
    assert envelope.command == "worktree:remove"


def test_the_domain_refuses_a_slug_that_is_not_kebab_case(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="slug"):
        WorktreeRef(slug="Not A Slug", main=tmp_path)


def test_a_reference_derives_its_branch_and_path_from_its_slug(tmp_path: Path) -> None:
    ref = WorktreeRef(slug="requirement-identity", main=tmp_path / "otsafety-gnn")
    assert ref.branch == "feature/requirement-identity"
    assert ref.path == tmp_path / "otsafety-gnn-requirement-identity"
