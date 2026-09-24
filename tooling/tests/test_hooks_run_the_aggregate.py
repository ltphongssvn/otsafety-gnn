# tooling/tests/test_hooks_run_the_aggregate.py
"""The push gate is the aggregate, not a list that drifts from it (G.7).

WHAT THIS PREVENTS. pre-push ran types and test -- two of ten gates. The other
eight ran only in CI, so a commit could pass every local hook and fail on the
runner; it did twice in one session, once because a workflow never installed the
project and once because a site gate was never exercised here.

LOCAL LIGHT, CI AUTHORITY -- BUT THE PUSH GATE IS THE SAME GATE. 2026 practice
measured a full local gate consuming more than half a delivery's wall clock, so
pre-commit stays fast and scoped. What is pushed, though, must have passed what
CI will run, and the only way that cannot drift is for the hook to run the
AGGREGATE rather than a list of gate names maintained beside it.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.lefthook_config import LefthookConfig
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.7")


def _jobs(hook: str) -> list[str]:
    config = read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig)
    return [job.run for job in getattr(config, hook.replace("-", "_")).jobs]


def test_the_push_gate_runs_the_aggregate() -> None:
    """One command, so a new gate is covered the day it is added."""
    assert any("mise run check" in run for run in _jobs("pre-push")), (
        "pre-push must run the aggregate gate, not a subset of it"
    )


def test_the_push_gate_names_no_individual_gate() -> None:
    """A hand-written list is what drifted: eight gates were missing from it."""
    named = [run for run in _jobs("pre-push") if "mise run" in run and "mise run check" not in run]
    assert named == [], f"pre-push names gates of its own, which will drift: {named}"


def test_the_commit_hook_stays_fast() -> None:
    """Pre-commit is scoped deliberately: a gate that takes minutes on every
    commit is bypassed, and a bypassed gate protects nothing."""
    slow = [run for run in _jobs("pre-commit") if "mise run check" in run]
    assert slow == [], f"the aggregate belongs on push, not on every commit: {slow}"
