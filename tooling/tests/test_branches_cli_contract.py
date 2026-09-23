# tooling/tests/test_branches_cli_contract.py
"""The branch report speaks in an envelope, not four printed lines (G.42).

WHY THIS EXISTS. run_report already builds branch-report/v1 -- a typed report with
a verdict, its facts and its findings -- writes it to the evidence root, and then
prints a flattened summary to stdout. A caller reading stdout got prose about data
that existed as a model one line earlier. stdout now carries one
command-outcome/v1 envelope naming the verdict, the counts and the report it
wrote; the findings stay in the report, which the envelope points at.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from otsafety_tooling.contracts.outcome import CommandOutcome
from otsafety_tooling.git.branches import run_report
from otsafety_tooling.git.env import git


def _envelope(out: str) -> CommandOutcome:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, f"stdout must carry exactly one envelope, got: {out!r}"
    return CommandOutcome.model_validate_json(lines[0])


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    assert git("init", "-q", "-b", "develop", cwd=root).returncode == 0
    for name, value in (("user.email", "t@e.st"), ("user.name", "T")):
        assert git("config", name, value, cwd=root).returncode == 0
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    assert git("add", "seed.txt", cwd=root).returncode == 0
    assert git("commit", "-qm", "seed", cwd=root).returncode == 0
    return root


def test_a_report_that_cannot_read_the_branches_is_a_failure(
    repository: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No origin/develop here, so the facts cannot be gathered: unknown, never pass."""
    code = run_report(repository, tmp_path / "artifacts", fetch=False)
    envelope = _envelope(capsys.readouterr().out)
    assert code == 1, "an unreadable repository is a failure, not a refusal"
    assert envelope.command == "branch:report" and envelope.outcome == "failed"
    assert envelope.code == "branches_unknown"
    assert envelope.data["verdict"] == "unknown"
    assert Path(str(envelope.data["report"])).is_file(), "the envelope names the report it wrote"
