# tooling/src/otsafety_tooling/cli.py
"""How a command speaks: the payload on stdout, everything else on stderr.

THE ONE WAY. emit() writes the outcome envelope to stdout, newline-terminated, and
returns the exit code the outcome carries. note() writes human text to stderr. No
command writes prose to stdout, so a caller parses stdout unconditionally rather
than filtering it with grep.
"""

from __future__ import annotations

import sys

from pydantic import BaseModel

from otsafety_tooling.contracts.outcome import CommandOutcome, Verdict


class CommandRefused(SystemExit):
    """A refusal: the input or the repository state was wrong, never a crash.

    Still a SystemExit, so every existing caller and test keeps working; main()
    catches it and emits a refused envelope carrying its machine code and exit 2.
    """

    def __init__(self, code: str, message: str, payload: BaseModel | None = None) -> None:
        super().__init__(message)
        # NOT `code`: SystemExit already owns that name, typed str | int | None.
        self.machine_code = code
        self.message = message
        self.payload = payload


def refusal(command: str, error: CommandRefused) -> int:
    """Emit a refusal as the command's outcome."""
    return result(command, "refused", error.machine_code, error.message, error.payload)


def note(text: str) -> None:
    """Human-facing progress or explanation: stderr, never the payload channel."""
    sys.stderr.write(f"{text}\n")


def emit(outcome: CommandOutcome) -> int:
    """Write the envelope to stdout and return the exit code it carries."""
    sys.stdout.write(outcome.model_dump_json() + "\n")
    return outcome.exit_code


def result(
    command: str,
    outcome: Verdict,
    code: str,
    message: str,
    payload: BaseModel | None = None,
) -> int:
    """Build the envelope and emit it. The payload is a model, never loose keywords.

    **kwargs cannot be checked: a misspelt field would ship. A model declares what
    a command carries, so its fields are checked where they are written, and a
    list stays a list because the model says so.
    """
    envelope = CommandOutcome(
        command=command,
        outcome=outcome,
        code=code,
        message=message,
        data=payload.model_dump(mode="json") if payload is not None else {},
    )
    return emit(envelope)
