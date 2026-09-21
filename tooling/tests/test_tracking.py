# tooling/tests/test_tracking.py
"""Experiments record themselves through a port, never through a vendor.

WHY A PORT AND NOT `import mlflow`. The contract exists because trackers log
only what they are told; the port exists so no experiment can reach past it.
MLflow and Weights & Biases arrive later as adapters, and no training code
changes when they do.

RECORDED EVEN WHEN IT FAILS. A run that raises still produces a record, with
its error type, and the exception still propagates. A failure that leaves no
evidence is how tracking quietly stops being trusted.

THE ENVIRONMENT IS GATHERED, NOT DECLARED. The commit, whether the tree was
clean, the Python version and the installed package versions come from the
running process, so an experiment cannot forget them or invent them.
"""

import hashlib
import importlib.util
from pathlib import Path

import pytest

from otsafety_tooling.contracts.experiment_run import ExperimentRun
from otsafety_tooling.git.env import git
from otsafety_tooling.tracking import (
    FanOutTracker,
    FileTracker,
    MemoryTracker,
    gather_environment,
    track,
)


def _git(*args: str, cwd: Path) -> None:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", "-b", "feature/x", cwd=root)
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=root)
    return root


DIGEST = "c" * 64


DATASET = "movielens-1m"


def test_the_environment_carries_every_required_fact(tmp_path: Path) -> None:
    environment = gather_environment(_repo(tmp_path))

    assert len(environment.commit) == 40
    assert environment.working_tree_clean
    assert environment.python_version.startswith("3.13")
    assert environment.packages
    assert "pydantic" in environment.packages


def test_a_dirty_tree_is_observed_not_assumed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")

    assert not gather_environment(root).working_tree_clean


def test_a_memory_tracker_keeps_what_it_was_given(tmp_path: Path) -> None:
    tracker = MemoryTracker()
    with track(
        "baseline",
        tracker,
        root=_repo(tmp_path),
        seeds={"python": 7},
        dataset=DATASET,
        dataset_digest=DIGEST,
    ) as run:
        run.metric("rmse", 0.87)

    (recorded,) = tracker.runs
    assert recorded.experiment == "baseline"
    assert recorded.metrics == {"rmse": 0.87}
    assert recorded.status == "completed"


def test_a_file_tracker_writes_one_valid_record(tmp_path: Path) -> None:
    records = tmp_path / "experiments"
    tracker = FileTracker(records)
    with track(
        "baseline",
        tracker,
        root=_repo(tmp_path),
        seeds={"python": 7},
        dataset=DATASET,
        dataset_digest=DIGEST,
    ):
        pass

    (written,) = sorted(records.glob("*.json"))
    run = ExperimentRun.model_validate_json(written.read_text(encoding="utf-8"))
    assert run.contract == "experiment-run/v1"
    assert run.experiment == "baseline"


def test_one_run_reaches_every_tracker(tmp_path: Path) -> None:
    """Adding MLflow or W&B later must be a composition, not a rewrite."""
    first, second = MemoryTracker(), MemoryTracker()
    with track(
        "baseline",
        FanOutTracker(first, second),
        root=_repo(tmp_path),
        seeds={"a": 1},
        dataset=DATASET,
        dataset_digest=DIGEST,
    ):
        pass

    assert len(first.runs) == len(second.runs) == 1
    assert first.runs[0] == second.runs[0]


def test_parameters_and_metrics_are_recorded(tmp_path: Path) -> None:
    tracker = MemoryTracker()
    with track(
        "ridge",
        tracker,
        root=_repo(tmp_path),
        seeds={"python": 7},
        dataset=DATASET,
        dataset_digest=DIGEST,
    ) as run:
        run.param("alpha", 1.0)
        run.param("fit_intercept", True)
        run.metric("rmse", 0.8721)

    recorded = tracker.runs[0]
    assert recorded.params == {"alpha": 1.0, "fit_intercept": True}
    assert recorded.metrics == {"rmse": 0.8721}


def test_a_failing_experiment_is_recorded_and_still_raises(tmp_path: Path) -> None:
    tracker = MemoryTracker()

    with pytest.raises(ZeroDivisionError):
        with track(
            "broken",
            tracker,
            root=_repo(tmp_path),
            seeds={"a": 1},
            dataset=DATASET,
            dataset_digest=DIGEST,
        ):
            raise ZeroDivisionError("diverged")

    (recorded,) = tracker.runs
    assert recorded.status == "failed"
    assert recorded.error_type == "ZeroDivisionError"


def test_an_artifact_is_recorded_by_its_digest(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    model = tmp_path / "model.joblib"
    model.write_bytes(b"weights")
    tracker = MemoryTracker()

    with track(
        "ridge", tracker, root=root, seeds={"a": 1}, dataset=DATASET, dataset_digest=DIGEST
    ) as run:
        run.artifact("model.joblib", model)

    assert tracker.runs[0].artifacts == {"model.joblib": hashlib.sha256(b"weights").hexdigest()}


def test_a_missing_artifact_is_refused_rather_than_recorded_as_absent(tmp_path: Path) -> None:
    tracker = MemoryTracker()
    with pytest.raises(FileNotFoundError):
        with track(
            "ridge",
            tracker,
            root=_repo(tmp_path),
            seeds={"a": 1},
            dataset=DATASET,
            dataset_digest=DIGEST,
        ) as run:
            run.artifact("model.joblib", tmp_path / "not-here.joblib")


def test_the_run_is_timed(tmp_path: Path) -> None:
    tracker = MemoryTracker()
    with track(
        "baseline",
        tracker,
        root=_repo(tmp_path),
        seeds={"a": 1},
        dataset=DATASET,
        dataset_digest=DIGEST,
    ):
        pass

    recorded = tracker.runs[0]
    assert recorded.duration_ms >= 0
    assert recorded.ended_at >= recorded.started_at


def test_determinism_is_declared_by_the_experiment(tmp_path: Path) -> None:
    tracker = MemoryTracker()
    with track(
        "sampled",
        tracker,
        root=_repo(tmp_path),
        seeds={"a": 1},
        deterministic=False,
        dataset=DATASET,
        dataset_digest=DIGEST,
    ):
        pass

    assert not tracker.runs[0].deterministic
    assert not tracker.runs[0].is_reproducible


# --- the composition root -----------------------------------------------------
# FanOutTracker existed and nothing assembled it, so every experiment chose its
# own trackers -- and the first one written in a hurry chooses FileTracker alone.
# That is how W&B became optional in cs1090b: a --log-to-wandb flag somebody had
# to remember. default_tracker() is the one place that decides, so an experiment
# cannot quietly record less than the project intends.


def test_the_default_tracker_writes_files_and_every_installed_backend() -> None:
    from otsafety_tooling.tracking import FanOutTracker, FileTracker, default_tracker

    tracker = default_tracker()
    assert isinstance(tracker, FanOutTracker)
    kinds = [type(t).__name__ for t in tracker.trackers]

    # The file tracker is not optional: it is the copy that survives a vendor.
    assert kinds[0] == FileTracker.__name__

    for module, adapter in (("mlflow", "MlflowTracker"), ("wandb", "WandbTracker")):
        if importlib.util.find_spec(module) is not None:
            assert adapter in kinds, f"{module} is installed but {adapter} is not composed"


def test_a_backend_that_is_not_installed_is_simply_absent() -> None:
    """Optional means optional: a missing extra must not break recording."""
    from otsafety_tooling.tracking import default_tracker

    tracker = default_tracker(backends=())
    assert [type(t).__name__ for t in tracker.trackers] == ["FileTracker"]
