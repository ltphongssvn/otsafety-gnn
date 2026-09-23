# tooling/tests/test_command_outcome.py
"""A command's stdout is its envelope, and its payload is a model (G.42).

WHY A MODEL AND NOT KEYWORDS. The first emitter took **data, so nothing checked
which keys a command emitted: a misspelt field would have shipped. 2026 practice
is a model per contract -- "create request, stored record, internal event" -- so
the payload's fields are checked where they are written, and a list stays a list
because the model says so rather than the emitter coercing it.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from otsafety_tooling.cli import result
from otsafety_tooling.contracts.outcome import CommandOutcome


class _Payload(BaseModel):
    """What a command carries: named fields, checked where they are written."""

    requirements: int
    paths: list[str] = []


def test_the_envelope_is_the_whole_of_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    code = result(
        "plan:matrix",
        "success",
        "matrix_written",
        "186 requirements",
        _Payload(requirements=186, paths=["a.py"]),
    )
    captured = capsys.readouterr()
    assert code == 0 and captured.err == ""
    assert captured.out.endswith("\n"), "a line reader must never drop the last record"
    envelope = CommandOutcome.model_validate_json(captured.out)
    assert envelope.command == "plan:matrix"
    assert envelope.data["requirements"] == 186
    assert envelope.data["paths"] == ["a.py"], "a list survives as a list"


def test_a_refusal_exits_two_and_carries_a_machine_code(capsys: pytest.CaptureFixture[str]) -> None:
    code = result("policy:trailers", "refused", "trailer_missing_or_unproved", "no trailer")
    assert code == 2
    envelope = CommandOutcome.model_validate_json(capsys.readouterr().out)
    assert envelope.code == "trailer_missing_or_unproved" and envelope.data == {}


def test_a_code_must_be_a_machine_token_not_prose() -> None:
    with pytest.raises(ValidationError):
        CommandOutcome(command="x", outcome="failed", code="It broke!", message="x")
