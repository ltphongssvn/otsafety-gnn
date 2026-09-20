# tooling/src/otsafety_tooling/contracts/run_record.py
"""run-record/v1: one task execution, recorded as data.

SHAPED BY THE OPEN TELEMETRY CONVENTIONS for an operation with a duration and a
boundary: a STABLE name (`branches`, `repo:check`) with no dynamic part, flat
fields, identifiers carried as data, and an error type present only on failure.

WHAT A RECORD MUST NOT CONTRADICT
    success        exactly when the exit code is zero
    error_type     present exactly when the outcome is a failure
    ended_at       never before started_at, and duration_ms agrees with both
    output         a file name, its size, and the digest of the FULL output,
                   so a truncated record is still verifiable

PRIVACY. The machine is an opaque identifier, never a hostname: this laptop's
name contains a person's name, and records are shared evidence. There is no
working-directory field for the same reason.

NAMING THE FILES. The producer names each record and its output after the run
(<timestamp>-<task>-<id>), so no two runs can overwrite one another -- the
defect that lost a pull request log earlier in this project.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    NonNegativeInt,
    StrictBool,
    model_validator,
)

CONTRACT: Final = "run-record/v1"

Outcome = Literal["success", "failure"]

TASK_PATTERN = r"^[a-z][a-z0-9]*(?:[:-][a-z0-9]+)*$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
MACHINE_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# The two timestamps are recorded independently of the measured duration, so
# rounding may differ by a millisecond; more than that is a contradiction.
DURATION_TOLERANCE_MS: Final = 1


class RunRecord(BaseModel, frozen=True, extra="forbid"):
    """What one task run did: its identity, timing, outcome and output."""

    contract: Literal["run-record/v1"] = CONTRACT
    id: str = Field(min_length=6, max_length=32, pattern=r"^[0-9a-f]+$")
    task: str = Field(pattern=TASK_PATTERN)
    arguments: tuple[str, ...] = ()

    started_at: AwareDatetime
    ended_at: AwareDatetime
    duration_ms: NonNegativeInt = Field(strict=True)

    exit_code: int = Field(strict=True)
    outcome: Outcome
    error_type: str | None = Field(default=None, min_length=1)

    repository: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    commit: str = Field(pattern=COMMIT_PATTERN)
    machine: str = Field(pattern=MACHINE_PATTERN)

    output_file: str = Field(min_length=1)
    output_bytes: NonNegativeInt = Field(strict=True)
    output_sha256: str = Field(pattern=SHA256_PATTERN)
    truncated: StrictBool = False

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        succeeded = self.exit_code == 0
        if succeeded != (self.outcome == "success"):
            raise ValueError(f"outcome is {self.outcome!r} but the exit code is {self.exit_code}")
        if self.outcome == "failure" and self.error_type is None:
            raise ValueError("a failure must name its error_type")
        if self.outcome == "success" and self.error_type is not None:
            raise ValueError("a success carries no error_type")

        if self.ended_at < self.started_at:
            raise ValueError("ended_at is before started_at")
        measured = (self.ended_at - self.started_at).total_seconds() * 1000
        if abs(measured - self.duration_ms) > DURATION_TOLERANCE_MS:
            raise ValueError(
                f"duration_ms is {self.duration_ms} but the timestamps span {measured:.0f}ms"
            )

        if not self.output_file:
            raise ValueError("output_file names where the run's output was kept")
        return self
