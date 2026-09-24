# tooling/tests/test_plan_contract.py
"""The project plan is intent as data; its status is observed, never typed.

WHY THIS EXISTS. The plan was prose, its status re-typed by hand at each step,
and every re-typing drifted: the one-pager still says "11 pull requests" when 19
are merged, and a thread was reported at 90% that was nearer 40. The drift was
always a typed status. So the plan declares only intent -- threads, phases,
steps, explicit dependencies, and for every step the evidence that proves it
done -- and status is derived from that evidence by observation.

SEMANTIC RULES, MUTATION-TESTED. 2026 roadmap-as-code practice validates unique
ids, resolvable references and the absence of dependency cycles beyond what a
schema can say, and proves the validator by requiring it to accept a converged
plan and refuse each deliberate mutation of it.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.plan import ProjectPlan


def _valid() -> dict[str, object]:
    return {
        "contract": "project-plan/v1",
        "threads": [{"id": "F", "title": "Release and deployment"}],
        "phases": [{"id": "8F", "title": "Release, deployment and supply chain"}],
        "loops": [
            {"id": "constrain", "code": "policy", "data": "verdicts with reasons"},
            {"id": "promise", "code": "contracts, SLOs", "data": "evidence"},
        ],
        "steps": [
            {
                "id": "F.1",
                "title": "Pinned CLI and image",
                "thread": "F",
                "phase": "8F",
                "serves": [{"loop": "promise", "side": "code"}],
                "done_when": [{"kind": "pr", "number": 14}],
            },
            {
                "id": "F.2",
                "title": "Tag-gated deploy",
                "thread": "F",
                "phase": "8F",
                "depends_on": ["F.1"],
                "branch": "feature/release-from-main",
                "serves": [
                    {"loop": "constrain", "side": "code"},
                    {"loop": "promise", "side": "data"},
                ],
                "done_when": [{"kind": "release", "tag": "v1.0.0"}],
            },
        ],
        "decisions": [
            {
                "id": "X.E10",
                "title": "Branch protection as data",
                "state": "declined",
                "reason": "no server-side rulesets, by the owner's decision",
            }
        ],
    }


def _mutate(path: str, value: object) -> dict[str, object]:
    plan = copy.deepcopy(_valid())
    node: object = plan
    *parents, last = path.split(".")
    for key in parents:
        if isinstance(node, list):
            node = node[int(key)]
        elif isinstance(node, dict):
            node = node[key]
        else:
            raise AssertionError(f"{path}: {key} does not address a list or a mapping")
    if isinstance(node, list):
        node[int(last)] = value
    elif isinstance(node, dict):
        node[last] = value
    else:
        raise AssertionError(f"{path}: {last} does not address a list or a mapping")
    return plan


def test_a_converged_plan_is_accepted() -> None:
    plan = ProjectPlan.model_validate(_valid())
    assert [s.id for s in plan.steps] == ["F.1", "F.2"]


@pytest.mark.parametrize(
    ("mutation", "path", "value"),
    [
        ("duplicate step id", "steps.1.id", "F.1"),
        ("unknown thread", "steps.0.thread", "Z"),
        ("unknown phase", "steps.0.phase", "99"),
        ("unknown dependency", "steps.1.depends_on", ["F.9"]),
        ("a step with no evidence", "steps.0.done_when", []),
        ("a decision with no reason", "decisions.0.reason", ""),
        ("an unknown evidence kind", "steps.0.done_when", [{"kind": "vibes"}]),
        ("a typed status", "steps.0.status", "done"),
        ("a step serving no loop", "steps.0.serves", []),
        ("a loop that is not declared", "steps.0.serves", [{"loop": "operate", "side": "code"}]),
        (
            "a side that is neither code nor data",
            "steps.0.serves",
            [{"loop": "promise", "side": "both"}],
        ),
        ("a loop missing its data side", "loops.0", {"id": "constrain", "code": "policy"}),
    ],
)
def test_each_mutation_is_refused(mutation: str, path: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(_mutate(path, value))


def test_a_dependency_cycle_is_refused() -> None:
    plan = _mutate("steps.0.depends_on", ["F.2"])
    with pytest.raises(ValidationError, match="cycle"):
        ProjectPlan.model_validate(plan)


def test_a_decision_may_not_reuse_a_step_id() -> None:
    plan = _mutate("decisions.0.id", "F.1")
    with pytest.raises(ValidationError, match="F.1"):
        ProjectPlan.model_validate(plan)


def test_a_superseded_decision_names_what_replaced_it() -> None:
    """GitHub Pages was replaced by Railway; the spike by red-first re-derivation."""
    plan = _mutate("decisions.0.state", "superseded")
    ProjectPlan.model_validate(plan)


@pytest.mark.parametrize("value", [9.1, 9.10, 0.1])
def test_a_numeric_id_is_refused_never_coerced(value: float) -> None:
    """YAML reads an unquoted 9.10 as the float 9.1, which then collides with step
    9.1. Coercing it to a string would have hidden the collision; refusing it
    forces every id in the plan file to be quoted."""
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(_mutate("steps.0.id", value))
