# tooling/src/otsafety_tooling/tracking.py
"""Experiments record themselves through a port, never through a vendor.

    with track("baseline", tracker, root=REPO_ROOT, seeds={"python": 7},
               dataset="opentargets-26.03", dataset_digest=DIGEST) as run:
        run.param("alpha", 1.0)
        run.metric("average_precision", ap)
        run.artifact("model.pt", path)

WHY A PORT AND NOT `import mlflow`. experiment-run/v1 exists because trackers
log only what they are told; this exists so no experiment can reach past the
contract. MLflow and Weights & Biases are adapters behind it, and
default_tracker() composes them, so an experiment never chooses its backends --
choosing was how W&B became a flag somebody had to remember in an earlier
project, and a forgotten flag records nothing.

THE ENVIRONMENT IS GATHERED, NOT DECLARED. The commit, whether the tree was
clean, the Python version and the installed package versions come from the
running process. An experiment cannot forget them, and cannot claim a clean
tree it does not have.

RECORDED EVEN WHEN IT FAILS. The record is written in a finally block, with the
exception's type as error_type, and the exception still propagates. A failure
that leaves no evidence is how tracking quietly stops being trusted.

ARTIFACTS ARE HASHED WHEN DECLARED, and a missing file raises rather than being
recorded as absent: a record naming an artifact that was never written is worse
than no record at all.
"""

from __future__ import annotations

import hashlib
import platform
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import distributions
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.contracts.experiment_run import ExperimentRun
from otsafety_tooling.git.env import git
from otsafety_tooling.runs import machine_id

UNKNOWN_COMMIT = "0" * 40


class Environment(BaseModel):
    """The facts about this process that make a run reproducible."""

    model_config = ConfigDict(frozen=True)

    commit: str
    working_tree_clean: bool
    python_version: str
    packages: dict[str, str]
    machine: str


def gather_environment(root: Path) -> Environment:
    """Read the reproducibility facts from the running process."""
    revision = git("rev-parse", "HEAD", cwd=root)
    commit = revision.stdout.strip() if revision.returncode == 0 else UNKNOWN_COMMIT

    status = git("status", "--porcelain", cwd=root)
    clean = status.returncode == 0 and not status.stdout.strip()

    packages = {
        name: version
        for distribution in distributions()
        if (name := distribution.metadata["Name"]) and (version := distribution.version)
    }
    return Environment(
        commit=commit,
        working_tree_clean=clean,
        python_version=platform.python_version(),
        packages=packages,
        machine=machine_id(),
    )


class Tracker(Protocol):
    """Everything an experiment needs from a tracking backend."""

    def record(self, run: ExperimentRun) -> None: ...


class MemoryTracker:
    """Keeps runs in memory: for tests, and for running with no backend."""

    def __init__(self) -> None:
        self.runs: list[ExperimentRun] = []

    def record(self, run: ExperimentRun) -> None:
        self.runs.append(run)


class FileTracker:
    """Writes each run as experiment-run/v1 JSON, named after the run."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def record(self, run: ExperimentRun) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = run.started_at.strftime("%Y%m%dT%H%M%S%fZ")
        path = self.directory / f"{stamp}-{run.experiment}-{run.id}.json"
        path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")


class FanOutTracker:
    """One run, several backends: file and MLflow and W&B, composed."""

    def __init__(self, *trackers: Tracker) -> None:
        self.trackers = trackers

    def record(self, run: ExperimentRun) -> None:
        for tracker in self.trackers:
            tracker.record(run)


def default_tracker(
    directory: Path | None = None,
    backends: tuple[str, ...] = ("mlflow", "wandb"),
) -> FanOutTracker:
    """The trackers every experiment records to, composed in one place.

    THE FILE TRACKER IS NOT OPTIONAL. It is the copy that outlives a vendor, an
    expired account or a deleted project, and it is what the site reads.

    EACH BACKEND IS ADDED WHEN ITS EXTRA IS INSTALLED, and simply absent
    otherwise -- that is what optional means. It is NOT skipped for any other
    reason: a tracker that quietly disables itself on a bad key or a missing
    entity is how tracking stops being trusted, so those failures stay loud.
    """
    import importlib.util

    from otsafety_tooling.artifacts import artifacts_root
    from otsafety_tooling.paths import REPO_ROOT

    records = directory if directory is not None else artifacts_root(REPO_ROOT) / "experiments"
    trackers: list[Tracker] = [FileTracker(records)]

    if "mlflow" in backends and importlib.util.find_spec("mlflow") is not None:
        from otsafety_tooling.tracking_mlflow import MlflowTracker

        trackers.append(MlflowTracker())

    if "wandb" in backends and importlib.util.find_spec("wandb") is not None:
        from otsafety_tooling.tracking_wandb import WandbTracker

        trackers.append(WandbTracker())

    return FanOutTracker(*trackers)


class RunBuilder:
    """What the body of an experiment writes to; it never builds the record."""

    def __init__(self) -> None:
        self.params: dict[str, float | int | bool | str] = {}
        self.metrics: dict[str, float] = {}
        self.artifacts: dict[str, str] = {}

    def param(self, name: str, value: float | int | bool | str) -> None:
        self.params[name] = value

    def metric(self, name: str, value: float) -> None:
        self.metrics[name] = value

    def artifact(self, name: str, path: Path) -> None:
        """Record an artifact by the digest of its bytes, hashed now."""
        if not path.is_file():
            raise FileNotFoundError(f"artifact {name} was declared but {path} does not exist")
        self.artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def track(
    experiment: str,
    tracker: Tracker,
    *,
    root: Path,
    seeds: Mapping[str, int],
    dataset: str,
    dataset_digest: str,
    deterministic: bool = True,
) -> Iterator[RunBuilder]:
    """Time an experiment, gather its environment, and record it either way."""
    builder = RunBuilder()
    environment = gather_environment(root)
    started_at = datetime.now(UTC)
    run_id = uuid.uuid4().hex[:12]
    error_type: str | None = None
    try:
        yield builder
    except BaseException as error:
        error_type = type(error).__name__
        raise
    finally:
        ended_at = datetime.now(UTC)
        tracker.record(
            ExperimentRun(
                id=run_id,
                experiment=experiment,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=round((ended_at - started_at).total_seconds() * 1000),
                status="failed" if error_type else "completed",
                error_type=error_type,
                commit=environment.commit,
                working_tree_clean=environment.working_tree_clean,
                dataset=dataset,
                dataset_digest=dataset_digest,
                seeds=dict(seeds),
                deterministic=deterministic,
                python_version=environment.python_version,
                packages=environment.packages,
                params=builder.params,
                metrics=builder.metrics,
                artifacts=builder.artifacts,
                machine=environment.machine,
            )
        )
