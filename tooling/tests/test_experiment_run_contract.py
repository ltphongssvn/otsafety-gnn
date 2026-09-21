# tooling/tests/test_experiment_run_contract.py
"""experiment-run/v1: what a reproducible experiment IS, before one is run.

THE PROBLEM THIS SOLVES, IN THE WORDS OF PRACTITIONERS: both MLflow and
Weights & Biases log what you tell them to log, so inconsistent instrumentation
quietly destroys reproducibility. Here the facts that make a run reproducible
are REQUIRED: the commit and whether the tree was clean, the dataset and its
digest, the seeds and whether the run is deterministic, the Python version and
the exact package versions. A run missing any of them cannot be recorded.

VENDOR-FREE. Nothing here names MLflow or W&B; they are adapters that translate
this record, so training code never imports either.

PRIVACY. The machine is an opaque identifier and no field carries a path, a
username or a hostname: experiment records are shared evidence.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.experiment_run import ExperimentRun

START = datetime(2026, 9, 19, 1, 12, 0, tzinfo=UTC)
COMMIT = "a" * 40
DIGEST = "b" * 64
MACHINE = "8f14e45f-ea8f-4b1a-9c3d-2b6b1a0f7e21"


def _run(**overrides: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "id": "0192f3ac9e7b",
        "experiment": "baseline-ridge",
        "started_at": START,
        "ended_at": START + timedelta(seconds=30),
        "duration_ms": 30000,
        "status": "completed",
        "commit": COMMIT,
        "working_tree_clean": True,
        "dataset": "movielens-1m",
        "dataset_digest": DIGEST,
        "seeds": {"python": 7, "numpy": 7},
        "deterministic": True,
        "python_version": "3.13.15",
        "packages": {"numpy": "2.3.4", "scikit-learn": "1.7.2"},
        "params": {"alpha": 1.0, "fit_intercept": True},
        "metrics": {"rmse": 0.8721, "mae": 0.6893},
        "artifacts": {"model.joblib": DIGEST},
        "machine": MACHINE,
    }
    run.update(overrides)
    return run


def test_a_complete_run_survives_a_json_round_trip() -> None:
    run = ExperimentRun.model_validate(_run())
    assert run.contract == "experiment-run/v1"
    assert ExperimentRun.model_validate_json(run.model_dump_json()) == run


def test_a_run_cannot_be_changed_after_it_is_recorded() -> None:
    run = ExperimentRun.model_validate(_run())
    with pytest.raises(ValidationError, match="frozen"):
        run.metrics = {}  # type: ignore[misc]


def test_unknown_fields_are_rejected() -> None:
    """A vendor-specific field belongs in the adapter, not in the contract."""
    with pytest.raises(ValidationError, match="extra"):
        ExperimentRun.model_validate(_run(wandb_url="https://wandb.ai/x"))


@pytest.mark.parametrize(
    "missing",
    ["commit", "dataset_digest", "seeds", "python_version", "packages", "working_tree_clean"],
)
def test_the_reproducibility_facts_are_all_required(missing: str) -> None:
    """Remembering to log them is exactly what fails in practice."""
    incomplete = _run()
    del incomplete[missing]
    with pytest.raises(ValidationError):
        ExperimentRun.model_validate(incomplete)


def test_an_experiment_without_seeds_is_refused() -> None:
    with pytest.raises(ValidationError, match="seed"):
        ExperimentRun.model_validate(_run(seeds={}))


def test_an_environment_without_packages_is_refused() -> None:
    with pytest.raises(ValidationError, match="package"):
        ExperimentRun.model_validate(_run(packages={}))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_metric_that_is_not_a_number_is_refused(value: float) -> None:
    """NaN in a metric is a bug in the run, not a result to compare."""
    with pytest.raises(ValidationError):
        ExperimentRun.model_validate(_run(metrics={"rmse": value}))


def test_a_failed_run_names_its_error_and_a_completed_one_does_not() -> None:
    failed = _run(status="failed", metrics={})
    with pytest.raises(ValidationError, match="error_type"):
        ExperimentRun.model_validate(failed)
    assert ExperimentRun.model_validate({**failed, "error_type": "Diverged"}).error_type
    with pytest.raises(ValidationError, match="error_type"):
        ExperimentRun.model_validate(_run(error_type="Diverged"))


def test_time_cannot_run_backwards() -> None:
    with pytest.raises(ValidationError, match="ended_at"):
        ExperimentRun.model_validate(_run(ended_at=START - timedelta(seconds=1), duration_ms=0))


def test_the_experiment_name_is_stable_and_carries_no_dynamic_part() -> None:
    with pytest.raises(ValidationError):
        ExperimentRun.model_validate(_run(experiment="baseline ridge 2026-09-19"))


def test_artifacts_are_recorded_by_digest_not_by_path() -> None:
    """A path names one machine; a digest names the bytes anywhere."""
    with pytest.raises(ValidationError):
        ExperimentRun.model_validate(_run(artifacts={"model": "/Users/someone/model.joblib"}))


def test_a_run_from_a_dirty_tree_is_recorded_as_such() -> None:
    """Refusing would push people to record nothing; declaring keeps it honest."""
    run = ExperimentRun.model_validate(_run(working_tree_clean=False))
    assert not run.working_tree_clean
    assert not run.is_reproducible


def test_a_clean_deterministic_run_is_reproducible() -> None:
    assert ExperimentRun.model_validate(_run()).is_reproducible


def test_a_non_deterministic_run_is_not_reproducible() -> None:
    assert not ExperimentRun.model_validate(_run(deterministic=False)).is_reproducible
