# tooling/src/otsafety_tooling/contracts/policy_inputs.py
"""policy-inputs/v1: every file the policy reads, declared once.

THE SET LIVED IN THREE PLACES -- the policy task's command line, the probe's own
list, and the required set in the Rego. Adding one input meant three edits, and
missing one failed late. 2026 practice for duplicated policy configuration calls
that a divergence problem and answers it with one versioned artifact every
consumer reads; the parity between them is itself checked.

The manifest is also one of the inputs, so the Rego derives what it requires from
the manifest rather than repeating it.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class PolicyInput(BaseModel):
    """One file the policy reads, and how it comes to exist."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    why: str
    # GENERATED INPUTS ARE WRITTEN BEFORE EACH RUN, into the evidence root, by the
    # command named here. A committed input is read where it lies.
    generated: str | None = None


class PolicyInputs(BaseModel):
    """The whole input set: the source the task, the probe and the Rego read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CONTRACT_ID: ClassVar[str] = "policy-inputs/v1"

    contract: str = Field(default="policy-inputs/v1")
    inputs: tuple[PolicyInput, ...]
