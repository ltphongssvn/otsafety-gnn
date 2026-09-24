# tooling/tests/test_sync_cli_contract.py
"""The sync command speaks in envelopes, not prose (G.42).

WHY THIS EXISTS. sync advances every protected branch, leaves a finished branch
and removes what is safe, and it reported all of that as twelve printed lines: a
caller wanting to know what was removed had to parse them. stdout now carries one
command-outcome/v1 envelope naming what advanced, what was removed and what was
kept with its reason; the same lines stay on stderr for a person to read. A
refusal -- an unknown branch, a bad verb -- exits 2 with a machine code.
"""

from __future__ import annotations

import subprocess

import pytest

from otsafety_tooling.contracts.outcome import CommandOutcome
from otsafety_tooling.git import sync as sync_module

pytestmark = pytest.mark.requirement("G.42")


def _envelope(out: str) -> CommandOutcome:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, f"stdout must carry exactly one envelope, got: {out!r}"
    return CommandOutcome.model_validate_json(lines[0])


def test_an_unknown_verb_is_refused_with_a_machine_code(capsys: pytest.CaptureFixture[str]) -> None:
    code = sync_module.main(["nonsense"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2, "a refusal exits 2, never 1"
    assert envelope.command == "sync" and envelope.code == "usage"


def test_switching_without_a_branch_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    code = sync_module.main(["switch"])
    envelope = _envelope(capsys.readouterr().out)
    # main checks its own usage before switch_command is reached.
    assert code == 2 and envelope.code == "usage"


def test_switching_to_an_unknown_branch_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake(*args: str, **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(args), returncode=0, stdout="develop\n", stderr=""
        )

    monkeypatch.setattr(sync_module, "git", fake)
    code = sync_module.main(["switch", "no-such-branch"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2 and envelope.code == "unknown_branch"
    assert "no-such-branch" in envelope.message
