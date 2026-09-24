# tooling/tests/test_branch_prune_contract.py
"""branch-prune/v1: every pruning decision, and what came of it, as data.

A deletion on the shared remote is irreversible for everyone, so each one is
recorded with the report that justified it, the reason, and the outcome. The
contract refuses records that contradict themselves: a kept branch marked
deleted, a plan that claims deletions, a failure reported as a pass.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.branch_prune import PruneDecision, PruneRecord


def _decision(**overrides: object) -> dict[str, object]:
    decision: dict[str, object] = {
        "branch": "origin/feature/done",
        "decision": "delete",
        "reason_code": "DELETE_MERGED",
        "message": "merged into origin/develop",
        "outcome": "deleted",
    }
    decision.update(overrides)
    return decision


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "generated_at": datetime(2026, 9, 17, tzinfo=UTC),
        "repository": "owner/repo",
        "source_report": "20260917T070050043911Z.json",
        "applied": True,
        "decisions": [_decision()],
        "verdict": "pass",
    }
    record.update(overrides)
    return record


def test_an_applied_record_survives_a_json_round_trip() -> None:
    record = PruneRecord.model_validate(_record())
    assert record.contract == "branch-prune/v1"
    assert PruneRecord.model_validate_json(record.model_dump_json()) == record


def test_a_kept_branch_cannot_have_been_deleted() -> None:
    with pytest.raises(ValidationError, match="keep"):
        PruneDecision.model_validate(
            _decision(decision="keep", reason_code="KEEP_NOT_MERGED", outcome="deleted")
        )


def test_a_deletion_must_be_justified_by_a_merge() -> None:
    with pytest.raises(ValidationError, match="DELETE_MERGED"):
        PruneDecision.model_validate(_decision(reason_code="KEEP_PROTECTED"))


def test_a_plan_cannot_claim_deletions() -> None:
    with pytest.raises(ValidationError, match="plan"):
        PruneRecord.model_validate(_record(applied=False))


def test_an_applied_run_leaves_nothing_merely_planned() -> None:
    with pytest.raises(ValidationError, match="planned"):
        PruneRecord.model_validate(_record(decisions=[_decision(outcome="planned")]))


def test_a_failed_deletion_fails_the_run() -> None:
    failed = [_decision(outcome="failed")]
    with pytest.raises(ValidationError, match="verdict"):
        PruneRecord.model_validate(_record(decisions=failed, verdict="pass"))
    assert PruneRecord.model_validate(_record(decisions=failed, verdict="fail")).verdict == "fail"


def test_a_run_without_a_branch_report_is_unknown() -> None:
    with pytest.raises(ValidationError, match="verdict"):
        PruneRecord.model_validate(
            _record(source_report=None, applied=False, decisions=[], verdict="pass")
        )
    record = PruneRecord.model_validate(
        _record(source_report=None, applied=False, decisions=[], verdict="unknown")
    )
    assert record.verdict == "unknown"
