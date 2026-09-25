# tooling/src/otsafety_tooling/planning/report.py
"""Collect the step-level plan report, where the plan and the matrix are."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from otsafety_tooling.contracts.plan_report import PhaseRows, PlanReport, StepRow
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.ledger import load_ledger
from otsafety_tooling.planning.matrix import build as build_matrix
from otsafety_tooling.planning.status import staged_facts, unmet

TARGET = Path("build/onepager/plan-report.json")


def collect(root: Path = REPO_ROOT) -> PlanReport:
    """Every step, its state, what it waits on, what proves it, what is missing."""
    plan = load()
    facts = staged_facts(root)
    gaps = {step.id: unmet(plan, facts, step.id) for step in plan.steps}
    done = {identifier for identifier, missing in gaps.items() if not missing}
    ready = {
        step.id
        for step in plan.steps
        if step.id not in done and all(d in done for d in step.depends_on)
    }

    phases: list[PhaseRows] = []
    for phase in plan.phases:
        mine = [s for s in plan.steps if s.phase == phase.id]
        rows: list[StepRow] = []
        for step in mine:
            evidence: list[str] = []
            for item in step.done_when:
                for attribute in ("path", "name", "number", "tag"):
                    value = getattr(item, attribute, None)
                    if value is not None:
                        evidence.append(f"{item.kind}:{value}")
            state: Literal["DONE", "READY", "BLOCK"] = (
                "DONE" if step.id in done else ("READY" if step.id in ready else "BLOCK")
            )
            rows.append(
                StepRow(
                    id=step.id,
                    title=step.title,
                    thread=step.thread,
                    state=state,
                    after=tuple(d for d in step.depends_on if d not in done),
                    evidence=tuple(evidence),
                    unmet=tuple(gaps[step.id]),
                )
            )
        phases.append(
            PhaseRows(
                id=phase.id,
                title=phase.title,
                done=sum(1 for s in mine if s.id in done),
                total=len(mine),
                steps=tuple(rows),
            )
        )

    matrix = build_matrix()
    return PlanReport(
        steps=len(plan.steps),
        steps_done=len(done),
        ready=len(ready),
        blocked=len(plan.steps) - len(done) - len(ready),
        ids=len(load_ledger().issued),
        requirements=len(matrix.requirements),
        orphans=len(matrix.orphan_candidates),
        phases=tuple(phases),
    )


def export(root: Path = REPO_ROOT) -> str:
    """The report as the sheet will read it."""
    return collect(root).model_dump_json(indent=2) + "\n"


def main() -> int:
    """Write the report, and say what it holds."""
    from otsafety_tooling.cli import note, result

    target = REPO_ROOT / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(export(), encoding="utf-8")
    seen = collect()
    note(f"wrote {TARGET}")
    return result(
        "plan:report",
        "success",
        "report_collected",
        f"{seen.steps_done} of {seen.steps} done, {seen.ready} ready, {seen.blocked} blocked",
        seen,
    )


if __name__ == "__main__":
    raise SystemExit(main())
