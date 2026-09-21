# tooling/tests/test_plan_files.py
"""The committed plan and its trace validate, and agree, in the gate.

These waited for the sanctioned YAML reader: the plan was checked by one-off
probes until read_yaml reached develop.
"""

from __future__ import annotations

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.contracts.plan_trace import PlanTrace, untraced
from otsafety_tooling.paths import REPO_ROOT

CONTEXT = REPO_ROOT / "context"


def test_the_plan_file_validates() -> None:
    assert read_yaml(CONTEXT / "plan.yaml", ProjectPlan).steps


def test_the_trace_agrees_with_the_plan_in_both_directions() -> None:
    plan = read_yaml(CONTEXT / "plan.yaml", ProjectPlan)
    assert untraced(read_yaml(CONTEXT / "plan-trace.yaml", PlanTrace), plan) == []
