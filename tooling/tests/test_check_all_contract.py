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
from types import ModuleType
from typing import Protocol

import pytest
from pydantic import JsonValue

from otsafety_tooling.contracts.outcome import EXIT_CODES, CommandOutcome
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


class _Runner(Protocol):
    """The subprocess seam, with the signature the stand-in actually has."""

    def __call__(
        self, command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]: ...


def _fake(results: dict[str, int], envelopes: dict[str, str] | None = None) -> _Runner:
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


def test_every_gate_is_bounded_in_time() -> None:
    """A GATE THAT CAN HANG IS NOT A GATE. subprocess.run had no timeout and
    capture_output=True, so when bun auto-installed from the registry the whole
    check sat for forty-one minutes printing nothing and returning no prompt. The
    bunfig stops that particular fetch; this stops the next one, whatever it is.
    """
    import ast

    source = (REPO_ROOT / "scripts" / "check_all.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "run":
            continue
        assert any(keyword.arg == "timeout" for keyword in node.keywords), (
            f"check_all.py:{node.lineno}: a gate with no timeout can hang the whole check"
        )


def test_a_gate_that_exceeds_its_bound_is_reported_not_raised(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A timeout that escapes as an exception loses every other gate's verdict,
    which is the failure this aggregate was written to prevent."""
    module = _module()

    def hangs(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[-1] == "lint":
            raise subprocess.TimeoutExpired(command, module.BOUND, output="partial")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", hangs)
    code = module.main(["--fast"])
    envelope = _envelope(capsys.readouterr().out)

    assert code == EXIT_CODES["refused"]
    assert envelope.code == "gates_failed"
    reported = {gate["name"]: gate["passed"] for gate in _gates(envelope)}
    assert reported["lint"] is False, "the gate that hung is the one reported failing"
    assert reported["types"] is True, "the others keep their verdicts"


def test_a_composed_task_reports_its_own_verdict_not_its_first_step() -> None:
    """THE LAST ENVELOPE IS THE TASK'S OWN.

    pdf:render collects the sheet's facts before rendering, so its output carries
    the collector's envelope and then its own. Reading the FIRST match reported
    facts_collected where the gate had rendered a sheet -- the wrong step's
    verdict, and it would have reported success for a step that had not run yet.

    2026 convention for a stream of envelopes is a terminal line: zero or more
    records followed by exactly one summary. The task's own result is what it
    ends with.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_all", REPO_ROOT / "scripts" / "check_all.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    composed = (
        '{"contract": "command-outcome/v1", "command": "sheet:facts", '
        '"outcome": "success", "code": "facts_collected"}\n'
        "WROTE_PDF something\n"
        '{"contract": "command-outcome/v1", "command": "pdf:render", '
        '"outcome": "success", "code": "sheet_rendered"}\n'
    )
    assert module.inner_outcome(composed) == {
        "outcome": "success",
        "code": "sheet_rendered",
    }
