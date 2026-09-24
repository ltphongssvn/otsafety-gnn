# tooling/tests/test_check_all_contract.py
"""The aggregate gate speaks in an envelope, and carries each gate's own (G.42).

WHY THIS EXISTS. check_all ran every gate and printed a PASS/FAIL table: a caller
learned which gate failed by matching "FAIL  name". It captures each gate's stdout
already, and each gate now emits a command-outcome/v1 envelope there, so the
aggregate carries those verdicts as data instead of discarding them into a text
blob it prints only on failure. The table stays on stderr, where a person reads
it as the run proceeds.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable
from types import ModuleType

import pytest
from pydantic import JsonValue

from otsafety_tooling.contracts.outcome import CommandOutcome
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.42")


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_all", REPO_ROOT / "scripts" / "check_all.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _gates(envelope: CommandOutcome) -> list[dict[str, JsonValue]]:
    """The gates the aggregate reported, narrowed from the payload's JSON."""
    gates = envelope.data["gates"]
    assert isinstance(gates, list)
    return [gate for gate in gates if isinstance(gate, dict)]


def _envelope(out: str) -> CommandOutcome:
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1, f"stdout must carry exactly one envelope, got: {out!r}"
    return CommandOutcome.model_validate_json(lines[0])


def _fake(
    results: dict[str, int], envelopes: dict[str, str] | None = None
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        name = command[-1]
        return subprocess.CompletedProcess(
            args=command,
            returncode=results.get(name, 0),
            stdout=(envelopes or {}).get(name, ""),
            stderr="",
        )

    return run


def test_every_gate_passing_is_one_envelope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    monkeypatch.setattr(module.subprocess, "run", _fake({}))
    code = module.main(["--fast"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 0 and envelope.command == "check"
    assert envelope.code == "gates_passed"
    assert [gate["name"] for gate in _gates(envelope)] == [
        "toolchain:verify",
        "lint",
        "types",
        "test",
    ]
    assert all(gate["passed"] for gate in _gates(envelope))


def test_a_failing_gate_is_refused_and_named(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    monkeypatch.setattr(module.subprocess, "run", _fake({"types": 1}))
    code = module.main(["--fast"])
    envelope = _envelope(capsys.readouterr().out)
    assert code == 2, "a failing gate is a refusal, not a crash"
    assert envelope.code == "gates_failed"
    assert envelope.data["failed"] == ["types"]


def test_a_gates_own_envelope_is_carried(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate's verdict is data it already produced; the aggregate keeps it."""
    module = _module()
    inner = (
        '{"contract":"command-outcome/v1","command":"toolchain:verify","outcome":"success",'
        '"code":"tools_pinned","message":"every task resolves the pinned 7 tools","data":{}}'
    )
    monkeypatch.setattr(module.subprocess, "run", _fake({}, {"toolchain:verify": inner}))
    module.main(["--fast"])
    envelope = _envelope(capsys.readouterr().out)
    first = _gates(envelope)[0]
    assert first["outcome"] == {"code": "tools_pinned", "outcome": "success"}
