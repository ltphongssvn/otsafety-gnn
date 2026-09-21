# tooling/src/otsafety_tooling/contracts/plan.py
"""project-plan/v1: the plan as intent, with the evidence that proves each step.

INTENT ONLY. The plan declares threads, phases, steps, explicit dependencies and,
for every step, the evidence that proves it done. It never records status: every
status written into a plan by hand drifted from the work it described. extra is
forbidden, so a `status` field on a step is refused rather than trusted. Status
is derived by observing the evidence -- a merged pull request, a release tag, a
file or task that exists -- and is never written back here.

SEMANTIC RULES a schema cannot state: ids unique across steps and decisions,
every reference resolvable, dependencies acyclic and explicit -- phase order is
not a dependency graph. A decision not to do something is data too, with its
reason, so nothing is ever silently left open.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

ID = r"^[0-9A-Z]+\.[0-9A-Z]+$"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Thread(_Strict):
    id: str = Field(pattern=r"^[A-Z]$")
    title: str = Field(min_length=1)


class Phase(_Strict):
    id: str = Field(pattern=r"^[0-9]+[A-Z]?$")
    title: str = Field(min_length=1)


class Loop(_Strict):
    """One of the five loops: an as-code side that declares, an as-data side that records.

    A loop with only one side is the classic failure -- policy with no verdicts,
    contracts with no evidence -- so both sides are required.
    """

    id: Literal["declare", "constrain", "produce", "promise", "instrument"]
    code: str = Field(min_length=1)
    data: str = Field(min_length=1)


class Serves(_Strict):
    """Which loop a step advances, and on which side."""

    loop: str
    side: Literal["code", "data"]


class PrEvidence(_Strict):
    """Done when this pull request is merged."""

    kind: Literal["pr"]
    number: PositiveInt


class ReleaseEvidence(_Strict):
    """Done when this release tag exists."""

    kind: Literal["release"]
    tag: str = Field(pattern=r"^v[0-9]+\.[0-9]+\.[0-9]+$")


class PathEvidence(_Strict):
    """Done when this file exists on the integration branch."""

    kind: Literal["path"]
    path: str = Field(min_length=1)


class TaskEvidence(_Strict):
    """Done when mise.toml declares this task."""

    kind: Literal["task"]
    name: str = Field(min_length=1)


Evidence = Annotated[
    PrEvidence | ReleaseEvidence | PathEvidence | TaskEvidence, Field(discriminator="kind")
]


class Step(_Strict):
    id: str = Field(pattern=ID)
    title: str = Field(min_length=1)
    thread: str
    phase: str
    depends_on: tuple[str, ...] = ()
    # The branch that carries the work, so an open branch shows a step in progress.
    branch: str | None = Field(default=None, pattern=r"^(feature|release|hotfix)/[a-z0-9-]+$")
    # Where the step came from, when another project's plan supplied it.
    source: str | None = None
    # The loop and side it advances; a step that serves no loop is not in the plan.
    serves: tuple[Serves, ...] = Field(min_length=1)
    # Every item must hold for the step to be done.
    done_when: tuple[Evidence, ...] = Field(min_length=1)


class Decision(_Strict):
    """Something this plan deliberately does not do, or defers, and why."""

    id: str = Field(pattern=ID)
    title: str = Field(min_length=1)
    state: Literal["declined", "deferred", "superseded"]
    reason: str = Field(min_length=1)
    source: str | None = None


class ProjectPlan(_Strict):
    contract: Literal["project-plan/v1"]
    threads: tuple[Thread, ...] = Field(min_length=1)
    phases: tuple[Phase, ...] = Field(min_length=1)
    loops: tuple[Loop, ...] = Field(min_length=1)
    steps: tuple[Step, ...] = Field(min_length=1)
    decisions: tuple[Decision, ...] = ()

    @model_validator(mode="after")
    def _references_resolve_and_nothing_cycles(self) -> Self:
        for kind, ids in (
            ("thread", [t.id for t in self.threads]),
            ("phase", [p.id for p in self.phases]),
            ("loop", [loop.id for loop in self.loops]),
            ("step or decision", [s.id for s in self.steps] + [d.id for d in self.decisions]),
        ):
            seen: set[str] = set()
            for item in ids:
                if item in seen:
                    raise ValueError(f"duplicate {kind} id {item}")
                seen.add(item)

        loops = {loop.id for loop in self.loops}
        threads = {t.id for t in self.threads}
        phases = {p.id for p in self.phases}
        steps = {s.id: s for s in self.steps}
        for step in self.steps:
            if step.thread not in threads:
                raise ValueError(f"{step.id} names unknown thread {step.thread}")
            if step.phase not in phases:
                raise ValueError(f"{step.id} names unknown phase {step.phase}")
            for serving in step.serves:
                if serving.loop not in loops:
                    raise ValueError(f"{step.id} serves undeclared loop {serving.loop}")
            for dependency in step.depends_on:
                if dependency not in steps:
                    raise ValueError(f"{step.id} depends on unknown step {dependency}")

        visiting: set[str] = set()
        finished: set[str] = set()

        def visit(step_id: str, trail: tuple[str, ...]) -> None:
            if step_id in finished:
                return
            if step_id in visiting:
                raise ValueError(f"dependency cycle: {' -> '.join((*trail, step_id))}")
            visiting.add(step_id)
            for dependency in steps[step_id].depends_on:
                visit(dependency, (*trail, step_id))
            visiting.discard(step_id)
            finished.add(step_id)

        for step_id in steps:
            visit(step_id, ())
        return self
