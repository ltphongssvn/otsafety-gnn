# tooling/tests/test_mlflow_tracker.py
"""MLflow is an adapter behind the port, never something training code imports.

WHY IT IS OPTIONAL. MLflow is a large dependency, and a machine that only runs
the git tasks -- a runner that only syncs branches -- should not install it.
These tests skip when it is absent, so the suite stays green there, and the
adapter imports it inside its methods so tracking.py loads without it.

WHAT IS RECORDED. Parameters and metrics map to MLflow's own, the
reproducibility facts become tags, and the experiment-run/v1 record is attached
as an artifact so MLflow never becomes the only copy of what happened.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import pytest
from pydantic import TypeAdapter

from otsafety_tooling.contracts.experiment_run import Digest, ExperimentRun

mlflow = pytest.importorskip("mlflow", reason="the ml group is not installed")

from otsafety_tooling.tracking_mlflow import MlflowTracker, tracking_uri  # noqa: E402

pytestmark = pytest.mark.requirement("D.1")

START = datetime(2026, 9, 19, 5, 30, tzinfo=UTC)
COMMIT = "a" * 40
DIGEST = "b" * 64


def _run(**overrides: object) -> ExperimentRun:
    payload: dict[str, object] = {
        "id": "0192f3ac9e7b",
        "experiment": "baseline-ridge",
        "started_at": START,
        "ended_at": START + timedelta(seconds=12),
        "duration_ms": 12000,
        "status": "completed",
        "commit": COMMIT,
        "working_tree_clean": True,
        "dataset": "movielens-1m",
        "dataset_digest": DIGEST,
        "seeds": {"python": 7},
        "deterministic": True,
        "python_version": "3.13.15",
        "packages": {"numpy": "2.3.4"},
        "params": {"alpha": 1.0},
        "metrics": {"rmse": 0.87},
        "artifacts": {"model.joblib": DIGEST},
        "machine": "8f14e45f-ea8f-4b1a-9c3d-2b6b1a0f7e21",
    }
    payload.update(overrides)
    return ExperimentRun.model_validate(payload)


def _store(tmp_path: Path) -> Path:
    return tmp_path / "mlflow" / "runs.db"


class _RunData(Protocol):
    """The three mappings these tests read from a recorded run."""

    @property
    def params(self) -> dict[str, str]: ...

    @property
    def metrics(self) -> dict[str, float]: ...

    @property
    def tags(self) -> dict[str, str]: ...


class _RunInfo(Protocol):
    """The four fields these tests read from a recorded run's info."""

    @property
    def status(self) -> str: ...

    @property
    def start_time(self) -> int: ...

    @property
    def end_time(self) -> int: ...

    @property
    def artifact_uri(self) -> str: ...


class _Recorded(Protocol):
    """A recorded MLflow run, as these tests read it."""

    @property
    def data(self) -> _RunData: ...

    @property
    def info(self) -> _RunInfo: ...


def _tracker(tmp_path: Path) -> MlflowTracker:
    return MlflowTracker(store=_store(tmp_path))


def _recorded(tmp_path: Path, name: str) -> _Recorded:
    """The single MLflow run for an experiment, read back through MLflow."""
    mlflow.set_tracking_uri(tracking_uri(_store(tmp_path)))
    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name(name)
    assert experiment is not None, f"no MLflow experiment named {name}"
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1, runs
    recorded: _Recorded = runs[0]
    return recorded


def test_a_run_reaches_mlflow_with_its_parameters_and_metrics(tmp_path: Path) -> None:
    _tracker(tmp_path).record(_run())

    recorded = _recorded(tmp_path, "baseline-ridge")
    assert recorded.data.params["alpha"] == "1.0"
    assert recorded.data.metrics["rmse"] == pytest.approx(0.87)


def test_the_reproducibility_facts_become_tags(tmp_path: Path) -> None:
    """A run in MLflow must answer which code and which data produced it."""
    _tracker(tmp_path).record(_run())

    tags = _recorded(tmp_path, "baseline-ridge").data.tags
    assert tags["commit"] == COMMIT
    assert tags["dataset"] == "movielens-1m"
    assert tags["dataset_digest"] == DIGEST
    assert tags["working_tree_clean"] == "True"
    assert tags["deterministic"] == "True"


def test_the_record_itself_is_attached_so_mlflow_is_not_the_only_copy(
    tmp_path: Path,
) -> None:
    _tracker(tmp_path).record(_run())

    recorded = _recorded(tmp_path, "baseline-ridge")
    artifacts = Path(recorded.info.artifact_uri.removeprefix("file://"))
    attached = artifacts / "experiment-run.json"
    assert attached.is_file()
    restored = ExperimentRun.model_validate_json(attached.read_text(encoding="utf-8"))
    assert restored == _run()


def test_a_failed_run_is_recorded_as_failed(tmp_path: Path) -> None:
    _tracker(tmp_path).record(_run(status="failed", error_type="Diverged", metrics={}))

    recorded = _recorded(tmp_path, "baseline-ridge")
    assert recorded.info.status == "FAILED"
    assert recorded.data.tags["error_type"] == "Diverged"


def test_the_run_keeps_the_times_it_was_measured_with(tmp_path: Path) -> None:
    """MLflow's own timing would measure the recording, not the experiment."""
    _tracker(tmp_path).record(_run())

    recorded = _recorded(tmp_path, "baseline-ridge")
    assert recorded.info.start_time == int(START.timestamp() * 1000)
    assert recorded.info.end_time == int((START + timedelta(seconds=12)).timestamp() * 1000)


def test_two_runs_of_one_experiment_are_both_kept(tmp_path: Path) -> None:
    tracker = _tracker(tmp_path)
    tracker.record(_run(id="a" * 12))
    tracker.record(_run(id="c" * 12, metrics={"rmse": 0.81}))

    mlflow.set_tracking_uri(tracking_uri(_store(tmp_path)))
    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name("baseline-ridge")
    assert experiment is not None
    assert len(client.search_runs([experiment.experiment_id])) == 2


def test_artifact_digests_are_recorded_as_tags(tmp_path: Path) -> None:
    """The bytes are elsewhere; MLflow records which bytes they were."""
    _tracker(tmp_path).record(_run())

    tags = _recorded(tmp_path, "baseline-ridge").data.tags
    digests = TypeAdapter(dict[str, Digest]).validate_json(tags["artifact_digests"])
    assert digests == {"model.joblib": DIGEST}
