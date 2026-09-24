# tooling/tests/test_run_record_contract.py
"""run-record/v1: what one task execution IS, before anything produces one.

SHAPED BY THE OPEN TELEMETRY CONVENTIONS for an operation with a duration and
a boundary: a stable name with no dynamic parts, flat fields, an error type on
failure, and identifiers carried as data rather than in the name.

PRIVACY. A record names the machine only by an opaque id, and holds no
hostname and no local path: records are shared evidence.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.run_record import RunRecord

START = datetime(2026, 9, 18, 1, 2, 3, tzinfo=UTC)
SHA = "c" * 40
DIGEST = "d" * 64


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "0192f3ac9e7b",
        "task": "branches",
        "arguments": ["--apply"],
        "started_at": START,
        "ended_at": START + timedelta(milliseconds=1500),
        "duration_ms": 1500,
        "exit_code": 0,
        "outcome": "success",
        "repository": "otsafety-gnn",
        "branch": "feature/run-records",
        "commit": SHA,
        "machine": "8f14e45f-ea8f-4b1a-9c3d-2b6b1a0f7e21",
        "output_file": "20260918T010203000000Z-branches-0192f3ac9e7b.log",
        "output_bytes": 412,
        "output_sha256": DIGEST,
        "truncated": False,
    }
    record.update(overrides)
    return record


def test_a_valid_record_survives_a_json_round_trip() -> None:
    record = RunRecord.model_validate(_record())
    assert record.contract == "run-record/v1"
    assert RunRecord.model_validate_json(record.model_dump_json()) == record


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        RunRecord.model_validate(_record(hostname="MacBookPro"))


def test_a_record_cannot_be_changed_after_creation() -> None:
    record = RunRecord.model_validate(_record())
    with pytest.raises(ValidationError, match="frozen"):
        record.exit_code = 1  # type: ignore[misc]


def test_success_means_exit_zero() -> None:
    with pytest.raises(ValidationError, match="outcome"):
        RunRecord.model_validate(_record(exit_code=1))


def test_failure_means_a_non_zero_exit() -> None:
    with pytest.raises(ValidationError, match="outcome"):
        RunRecord.model_validate(_record(outcome="failure", error_type="NonZeroExit"))


def test_a_failure_names_its_error_type() -> None:
    failed = _record(exit_code=2, outcome="failure")
    with pytest.raises(ValidationError, match="error_type"):
        RunRecord.model_validate(failed)
    assert RunRecord.model_validate({**failed, "error_type": "NonZeroExit"}).error_type


def test_a_success_carries_no_error_type() -> None:
    with pytest.raises(ValidationError, match="error_type"):
        RunRecord.model_validate(_record(error_type="NonZeroExit"))


def test_time_cannot_run_backwards() -> None:
    with pytest.raises(ValidationError, match="ended_at"):
        RunRecord.model_validate(_record(ended_at=START - timedelta(seconds=1), duration_ms=0))


def test_the_duration_matches_the_timestamps() -> None:
    with pytest.raises(ValidationError, match="duration"):
        RunRecord.model_validate(_record(duration_ms=99))


def test_timestamps_carry_a_time_zone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        RunRecord.model_validate(_record(started_at=datetime(2026, 9, 18, 1, 2, 3)))


@pytest.mark.parametrize("task", ["mise run branches", "branches 2026", "", "Branches"])
def test_the_task_name_is_stable_and_carries_no_dynamic_part(task: str) -> None:
    """OpenTelemetry: names identify a structure; identifiers belong in fields."""
    with pytest.raises(ValidationError):
        RunRecord.model_validate(_record(task=task))


def test_a_truncated_record_still_states_the_full_output_digest() -> None:
    truncated = RunRecord.model_validate(_record(truncated=True, output_bytes=65536))
    assert truncated.output_sha256 == DIGEST
    with pytest.raises(ValidationError, match="output"):
        RunRecord.model_validate(_record(output_file="", output_bytes=0))
