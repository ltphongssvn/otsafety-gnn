# tooling/src/otsafety_tooling/planning/render.py
"""The plan's status, rendered for a person to read. Pure: a plan and a status in."""

from __future__ import annotations

from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.contracts.plan_status import PlanStatus

MARK = {"done": "✅", "in_progress": "🔵", "ready": "⬜", "blocked": "🔒"}


def render(plan: ProjectPlan, status: PlanStatus) -> str:
    by_id = {s.id: s for s in status.steps}
    out = [
        f"PROJECT PLAN -- observed on {status.ref}: {status.done} of {status.total} steps done",
        "",
    ]
    for phase in plan.phases:
        rows = [s for s in plan.steps if s.phase == phase.id]
        if not rows:
            continue
        n = sum(1 for s in rows if by_id[s.id].state == "done")
        out.append(f"-- Phase {phase.id} . {phase.title}  ({n}/{len(rows)})")
        for step in rows:
            st = by_id[step.id]
            waits = f"   [after {', '.join(st.blocked_by)}]" if st.state == "blocked" else ""
            out.append(f"   {MARK[st.state]} {step.id:5s} {step.title[:84]}{waits}")
        out.append("")
    out.append("-- THREADS, computed from the steps above")
    for thread in plan.threads:
        done, total = status.threads[thread.id]
        filled = round(20 * done / total) if total else 0
        bar = "#" * filled + "." * (20 - filled)
        out.append(f"   {thread.id} {thread.title[:38]:38s} {bar} {done:3d}/{total:<3d}")
    out += ["", "-- NOW: in progress, then ready to start"]
    out += [
        f"   {MARK[by_id[i].state]} {i:5s} {next(s.title for s in plan.steps if s.id == i)[:88]}"
        for i in status.now
    ]
    out += [
        "",
        f"-- DECISIONS ({len(plan.decisions)}): deliberately not done, each with its reason",
    ]
    out += [f"   {d.state[:10]:10s} {d.id:9s} {d.title[:80]}" for d in plan.decisions]
    return "\n".join(out)
