# tooling/src/otsafety_tooling/contracts/experiment_run.py
"""experiment-run/v1: one experiment, recorded so it can be reproduced.

WHY THE REPRODUCIBILITY FACTS ARE REQUIRED, NOT OPTIONAL. Practitioners
comparing MLflow and Weights & Biases put it plainly: both log what you tell
them to log, so inconsistent instrumentation is what actually destroys
reproducibility. Here a run cannot be recorded without the commit and whether
the tree was clean, the dataset and its digest, the seeds and whether the run
is deterministic, the Python version and the exact package versions.

VENDOR-FREE ON PURPOSE. Nothing here names a tracker. MLflow and W&B are
adapters that translate this record, so training code never imports either and
a tracker can be added or dropped without touching an experiment.

A DIRTY TREE IS DECLARED, NOT REFUSED. Refusing would push people to record
nothing, which is worse; is_reproducible simply reads false, and it is derived
rather than stored, so it cannot disagree with the facts.

METRICS ARE REAL NUMBERS. NaN and infinity are rejected: a metric that is not a
number is a bug in the run, not a result to compare.

ARTIFACTS ARE RECORDED BY DIGEST. A path names one machine; a digest names the
bytes anywhere, which is what another machine needs to verify it has the same
model.

PRIVACY. The machine is an opaque identifier, and no field carries a path, a
username or a hostname: experiment records are shared evidence.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    NonNegativeInt,
    StrictBool,
    StrictInt,
    model_validator,
)

# A metric is a real number: NaN and infinity are rejected at the field, since a
# metric that is not a number is a bug in the run rather than a result.
MetricValue = Annotated[float, Field(allow_inf_nan=False)]

CONTRACT: Final = "experiment-run/v1"

Status = Literal["completed", "failed"]

NAME_PATTERN = r"^[a-z][a-z0-9]*(?:[:-][a-z0-9]+)*$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
MACHINE_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

Digest = Annotated[str, Field(pattern=SHA256_PATTERN)]
VERSION_PATTERN = r"^\d+\.\d+"

# The timestamps are recorded independently of the measured duration, so
# rounding may differ by a millisecond; more than that is a contradiction.
DURATION_TOLERANCE_MS: Final = 1


class ExperimentRun(BaseModel, frozen=True, extra="forbid"):
    """One experiment: what was run, on what, with what, and what came out."""

    contract: Literal["experiment-run/v1"] = CONTRACT
    id: str = Field(min_length=6, max_length=32, pattern=r"^[0-9a-f]+$")
    experiment: str = Field(pattern=NAME_PATTERN)

    started_at: AwareDatetime
    ended_at: AwareDatetime
    duration_ms: NonNegativeInt = Field(strict=True)
    status: Status
    error_type: str | None = Field(default=None, min_length=1)

    # Code
    commit: str = Field(pattern=COMMIT_PATTERN)
    working_tree_clean: StrictBool

    # Data
    dataset: str = Field(min_length=1)
    dataset_digest: str = Field(pattern=SHA256_PATTERN)

    # Determinism
    seeds: dict[str, StrictInt] = Field(min_length=1)
    deterministic: StrictBool

    # Environment
    python_version: str = Field(pattern=VERSION_PATTERN)
    packages: dict[str, str] = Field(min_length=1)

    # Results
    params: dict[str, float | int | bool | str] = Field(default_factory=dict)
    metrics: dict[str, MetricValue] = Field(default_factory=dict)
    # BY DIGEST, NOT BY PATH: a path names one machine, a digest names the bytes.
    artifacts: dict[str, Digest] = Field(default_factory=dict)

    machine: str = Field(pattern=MACHINE_PATTERN)

    @property
    def is_reproducible(self) -> bool:
        """Another machine could expect the same numbers from these facts."""
        return self.working_tree_clean and self.deterministic

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.status == "failed" and self.error_type is None:
            raise ValueError("a failed run must name its error_type")
        if self.status == "completed" and self.error_type is not None:
            raise ValueError("a completed run carries no error_type")

        if self.ended_at < self.started_at:
            raise ValueError("ended_at is before started_at")
        measured = (self.ended_at - self.started_at).total_seconds() * 1000
        if abs(measured - self.duration_ms) > DURATION_TOLERANCE_MS:
            raise ValueError(
                f"duration_ms is {self.duration_ms} but the timestamps span {measured:.0f}ms"
            )
        return self
