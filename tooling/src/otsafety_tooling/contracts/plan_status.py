# tooling/src/otsafety_tooling/contracts/plan_status.py
"""plan-status/v1: the plan's status as observed, recorded as data.

STATUS IS OBSERVED, NEVER TYPED, AND NEVER WRITTEN BACK INTO THE PLAN. Each
observation is a record of its own, taken against a named ref. Counts and the
list of what to do next are properties computed from the steps, so no number is
ever stored where it could drift from what it counts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

State = Literal["done", "in_progress", "ready", "blocked"]


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StepStatus(_Strict):
    id: str
    state: State
    # For a blocked step: the dependencies not yet done, in plan order.
    blocked_by: tuple[str, ...] = ()


class PlanStatus(_Strict):
    contract: Literal["plan-status/v1"] = "plan-status/v1"
    # The ref the evidence was observed on.
    ref: str
    steps: tuple[StepStatus, ...]
    # thread id -> (done, total), in plan order.
    threads: dict[str, tuple[int, int]]

    @property
    def done(self) -> int:
        return sum(1 for s in self.steps if s.state == "done")

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def now(self) -> tuple[str, ...]:
        """Work in flight first, then work that could start: what to pick up next."""
        return tuple(s.id for s in self.steps if s.state == "in_progress") + tuple(
            s.id for s in self.steps if s.state == "ready"
        )
