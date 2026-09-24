# tooling/src/otsafety_tooling/contracts/traceability.py
"""A requirement's identity, as data: the ledger of IDs, and the matrix built from one.

WHY THIS EXISTS. G.38 is not "the setup bug": it is an ID that the constraint, the
observation that produced it, the evidence file and the behavioural proof all hang
from. 2026 practice for requirements traceability is blunt about what breaks that:
IDs must be assigned once and never reused, links must be made when the work is
made rather than reconstructed later, and the matrix must be generated and
drift-gated rather than maintained by hand.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IssuedId(_Strict):
    """One identifier, issued once. Retired ids stay here so none is ever reused."""

    id: str = Field(pattern=r"^[A-Z0-9]+\.[A-Za-z0-9]+$")
    first_title: str = Field(min_length=1)
    retired: bool = False


class IdLedger(_Strict):
    """context/plan-ids.yaml: append-only. An id leaves this file only by being retired."""

    CONTRACT_ID: ClassVar[str] = "id-ledger/v1"

    contract: Literal["id-ledger/v1"] = "id-ledger/v1"
    issued: tuple[IssuedId, ...] = Field(min_length=1)


class Requirement(_Strict):
    """One row of the matrix: everything that hangs off one id."""

    id: str
    title: str
    thread: str
    phase: str
    kind: Literal["step", "decision"]
    evidence: tuple[str, ...]
    justified_by: tuple[str, ...]
    named_in: tuple[str, ...]
    referenced_by: tuple[str, ...]
    claimed_by: tuple[str, ...]
    # EVIDENCE THE BUILDER COULD NOT CONFIRM. A link is not verified until the
    # evidence itself is: a test file by claiming the id, any other file by
    # containing it -- inspection, as a requirement verified without a test is.
    unconfirmed: tuple[str, ...] = ()


class RequirementMatrix(_Strict):
    """Generated from the plan, its trace, the tree and the commits: never written by hand."""

    CONTRACT_ID: ClassVar[str] = "requirement-matrix/v1"

    contract: Literal["requirement-matrix/v1"] = "requirement-matrix/v1"
    ref: str = Field(min_length=1)
    requirements: tuple[Requirement, ...] = Field(min_length=1)
    orphan_candidates: tuple[str, ...]
