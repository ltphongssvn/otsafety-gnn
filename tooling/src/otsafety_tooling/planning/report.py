# tooling/src/otsafety_tooling/planning/report.py
"""Collect the step-level plan report, where the plan and the matrix are."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.contracts.plan_report import PhaseRows, PlanReport, StepRow
from otsafety_tooling.contracts.sheet_facts import ThreadFact as ThreadRatio
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.ledger import load_ledger
from otsafety_tooling.planning.matrix import build as build_matrix
from otsafety_tooling.planning.status import staged_facts, unmet

TARGET = Path("build/onepager/plan-report.json")


class ReportWritten(BaseModel):
    """What the command did, without restating the document it wrote."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    steps: int
    steps_done: int
    ready: int
    blocked: int
    phases: int


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


def render_text(report: PlanReport, threads: tuple[ThreadRatio, ...] = ()) -> str:
    """The whole plan, for a reader: totals, threads, then every step in order."""
    out: list[str] = []
    rule = "=" * 104
    out.append(rule)
    out.append("  OTSAFETY-GNN -- every step in every phase, with state, dependencies and evidence")
    out.append(rule)
    out.append(
        f"  steps {report.steps}   done {report.steps_done}   open "
        f"{report.steps - report.steps_done}   of which ready {report.ready}   "
        f"blocked {report.blocked}"
    )
    out.append(
        f"  requirement ids {report.ids}   matrix rows {report.requirements}   "
        f"orphan observations {report.orphans}"
    )
    out.append("")

    if threads:
        out.append("-" * 104)
        out.append("  THREADS")
        out.append("-" * 104)
        for thread in threads:
            filled = thread.percent // 5
            bar = "#" * filled + "." * (20 - filled)
            out.append(
                f"  {thread.id:<2} {thread.title[:38]:<38} {bar} {thread.percent:>3}%  "
                f"{thread.done:>3} of {thread.total:<3}"
            )
        out.append("")

    for phase in report.phases:
        out.append(rule)
        out.append(
            f"  PHASE {phase.id:<4} {phase.title[:58]:<58} {phase.done:>3} of {phase.total:<3} done"
        )
        out.append(rule)
        for step in phase.steps:
            out.append(f"  [{step.state}] {step.id:<6} {step.title}")
            out.append(f"         thread {step.thread}")
            if step.after:
                out.append(f"         waiting on {', '.join(step.after)}")
            out.append(f"         evidence   {', '.join(step.evidence) or 'none declared'}")
            for gap in step.unmet:
                out.append(f"         UNMET      {gap}")
            out.append("")
    return "\n".join(out)


def export(root: Path = REPO_ROOT) -> str:
    """The report as the sheet will read it."""
    return collect(root).model_dump_json(indent=2) + "\n"


def main() -> int:
    """Write the report, print it for a reader, and report as data.

    THE HUMAN RENDERING GOES TO STDERR, which is what 2026 practice means by
    never polluting the payload channel: a caller parses the envelope on stdout
    while a reader watches the report scroll past. G.42 already draws that line.

    THE ENVELOPE CARRIES THE TOTALS, NOT THE STEPS. Emitting all of them put a
    hundred kilobytes of JSON on the terminal beside the report a reader had
    just been shown, which defeats the split it exists for -- and the document
    this writes holds every step for anything that needs them.
    """
    from otsafety_tooling.cli import note, result
    from otsafety_tooling.planning.sheet import collect as collect_facts

    target = REPO_ROOT / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(export(), encoding="utf-8")
    seen = collect()
    note(render_text(seen, collect_facts().threads))
    note(f"wrote {TARGET}")
    return result(
        "plan:report",
        "success",
        "report_collected",
        f"{seen.steps_done} of {seen.steps} done, {seen.ready} ready, {seen.blocked} blocked",
        ReportWritten(
            path=str(TARGET),
            steps=seen.steps,
            steps_done=seen.steps_done,
            ready=seen.ready,
            blocked=seen.blocked,
            phases=len(seen.phases),
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
