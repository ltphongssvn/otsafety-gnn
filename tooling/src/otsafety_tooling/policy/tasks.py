# tooling/src/otsafety_tooling/policy/tasks.py
"""Every task this repository offers is claimed by a step, both ways.

FORTY-SIX OF SIXTY-SIX WERE ORPHANS -- check, lint, test, fmt, commit, sync,
pr:merge among them. They ran, they gated every commit, and nothing recorded why
they existed or what depended on them. The matrix proves a step has evidence;
until now nothing proved a task has a step, so the traceability ran one way.

THE SIBLING NAMED THE COST: pr:merge stayed invisible for weeks there while four
dependency updates sat unmerged. A capability nobody authorised is a capability
nobody maintains.

BOTH DIRECTIONS, BECAUSE EACH CATCHES A DIFFERENT DRIFT. An orphan is a task no
step claims; a phantom is a step naming a task the repository no longer offers,
which is how a renamed task leaves a requirement pointing at nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.edit import load

# A TASK NAME AS IT APPEARS IN PROSE OR IN EVIDENCE: lowercase, colon-separated.
NAMED = re.compile(
    r"\b([a-z][a-z0-9-]*(?::[a-z][a-z0-9-]*)+|check|lint|types|test|fmt|commit|sync|setup|run)\b"
)


def declared(root: Path = REPO_ROOT) -> set[str]:
    """Every task the repository offers."""
    return set(read_toml(root / "mise.toml", MiseConfig).tasks)


def claimed(root: Path = REPO_ROOT) -> set[str]:
    """Every task name a step mentions, in its evidence or its own words."""
    names: set[str] = set()
    for step in load().steps:
        for item in step.done_when:
            name = getattr(item, "name", None)
            if name is not None:
                names.add(str(name))
        for text in (step.title, step.source or ""):
            names.update(NAMED.findall(text))
    return names


def unclaimed(tasks: Iterable[str], names: Iterable[str]) -> list[str]:
    """The pure rule, so the gate can be proved non-vacuous."""
    held = set(names)
    return sorted(task for task in tasks if task not in held)


def orphans(root: Path = REPO_ROOT) -> list[str]:
    """Tasks no step claims."""
    return unclaimed(declared(root), claimed(root))


def phantoms(root: Path = REPO_ROOT) -> list[str]:
    """Steps that are DONE and name a task the repository does not offer.

    AN OPEN STEP PROMISING A TASK IS THE PLAN WORKING. 10.1 names
    lightning:verify, F.9 names sbom:generate, G.9 names ledger:verify -- none
    exist, because none of those steps are built. Judging them would make the
    gate refuse the plan for describing the future, which is what a plan is for.

    A COMPLETED STEP IS DIFFERENT: it claims the task exists, so a rename that
    left the requirement pointing at nothing fails here.
    """
    from otsafety_tooling.planning.status import staged_facts, unmet

    offered = declared(root)
    plan = load()
    facts = staged_facts(root)
    missing: list[str] = []
    for step in plan.steps:
        if unmet(plan, facts, step.id):
            continue
        for item in step.done_when:
            name = getattr(item, "name", None)
            if name is not None and str(name) not in offered:
                missing.append(f"{step.id} -> {name}")
    return sorted(missing)
