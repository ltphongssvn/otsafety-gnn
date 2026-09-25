# tooling/src/otsafety_tooling/contracts/plan_report.py
"""plan-report/v1: every step in every phase, collected before it is printed.

THE RENDERER CANNOT COLLECT. Its image carries Playwright and pypdf and neither
git nor this package, so the report is gathered where the tooling is, validated,
and handed over as a document -- the same separation sheet-facts/v1 makes.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict


class StepRow(BaseModel):
    """One step, as a reader needs it: what it is, where it stands, what blocks it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    thread: str
    state: Literal["DONE", "READY", "BLOCK"]
    after: tuple[str, ...]
    evidence: tuple[str, ...]
    unmet: tuple[str, ...]


class PhaseRows(BaseModel):
    """One phase and its steps, in plan order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    done: int
    total: int
    steps: tuple[StepRow, ...]


class PlanReport(BaseModel):
    """The whole plan, as the sheet prints it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CONTRACT_ID: ClassVar[str] = "plan-report/v1"

    contract: Literal["plan-report/v1"] = "plan-report/v1"
    steps: int
    steps_done: int
    ready: int
    blocked: int
    ids: int
    requirements: int
    orphans: int
    phases: tuple[PhaseRows, ...]
