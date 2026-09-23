# tooling/tests/test_pr_cli_contract.py
"""The pull-request command speaks in envelopes, not prose (G.42).

WHY THIS EXISTS. pr merges every change in this repository, and reading its
result meant parsing sixteen printed lines: the pull request it opened, whether
each check passed, whether the merge happened. stdout now carries exactly one
command-outcome/v1 envelope naming the pull request, the checks and the merge
commit; the running commentary stays on stderr, where a person reads it while it
waits. A refusal -- a protected branch, a missing check -- exits 2 with a machine
code rather than a bare SystemExit.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

import pytest

from otsafety_tooling.contracts.outcome import CommandOutcome
from otsafety_tooling.git import pr as pr_module

pytestmark = pytest.mark.requirement("G.42")


def _envelope(out: str) -> CommandOutcome:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, f"stdout must carry exactly one envelope, got: {out!r}"
    return CommandOutcome.model_validate_json(lines[0])


def _git(result: str = "", code: int = 0) -> Callable[..., subprocess.CompletedProcess[str]]:
    """A stand-in for git(): the seam every remote call in pr.py goes through."""

    def run(*args: str, **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(args), returncode=code, stdout=result, stderr=""
        )

    return run


def test_a_protected_branch_is_refused_with_a_machine_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pr_module, "git", _git("develop\n"))
    code = pr_module.main([])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2, "a refusal exits 2, never 1"
    assert envelope.command == "pr" and envelope.outcome == "refused"
    assert envelope.code == "protected_branch"
    assert envelope.data["branch"] == "develop"


def test_an_unknown_verb_is_refused_with_usage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = pr_module.main(["nonsense"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2 and envelope.code == "usage"


def test_nothing_to_propose_is_reported_as_an_outcome(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A branch with no commits ahead is not a failure: it is a stated outcome."""
    monkeypatch.setattr(pr_module, "git", _git("feature/x\n"))
    monkeypatch.setattr(pr_module, "commits_ahead", lambda _root: 0)
    monkeypatch.setattr(pr_module, "merged_pr_number", lambda _branch: 41)
    code = pr_module.main([])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 0 and envelope.outcome == "success"
    assert envelope.data["pull_request"] == 41
