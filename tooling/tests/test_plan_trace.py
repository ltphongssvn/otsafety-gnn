# tooling/tests/test_plan_trace.py
"""Every plan item traced to a source, and every source item accounted for.

WHY THIS EXISTS. The plan grew from 64 to 92 to 103 steps across verification
rounds because it was assembled from memory, and each round found what the last
had missed. Completeness judged by recall is not completeness. The trace records
every candidate drawn from every source, and requires each to map to a plan item
or be declared not a plan item, with a reason.

BOTH DIRECTIONS. An unmapped candidate means the plan is missing something. A
plan item no candidate points at means it holds something no source asked for,
which is how an invented step would show itself.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.contracts.plan_trace import PlanTrace, untraced


def _plan() -> ProjectPlan:
    return ProjectPlan.model_validate(
        {
            "contract": "project-plan/v1",
            "threads": [{"id": "F", "title": "Release"}],
            "phases": [{"id": "8F", "title": "Release"}],
            "loops": [{"id": "promise", "code": "contracts", "data": "evidence"}],
            "steps": [
                {
                    "id": "F.1",
                    "title": "Pinned",
                    "thread": "F",
                    "phase": "8F",
                    "serves": [{"loop": "promise", "side": "code"}],
                    "done_when": [{"kind": "pr", "number": 14}],
                },
                {
                    "id": "F.2",
                    "title": "Verified",
                    "thread": "F",
                    "phase": "8F",
                    "serves": [{"loop": "promise", "side": "data"}],
                    "done_when": [{"kind": "pr", "number": 14}],
                },
            ],
            "decisions": [
                {"id": "X.E10", "title": "Rulesets", "state": "declined", "reason": "owner"}
            ],
        }
    )


def _trace() -> dict[str, Any]:
    return {
        "contract": "plan-trace/v1",
        "sources": [{"id": "T1", "title": "First transcript", "locator": "session one"}],
        "candidates": [
            {"source": "T1", "ref": "row 1", "text": "Pin the CLI", "maps_to": ["F.1"]},
            {"source": "T1", "ref": "row 2", "text": "Verify after deploy", "maps_to": ["F.2"]},
            {"source": "T1", "ref": "row 3", "text": "Branch protection", "maps_to": ["X.E10"]},
            {
                "source": "T1",
                "ref": "row 4",
                "text": "One command per answer",
                "not_a_plan_item": "a working rule, not a deliverable",
            },
        ],
    }


def test_a_complete_trace_leaves_nothing_untraced() -> None:
    assert untraced(PlanTrace.model_validate(_trace()), _plan()) == []


@pytest.mark.parametrize(
    ("mutation", "index", "change"),
    [
        ("mapped and dismissed at once", 0, {"not_a_plan_item": "both"}),
        ("neither mapped nor dismissed", 3, {"not_a_plan_item": None}),
        ("dismissed with an empty reason", 3, {"not_a_plan_item": ""}),
        ("an unknown source", 0, {"source": "T9"}),
        ("empty text", 0, {"text": ""}),
    ],
)
def test_each_malformed_candidate_is_refused(
    mutation: str, index: int, change: dict[str, Any]
) -> None:
    trace = copy.deepcopy(_trace())
    trace["candidates"][index].update(change)
    with pytest.raises(ValidationError):
        PlanTrace.model_validate(trace)


def test_a_candidate_pointing_at_no_plan_item_is_reported() -> None:
    trace = copy.deepcopy(_trace())
    trace["candidates"][0]["maps_to"] = ["F.9"]
    problems = untraced(PlanTrace.model_validate(trace), _plan())
    assert any("F.9" in p for p in problems)


def test_a_plan_item_no_source_asked_for_is_reported() -> None:
    """How an invented step shows itself."""
    trace = copy.deepcopy(_trace())
    del trace["candidates"][1]
    problems = untraced(PlanTrace.model_validate(trace), _plan())
    assert any("F.2" in p for p in problems)
