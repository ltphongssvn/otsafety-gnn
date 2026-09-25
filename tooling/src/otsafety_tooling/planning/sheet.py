# tooling/src/otsafety_tooling/planning/sheet.py
"""Collect what the architecture sheet reports, where the tooling actually is.

THE RENDERER IS A PURE TRANSFORM. It gets a document; it does not go and look.
Collection needs the plan, the ledger, the matrix, the task file and the commit
graph -- none of which exist in the image that renders the sheet -- so it happens
here and the result is committed as sheet-facts/v1, drift-gated like every other
export.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.sheet_facts import PhaseFact, SheetFacts, ThreadFact
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load
from otsafety_tooling.planning.ledger import load_ledger
from otsafety_tooling.planning.matrix import build as build_matrix
from otsafety_tooling.planning.status import staged_facts, unmet

TARGET = Path("build/onepager/sheet-facts.json")

DEFINITION = re.compile(r"^def test_", re.MULTILINE)


def _test_functions(root: Path) -> int:
    """How many test functions the repository defines.

    FUNCTIONS, NOT CASES: a parametrised function is one definition and many
    cases, so this is the smaller and more stable of the two numbers, and the
    sheet says which it means.
    """
    total = 0
    for where in ("tooling/tests", "apps/site/tests"):
        for path in sorted((root / where).rglob("test_*.py")):
            total += len(DEFINITION.findall(path.read_text(encoding="utf-8")))
    return total


def collect(root: Path = REPO_ROOT) -> SheetFacts:
    """Every figure the sheet states, observed once."""
    plan = load()
    facts = staged_facts(root)
    closed = {step.id: not unmet(plan, facts, step.id) for step in plan.steps}
    matrix = build_matrix()

    phases: list[PhaseFact] = []
    first_open = True
    for phase in plan.phases:
        mine = [s for s in plan.steps if s.phase == phase.id]
        done = sum(closed[s.id] for s in mine)
        phase_state: Literal["done", "now", "todo"]
        if mine and done == len(mine):
            phase_state = "done"
        elif first_open:
            phase_state, first_open = "now", False
        else:
            phase_state = "todo"
        phases.append(
            PhaseFact(id=phase.id, title=phase.title, done=done, total=len(mine), state=phase_state)
        )

    threads: list[ThreadFact] = []
    for thread in plan.threads:
        mine = [s for s in plan.steps if s.thread == thread.id]
        done = sum(closed[s.id] for s in mine)
        percent = round(100 * done / len(mine)) if mine else 0
        thread_state: Literal["done", "active", "todo"] = (
            "done" if mine and done == len(mine) else ("active" if done else "todo")
        )
        threads.append(
            ThreadFact(
                id=thread.id,
                title=thread.title,
                done=done,
                total=len(mine),
                percent=percent,
                state=thread_state,
            )
        )

    merges = [
        line
        for line in git("log", "--oneline", "--merges", "origin/develop").stdout.splitlines()
        if line.strip()
    ]
    return SheetFacts(
        steps=len(plan.steps),
        steps_done=sum(closed.values()),
        ids=len(load_ledger().issued),
        requirements=len(matrix.requirements),
        unconfirmed=sum(1 for row in matrix.requirements if row.unconfirmed),
        test_functions=_test_functions(root),
        merged_prs=len(merges),
        tasks=len(read_toml(root / "mise.toml", MiseConfig).tasks),
        phases=tuple(phases),
        threads=tuple(threads),
    )


def export(root: Path = REPO_ROOT) -> str:
    """The facts as the sheet will read them, ending in a newline."""
    return collect(root).model_dump_json(indent=2) + "\n"


def main() -> int:
    """Write the facts, and say what was observed."""
    from otsafety_tooling.cli import note, result

    target = REPO_ROOT / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(export(), encoding="utf-8")
    seen = collect()
    note(f"wrote {TARGET}")
    return result(
        "sheet:facts",
        "success",
        "facts_collected",
        f"{seen.steps_done} of {seen.steps} steps, {seen.test_functions} test functions, "
        f"{seen.merged_prs} pull requests",
        seen,
    )


if __name__ == "__main__":
    raise SystemExit(main())
