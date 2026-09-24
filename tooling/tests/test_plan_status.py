# tooling/tests/test_plan_status.py
"""Status derived from observed evidence, never typed.

WHY THIS EXISTS. Every status in a hand-kept plan drifted, and the probe that
first observed status here trusted any existing branch as progress: an empty
branch, cut and abandoned, read as work in flight. Status is a pure function of
the plan and of facts observed on the integration branch, and a branch counts
only when it holds commits beyond develop.
"""

from __future__ import annotations

from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.planning.status import Facts, PlanStatus, derive


def _plan() -> ProjectPlan:
    def step(
        i: str, deps: list[str], ev: list[dict[str, object]], **kw: object
    ) -> dict[str, object]:
        return {
            "id": i,
            "title": i,
            "thread": "F",
            "phase": "8F",
            "depends_on": deps,
            "serves": [{"loop": "promise", "side": "code"}],
            "done_when": ev,
            **kw,
        }

    return ProjectPlan.model_validate(
        {
            "contract": "project-plan/v1",
            "threads": [{"id": "F", "title": "Release"}],
            "phases": [{"id": "8F", "title": "Release"}],
            "loops": [{"id": "promise", "code": "contracts", "data": "evidence"}],
            "steps": [
                step("F.1", [], [{"kind": "pr", "number": 14}]),
                step(
                    "F.2",
                    ["F.1"],
                    [{"kind": "path", "path": "a.py"}, {"kind": "release", "tag": "v1.0.0"}],
                    branch="feature/two",
                ),
                step("F.3", ["F.2"], [{"kind": "task", "name": "x"}]),
            ],
        }
    )


def _facts(**overrides: object) -> Facts:
    base = Facts(
        ref="origin/develop",
        paths=frozenset(),
        tasks=frozenset(),
        merged_prs=frozenset(),
        tags=frozenset(),
        branches_with_work=frozenset(),
    )
    unknown = set(overrides) - set(Facts.model_fields)
    assert not unknown, f"no such fact: {sorted(unknown)}"
    return base.model_copy(update=overrides)


def _state(status: PlanStatus, step_id: str) -> str:
    return next(s.state for s in status.steps if s.id == step_id)


def test_every_piece_of_evidence_makes_a_step_done() -> None:
    assert _state(derive(_plan(), _facts(merged_prs=frozenset({14}))), "F.1") == "done"


def test_some_evidence_is_progress() -> None:
    status = derive(_plan(), _facts(merged_prs=frozenset({14}), paths=frozenset({"a.py"})))
    assert _state(status, "F.2") == "in_progress"


def test_a_branch_with_commits_is_progress() -> None:
    status = derive(
        _plan(), _facts(merged_prs=frozenset({14}), branches_with_work=frozenset({"feature/two"}))
    )
    assert _state(status, "F.2") == "in_progress"


def test_an_empty_branch_is_not_progress() -> None:
    """The branch exists but holds nothing beyond develop, so it is not in branches_with_work."""
    assert _state(derive(_plan(), _facts(merged_prs=frozenset({14}))), "F.2") == "ready"


def test_a_blocked_step_names_what_it_waits_for() -> None:
    status = derive(_plan(), _facts())
    blocked = next(s for s in status.steps if s.id == "F.2")
    assert blocked.state == "blocked" and blocked.blocked_by == ("F.1",)


def test_progress_is_computed_never_typed() -> None:
    status = derive(_plan(), _facts(merged_prs=frozenset({14})))
    assert (status.done, status.total) == (1, 3)
    assert status.threads["F"] == (1, 3)


def test_now_lists_work_in_flight_before_work_that_could_start() -> None:
    status = derive(
        _plan(), _facts(merged_prs=frozenset({14}), branches_with_work=frozenset({"feature/two"}))
    )
    assert status.now == ("F.2",)
    assert derive(_plan(), _facts(merged_prs=frozenset({14}))).now == ("F.2",)
