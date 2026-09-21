# tooling/src/otsafety_tooling/contracts/plan_trace.py
"""plan-trace/v1: every source a plan item came from, and every candidate drawn from them.

WHY THIS EXISTS. The plan grew from 64 to 92 to 103 steps across verification
rounds because it was assembled from memory, and each round found what the last
missed. Completeness judged by recall is not completeness. Each candidate drawn
from a source either maps to plan items or is declared not a plan item, with a
reason -- never both, never neither.

BOTH DIRECTIONS. untraced() reports a candidate pointing at nothing in the plan,
which means the plan is missing something, and a plan item no candidate points
at, which means the plan holds something no source asked for.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from otsafety_tooling.contracts.plan import ProjectPlan


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TraceSource(_Strict):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9-]*$")
    title: str = Field(min_length=1)
    # Where the source can be found: a transcript, a commit, a file, a page.
    locator: str = Field(min_length=1)


class Candidate(_Strict):
    source: str = Field(min_length=1)
    # Where in the source: a line, a row, a sentence, a commit.
    ref: str = Field(min_length=1)
    text: str = Field(min_length=1)
    maps_to: tuple[str, ...] = ()
    not_a_plan_item: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _exactly_one_disposition(self) -> Self:
        if bool(self.maps_to) == (self.not_a_plan_item is not None):
            raise ValueError(
                f"{self.source} {self.ref}: needs exactly one of maps_to or not_a_plan_item"
            )
        return self


class PlanTrace(_Strict):
    contract: Literal["plan-trace/v1"]
    sources: tuple[TraceSource, ...] = Field(min_length=1)
    candidates: tuple[Candidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sources_resolve(self) -> Self:
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate source id")
        known = set(ids)
        for candidate in self.candidates:
            if candidate.source not in known:
                raise ValueError(f"{candidate.ref} names unknown source {candidate.source}")
        return self


def untraced(trace: PlanTrace, plan: ProjectPlan) -> list[str]:
    """Every gap between the trace and the plan, in both directions."""
    items = {s.id for s in plan.steps} | {d.id for d in plan.decisions}
    problems: list[str] = []
    targeted: set[str] = set()
    for candidate in trace.candidates:
        for target in candidate.maps_to:
            targeted.add(target)
            if target not in items:
                problems.append(
                    f"{candidate.source} {candidate.ref} maps to {target}, which is not in the plan"
                )
    problems += [f"{item} is traced to no source" for item in sorted(items - targeted)]
    return problems
