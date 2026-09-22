# tooling/src/otsafety_tooling/planning/status.py
"""Derive the plan's status from facts observed on the integration branch.

A PURE FUNCTION: the plan and the facts in, a PlanStatus out. No git and no
network here, so every rule is testable in memory; gathering the facts is the
adapter's job.

THE RULES. A step is done when every piece of its evidence holds; in progress
when some does, or when its branch holds commits beyond develop; ready when all
it depends on is done; otherwise blocked, naming what it waits for. A branch
counts only with commits of its own: the first probe trusted any branch that
existed, and an empty, abandoned one read as work in flight.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, RootModel

from otsafety_tooling.contracts.files import parse_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.plan import (
    Evidence,
    PathEvidence,
    PrEvidence,
    ProjectPlan,
    ReleaseEvidence,
    TaskEvidence,
)
from otsafety_tooling.contracts.plan_status import PlanStatus, StepStatus
from otsafety_tooling.git.env import git
from otsafety_tooling.git.ghcli import gh_json

__all__ = ["Facts", "PlanStatus", "StepStatus", "derive", "gather_facts", "staged_facts", "unmet"]


class Facts(BaseModel):
    """What was observed, and where."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    paths: frozenset[str]
    tasks: frozenset[str]
    merged_prs: frozenset[int]
    tags: frozenset[str]
    # Branches holding commits beyond the integration branch -- not merely existing.
    branches_with_work: frozenset[str]


def _holds(evidence: Evidence, facts: Facts) -> bool:
    if isinstance(evidence, PathEvidence):
        return evidence.path in facts.paths
    if isinstance(evidence, TaskEvidence):
        return evidence.name in facts.tasks
    if isinstance(evidence, PrEvidence):
        return evidence.number in facts.merged_prs
    if isinstance(evidence, ReleaseEvidence):
        return evidence.tag in facts.tags
    raise TypeError(f"unknown evidence {evidence!r}")


def derive(plan: ProjectPlan, facts: Facts) -> PlanStatus:
    done = {s.id for s in plan.steps if all(_holds(e, facts) for e in s.done_when)}
    steps: list[StepStatus] = []
    for step in plan.steps:
        if step.id in done:
            steps.append(StepStatus(id=step.id, state="done"))
        elif (step.branch and step.branch in facts.branches_with_work) or any(
            _holds(e, facts) for e in step.done_when
        ):
            steps.append(StepStatus(id=step.id, state="in_progress"))
        else:
            waiting = tuple(d for d in step.depends_on if d not in done)
            steps.append(
                StepStatus(id=step.id, state="blocked" if waiting else "ready", blocked_by=waiting)
            )
    threads = {
        t.id: (
            sum(1 for s in plan.steps if s.thread == t.id and s.id in done),
            sum(1 for s in plan.steps if s.thread == t.id),
        )
        for t in plan.threads
    }
    return PlanStatus(ref=facts.ref, steps=tuple(steps), threads=threads)


class _Pr(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    number: int


class _MergedPrs(RootModel[tuple[_Pr, ...]]):
    pass


def _merged_prs_from_github() -> frozenset[int]:
    found = gh_json(
        _MergedPrs, "pr", "list", "--state", "merged", "--limit", "1000", "--json", "number"
    )
    return frozenset(pr.number for pr in found.root)


def _lines(root: Path, *args: str) -> list[str]:
    result = git(*args, cwd=root)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def gather_facts(
    root: Path, ref: str, *, merged_prs: Callable[[], frozenset[int]] = _merged_prs_from_github
) -> Facts:
    """Observe the evidence ON THE REF, never on the disk.

    The first probe read the working tree, so an uncommitted file made a step look
    done. Paths and tasks come from the ref itself; a branch counts only when it
    holds commits beyond the ref.
    """
    shown = git("show", f"{ref}:mise.toml", cwd=root)
    tasks = (
        frozenset(parse_toml(shown.stdout, MiseConfig).tasks)
        if shown.returncode == 0
        else frozenset()
    )
    base = {
        ref,
        ref.removeprefix("origin/"),
        "HEAD",
        "origin/HEAD",
        "origin",
        "main",
        "origin/main",
    }
    with_work = frozenset(
        name.removeprefix("origin/")
        for name in _lines(
            root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/origin"
        )
        if name not in base and int(_lines(root, "rev-list", "--count", f"{ref}..{name}")[0]) > 0
    )
    return Facts(
        ref=ref,
        paths=frozenset(_lines(root, "ls-tree", "-r", "--name-only", ref)),
        tasks=tasks,
        merged_prs=merged_prs(),
        tags=frozenset(_lines(root, "tag", "--list")),
        branches_with_work=with_work,
    )


def _describe(evidence: Evidence) -> str:
    if isinstance(evidence, PathEvidence):
        return f"path {evidence.path} is not in the tree"
    if isinstance(evidence, TaskEvidence):
        return f"task {evidence.name} is not in mise.toml"
    if isinstance(evidence, PrEvidence):
        return f"pull request #{evidence.number} is not merged"
    return f"release {evidence.tag} is not tagged"


def unmet(plan: ProjectPlan, facts: Facts, step_id: str) -> list[str]:
    """What a step's evidence still lacks, in words; empty when every piece holds."""
    step = next((s for s in plan.steps if s.id == step_id), None)
    if step is None:
        return [f"{step_id} is a decision or unknown; it has no evidence to close"]
    return [_describe(e) for e in step.done_when if not _holds(e, facts)]


def staged_facts(root: Path) -> Facts:
    """The evidence in the index: what the commit being made will contain.

    gather_facts reads a ref, and a commit being made is not one yet. A merged pull
    request or a tag cannot exist in it, so a step proved only by those cannot be
    closed by a commit; it closes when the pull request merges.
    """
    shown = git("show", ":mise.toml", cwd=root)
    tasks = (
        frozenset(parse_toml(shown.stdout, MiseConfig).tasks)
        if shown.returncode == 0
        else frozenset()
    )
    return Facts(
        ref="the index",
        paths=frozenset(_lines(root, "ls-files")),
        tasks=tasks,
        merged_prs=frozenset(),
        tags=frozenset(),
        branches_with_work=frozenset(),
    )
