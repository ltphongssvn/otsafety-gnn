# tooling/src/otsafety_tooling/tracking_mlflow.py
"""MLflow, as an adapter behind the tracking port.

NOTHING IMPORTS THIS EXCEPT THE COMPOSITION ROOT. An experiment depends on the
port, so adding or dropping MLflow changes no training code:

    tracker = FanOutTracker(FileTracker(records), MlflowTracker())

MLFLOW IS IMPORTED INSIDE THE METHOD, not at module scope, so
otsafety_tooling.tracking loads on a machine that installed only the git tasks --
FAS OnDemand pulling and syncing has no reason to carry a large ML dependency.
It comes from the `ml` extra: uv sync --extra ml.

A LOCAL SQLITE STORE BY DEFAULT: no server, works offline, works on a cluster,
and it is one file inside the evidence root. NOT THE FILE STORE: MLflow 3.16
refuses ./mlruns outright, calling it maintenance mode with no further updates
and pointing at a database backend. Keeping it behind MLFLOW_ALLOW_FILE_STORE
would be adopting something its own maintainers have stopped developing.

THE TIMES ARE THE EXPERIMENT'S OWN. MLflow would otherwise stamp the moment of
recording, which is the duration of writing a record rather than of the run.

THE RECORD IS ATTACHED AS AN ARTIFACT, so MLflow is never the only copy of what
happened: the same experiment-run/v1 document the file tracker writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.contracts.experiment_run import ExperimentRun
from otsafety_tooling.paths import REPO_ROOT

RECORD_FILENAME = "experiment-run.json"

# MLflow's terminal states; the contract has two outcomes and these are their names.
FINISHED = "FINISHED"
FAILED = "FAILED"


def default_store() -> Path:
    """Where runs are kept: one SQLite file under the clone's evidence root."""
    return artifacts_root(REPO_ROOT) / "mlflow" / "runs.db"


def tracking_uri(store: Path) -> str:
    """The MLflow tracking URI for a SQLite file, created if absent."""
    store.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{store}"


class MlflowTracker:
    """Records an experiment run into MLflow, without any experiment knowing."""

    def __init__(self, store: Path | None = None) -> None:
        self.store = store if store is not None else default_store()

    def record(self, run: ExperimentRun) -> None:
        """Create one MLflow run carrying this record, and attach the record."""
        import mlflow

        mlflow.set_tracking_uri(tracking_uri(self.store))

        client = mlflow.tracking.MlflowClient()
        experiment = client.get_experiment_by_name(run.experiment)
        experiment_id = (
            experiment.experiment_id
            if experiment is not None
            else client.create_experiment(run.experiment)
        )

        created = client.create_run(
            experiment_id=experiment_id,
            start_time=int(run.started_at.timestamp() * 1000),
            tags=self._tags(run),
        )
        run_id = created.info.run_id

        for name, value in run.params.items():
            client.log_param(run_id, name, value)
        for name, measurement in run.metrics.items():
            client.log_metric(run_id, name, measurement)

        self._attach_record(client, run_id, run)

        client.set_terminated(
            run_id,
            status=FINISHED if run.status == "completed" else FAILED,
            end_time=int(run.ended_at.timestamp() * 1000),
        )

    @staticmethod
    def _tags(run: ExperimentRun) -> dict[str, str]:
        """The reproducibility facts, so MLflow can answer what produced a number."""
        tags = {
            "contract": run.contract,
            "run_id": run.id,
            "commit": run.commit,
            "working_tree_clean": str(run.working_tree_clean),
            "dataset": run.dataset,
            "dataset_digest": run.dataset_digest,
            "deterministic": str(run.deterministic),
            "reproducible": str(run.is_reproducible),
            "python_version": run.python_version,
            "machine": run.machine,
            "seeds": json.dumps(run.seeds, sort_keys=True),
            "artifact_digests": json.dumps(run.artifacts, sort_keys=True),
        }
        if run.error_type is not None:
            tags["error_type"] = run.error_type
        return tags

    def _attach_record(self, client: object, run_id: str, run: ExperimentRun) -> None:
        """Attach the experiment-run/v1 document itself."""
        import tempfile

        with tempfile.TemporaryDirectory() as work:
            document = Path(work) / RECORD_FILENAME
            document.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
            client.log_artifact(run_id, str(document))  # type: ignore[attr-defined]
