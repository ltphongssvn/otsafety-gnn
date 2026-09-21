# tooling/tests/test_wandb_tracker.py
"""Weights & Biases is an adapter behind the same port as MLflow, from day one.

FIRST-CLASS, NOT AN AFTERTHOUGHT. cs1090a-recsys reserved a slot for W&B --
"adding W&B later is a composition rather than a rewrite" -- and never filled
it. These tests mirror test_mlflow_tracker.py assertion for assertion, so the
two trackers are held to one standard.

OFFLINE, SO THE SUITE IS HERMETIC. WANDB_MODE=offline writes the run to disk
under a temporary directory: no network, no API key, nothing to leak.

THE BOUNDARY THESE TESTS OWN. Offline, W&B 0.30 writes no config.yaml and no
wandb-summary.json: both live only in run-*.wandb, a binary protobuf log read
through wandb.sdk.internal. Parsing it would test W&B's storage and break on
their upgrades rather than on our bugs. So a thin spy records what this adapter
HANDS W&B, and delegates to the real init, so the real offline run still happens
and its directory, its syncstate and our attached record are checked on disk.

W&B READS ITS ENVIRONMENT ONCE PER PROCESS. wandb.setup() is a singleton, so a
second test changing WANDB_MODE changed nothing until wandb.teardown() ran
between tests. In production that is exactly right -- each experiment is its own
process -- and here it is what makes each test read its own environment.

THE ADAPTER NEVER DECIDES THE MODE. 2026 guidance is plain: the mode is a
runtime concern set by the environment, not an algorithm detail set in code. So
one test sets WANDB_MODE=disabled and asserts nothing is written -- proof the
adapter obeyed the environment rather than overriding it. And one asserts an
initialisation failure propagates: a tracker that swallows its own failure is
how "first-class" quietly becomes "absent".
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from otsafety_tooling.contracts.experiment_run import ExperimentRun

wandb = pytest.importorskip("wandb", reason="the wandb extra is not installed")

from otsafety_tooling.tracking_wandb import RECORD_FILENAME, WandbTracker  # noqa: E402

START = datetime(2026, 9, 19, 5, 30, tzinfo=UTC)
COMMIT = "a" * 40
DIGEST = "b" * 64


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The environment decides the mode; these tests declare it, the adapter reads it."""
    monkeypatch.setenv("WANDB_MODE", "offline")
    monkeypatch.setenv("WANDB_PROJECT", "otsafety-gnn-test")
    monkeypatch.setenv("WANDB_SILENT", "true")
    monkeypatch.delenv("WANDB_API_KEY", raising=False)
    wandb.teardown()
    yield
    wandb.teardown()


class _Summary:
    """Records what the adapter writes to the summary, then writes it for real."""

    def __init__(self, real: Any, sink: dict[str, Any]) -> None:
        self._real = real
        self._sink = sink

    def update(self, values: dict[str, Any]) -> None:
        self._sink.update(values)
        self._real.update(values)


class _Run:
    """The real run, with its summary and logged artifacts observed; the rest delegates."""

    def __init__(self, real: Any, sink: dict[str, Any], logged: list[Any]) -> None:
        self._real = real
        self.summary = _Summary(real.summary, sink)
        self._logged = logged

    def log_artifact(self, artifact: Any, *args: Any, **kwargs: Any) -> Any:
        self._logged.append(artifact)
        return self._real.log_artifact(artifact, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


@pytest.fixture
def handed(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """What the adapter handed W&B: the init config and the summary."""
    seen: dict[str, Any] = {"config": None, "summary": {}, "artifacts": [], "init": {}}
    real_init = wandb.init

    def spy(*args: Any, **kwargs: Any) -> Any:
        seen["init"] = dict(kwargs)
        seen["config"] = dict(kwargs.get("config") or {})
        return _Run(real_init(*args, **kwargs), seen["summary"], seen["artifacts"])

    monkeypatch.setattr(wandb, "init", spy)
    return seen


def _run(**overrides: Any) -> ExperimentRun:
    payload: dict[str, Any] = {
        "id": "0192f3ac9e7b",
        "experiment": "degree-null",
        "started_at": START,
        "ended_at": START + timedelta(seconds=12),
        "duration_ms": 12000,
        "status": "completed",
        "commit": COMMIT,
        "working_tree_clean": True,
        "dataset": "opentargets-26.03",
        "dataset_digest": DIGEST,
        "seeds": {"python": 7},
        "deterministic": True,
        "python_version": "3.13.15",
        "packages": {"numpy": "2.3.4"},
        "params": {"alpha": 1.0},
        "metrics": {"average_precision": 0.41},
        "artifacts": {"model.pt": DIGEST},
        "machine": "8f14e45f-ea8f-4b1a-9c3d-2b6b1a0f7e21",
    }
    payload.update(overrides)
    return ExperimentRun.model_validate(payload)


def _tracker(tmp_path: Path) -> WandbTracker:
    return WandbTracker(directory=tmp_path)


def _runs(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "wandb").glob("offline-run-*"))


def _only_run(tmp_path: Path) -> Path:
    runs = _runs(tmp_path)
    assert len(runs) == 1, runs
    return runs[0]


def test_a_run_reaches_wandb_with_its_parameters_and_metrics(
    tmp_path: Path, handed: dict[str, Any]
) -> None:
    _tracker(tmp_path).record(_run())

    _only_run(tmp_path)
    assert handed["config"]["alpha"] == 1.0
    assert handed["summary"]["average_precision"] == pytest.approx(0.41)


def test_the_reproducibility_facts_are_recorded(tmp_path: Path, handed: dict[str, Any]) -> None:
    """A run in W&B must answer which code and which data produced it."""
    _tracker(tmp_path).record(_run())

    config = handed["config"]
    assert config["commit"] == COMMIT
    assert config["dataset"] == "opentargets-26.03"
    assert config["dataset_digest"] == DIGEST
    assert config["working_tree_clean"] is True
    assert config["deterministic"] is True


def test_the_record_itself_is_attached_so_wandb_is_not_the_only_copy(
    tmp_path: Path,
) -> None:
    _tracker(tmp_path).record(_run())

    attached = _only_run(tmp_path) / "files" / RECORD_FILENAME
    assert attached.is_file()
    restored = ExperimentRun.model_validate_json(attached.read_text(encoding="utf-8"))
    assert restored == _run()


def test_an_offline_run_can_be_synced_later(tmp_path: Path) -> None:
    """wandb sync reads the syncstate; without it, offline is a dead end."""
    _tracker(tmp_path).record(_run())

    run_dir = _only_run(tmp_path)
    assert list(run_dir.glob("run-*.wandb")), "no run log for wandb sync to replay"
    assert list(run_dir.glob("run-*.wandb.syncstate")), "no syncstate for wandb sync"


def test_a_failed_run_is_recorded_as_failed(tmp_path: Path, handed: dict[str, Any]) -> None:
    _tracker(tmp_path).record(_run(status="failed", error_type="Diverged", metrics={}))

    assert handed["config"]["status"] == "failed"
    assert handed["config"]["error_type"] == "Diverged"


def test_the_run_keeps_the_times_it_was_measured_with(
    tmp_path: Path, handed: dict[str, Any]
) -> None:
    """W&B cannot backdate a run, so the experiment's own times are recorded
    explicitly; its timestamp would measure the recording, not the experiment."""
    _tracker(tmp_path).record(_run())

    config = handed["config"]
    assert config["started_at"] == START.isoformat()
    assert config["ended_at"] == (START + timedelta(seconds=12)).isoformat()
    assert config["duration_ms"] == 12000


def test_two_runs_of_one_experiment_are_both_kept(tmp_path: Path) -> None:
    tracker = _tracker(tmp_path)
    tracker.record(_run(id="a" * 12))
    tracker.record(_run(id="c" * 12, metrics={"average_precision": 0.44}))

    assert len(_runs(tmp_path)) == 2


def test_artifact_digests_are_recorded(tmp_path: Path, handed: dict[str, Any]) -> None:
    """The bytes are elsewhere; W&B records which bytes they were."""
    _tracker(tmp_path).record(_run())

    assert handed["config"]["artifact_digests"] == {"model.pt": DIGEST}


def test_a_parameter_cannot_overwrite_a_reproducibility_fact(tmp_path: Path) -> None:
    """W&B's config is flat, so a parameter named commit would erase the real one."""
    with pytest.raises(ValueError, match="overwrite reproducibility facts"):
        _tracker(tmp_path).record(_run(params={"commit": "fake"}))


def test_the_adapter_obeys_the_environment_rather_than_choosing_a_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mode is a runtime concern. Disabled in the environment means nothing
    is written; an adapter that forced offline would write a run here."""
    monkeypatch.setenv("WANDB_MODE", "disabled")
    _tracker(tmp_path).record(_run())

    assert _runs(tmp_path) == []


def test_an_initialisation_failure_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tracker that swallows its own failure is how first-class becomes absent."""

    def refuse(*_: Any, **__: Any) -> Any:
        raise RuntimeError("api key not configured")

    monkeypatch.setattr(wandb, "init", refuse)
    with pytest.raises(RuntimeError, match="api key not configured"):
        _tracker(tmp_path).record(_run())


def test_runs_default_to_the_evidence_root_so_a_worktree_cannot_delete_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """config_root is the worktree in a linked worktree; the evidence root is not."""
    from otsafety_tooling.artifacts import artifacts_root
    from otsafety_tooling.paths import REPO_ROOT

    monkeypatch.delenv("WANDB_DIR", raising=False)
    assert WandbTracker().directory == artifacts_root(REPO_ROOT)


def test_an_explicit_wandb_dir_is_left_to_wandb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_DIR", "/somewhere/chosen")
    assert WandbTracker().directory is None


# --- what cs1090b proved and this adapter lacked ------------------------------
# cs1090b-HallucinationLegalRAGChatbots ran W&B online with real runs on wandb.ai.
# It uploaded its reports as versioned Artifacts, with lineage, where this adapter
# only wrote a file into the run directory; a file there is not versioned, not
# addressable as name:version, and cannot be consumed by a later run.


def test_the_record_is_logged_as_a_versioned_artifact(
    tmp_path: Path, handed: dict[str, Any]
) -> None:
    _tracker(tmp_path).record(_run())

    logged = handed["artifacts"]
    assert len(logged) == 1, logged
    artifact = logged[0]
    assert artifact.type == "experiment-run"
    assert artifact.name == "degree-null-0192f3ac9e7b"


def test_the_artifact_carries_the_facts_that_identify_it(
    tmp_path: Path, handed: dict[str, Any]
) -> None:
    """An artifact found on its own must still say which code and data made it."""
    _tracker(tmp_path).record(_run())

    metadata = handed["artifacts"][0].metadata
    assert metadata["commit"] == COMMIT
    assert metadata["dataset_digest"] == DIGEST
    assert metadata["reproducible"] is True
