# tooling/src/otsafety_tooling/tracking_wandb.py
"""Weights & Biases, as an adapter behind the tracking port -- beside MLflow.

FIRST-CLASS FROM DAY ONE. cs1090a-recsys reserved a slot for W&B and never
filled it; "a composition rather than a rewrite" is how it stayed unimplemented.
This adapter ships with MLflow, is held to the same tests, and sits in the
default composition:

    tracker = FanOutTracker(FileTracker(records), MlflowTracker(), WandbTracker())

THE MODE IS NEVER DECIDED HERE. 2026 guidance is plain: the mode is a runtime
concern set by the environment, not an algorithm detail set in code. WANDB_MODE,
WANDB_PROJECT and WANDB_DIR are declared once in mise.toml; this adapter passes
none of them, so offline on the laptop and CI, online on Lightning AI, and
disabled anywhere are all a change of environment rather than of code.

AN INITIALISATION FAILURE IS NOT CAUGHT. Online with no WANDB_API_KEY, wandb.init
raises in a headless environment. That is loud and correct. A tracker that
catches it and carries on is how "first-class" quietly becomes "absent".

W&B IS IMPORTED INSIDE THE METHOD, as MLflow is, so otsafety_tooling.tracking
loads on a machine that installed only the git tasks. It comes from the `wandb`
extra: mise run wandb:install.

THE TIMES ARE THE EXPERIMENT'S OWN, RECORDED EXPLICITLY. MLflow accepts a start
time; W&B cannot backdate a run, so its own timestamp would measure when the
record was written rather than when the experiment ran. started_at, ended_at and
duration_ms are therefore written into the config.

METRICS GO TO THE SUMMARY, NOT THE HISTORY. A recorded metric is a final value,
not a step in a curve.

THE RECORD IS ATTACHED TWICE, AS A FILE AND AS A VERSIONED ARTIFACT. The file
keeps W&B from being the only copy of what happened. The Artifact is what makes
it addressable: cs1090b-HallucinationLegalRAGChatbots uploaded its reports that
way and could then refer to one as name:version and consume it from a later run,
where a file in a run directory is neither versioned nor addressable. Its
metadata repeats the identifying facts, so an artifact found on its own still
says which code and which data produced it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.contracts.experiment_run import ExperimentRun
from otsafety_tooling.contracts.settings import settings
from otsafety_tooling.paths import REPO_ROOT

RECORD_FILENAME = "experiment-run.json"

# The artifact's type, so every experiment record is one collection in W&B.
ARTIFACT_TYPE = "experiment-run"

# Keys the adapter itself writes into the config. A parameter with one of these
# names would silently overwrite a reproducibility fact, so it is refused.

if TYPE_CHECKING:
    # W&B ships py.typed: its own types check every call here. Imported at run
    # time only inside the methods, since it stays an optional dependency.
    import wandb

RESERVED = frozenset(
    {
        "contract",
        "run_id",
        "status",
        "error_type",
        "commit",
        "working_tree_clean",
        "dataset",
        "dataset_digest",
        "deterministic",
        "reproducible",
        "python_version",
        "machine",
        "seeds",
        "artifact_digests",
        "started_at",
        "ended_at",
        "duration_ms",
    }
)


class _Summary(Protocol):
    """The run summary this adapter writes, typed where wandb ships no py.typed."""

    def update(self, values: dict[str, object]) -> None: ...


class _Artifact(Protocol):
    """What this adapter builds and attaches: the fields it sets, and add_file."""

    @property
    def name(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def metadata(self) -> dict[str, object]: ...

    def add_file(self, local_path: str, name: str | None = None) -> object: ...


class _Run(Protocol):
    """WHAT THIS ADAPTER NEEDS FROM A W&B RUN, and nothing else.

    THE SAME TREATMENT MLFLOW'S ADAPTER ALREADY HAS, applied here: wandb ships no
    py.typed, so every call through it went unchecked and its test carried
    fourteen explicit Any to describe a surface nobody had typed. A protocol the
    repository owns inverts that -- the real wandb run satisfies it structurally,
    and a test double implements it with no Any on either side.
    """

    @property
    def summary(self) -> _Summary: ...

    @property
    def dir(self) -> str: ...

    def log_artifact(self, artifact: _Artifact) -> object: ...

    def finish(self, exit_code: int = 0) -> None: ...


def default_directory() -> Path | None:
    """Where runs land: WANDB_DIR if the environment chose one, else the evidence root.

    LOCATION IS A CORRECTNESS PROPERTY, NOT A PREFERENCE. mise.toml's config_root
    is the worktree itself in a linked worktree, so runs written there would be
    deleted by `git worktree remove` -- the bug the evidence root exists to fix.
    MLflow's store resolves the same way. Mode is different: that stays wholly
    with the environment, and nothing here reads or sets it.
    """
    if settings().wandb_dir is not None:
        return None
    return artifacts_root(REPO_ROOT)


class WandbTracker:
    """Records an experiment run into Weights & Biases, without any experiment knowing."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else default_directory()

    def record(self, run: ExperimentRun) -> None:
        """Create one W&B run carrying this record, and attach the record."""
        import wandb

        clash = RESERVED & run.params.keys()
        if clash:
            raise ValueError(
                f"parameters {sorted(clash)} would overwrite reproducibility facts in "
                f"the W&B config; rename them"
            )

        # No mode, no project: both are environment. group gathers the seeds of one
        # experiment together, which is how the Results page reads them too.
        wb = wandb.init(
            name=run.id,
            group=run.experiment,
            job_type="experiment",
            dir=str(self.directory) if self.directory is not None else None,
            config={**run.params, **self._facts(run)},
        )
        try:
            wb.summary.update(dict(run.metrics))
            document = self._attach_record(Path(wb.dir), run)
            wb.log_artifact(self._artifact(run, document))
        finally:
            wb.finish(exit_code=0 if run.status == "completed" else 1)

    @staticmethod
    def _facts(run: ExperimentRun) -> dict[str, object]:
        """The reproducibility facts, so W&B can answer what produced a number."""
        return {
            "contract": run.contract,
            "run_id": run.id,
            "status": run.status,
            "error_type": run.error_type,
            "commit": run.commit,
            "working_tree_clean": run.working_tree_clean,
            "dataset": run.dataset,
            "dataset_digest": run.dataset_digest,
            "deterministic": run.deterministic,
            "reproducible": run.is_reproducible,
            "python_version": run.python_version,
            "machine": run.machine,
            "seeds": dict(run.seeds),
            "artifact_digests": dict(run.artifacts),
            "started_at": run.started_at.isoformat(),
            "ended_at": run.ended_at.isoformat(),
            "duration_ms": run.duration_ms,
        }

    @staticmethod
    def _attach_record(files: Path, run: ExperimentRun) -> Path:
        """Write the experiment-run/v1 document into the run's own files."""
        files.mkdir(parents=True, exist_ok=True)
        document = files / RECORD_FILENAME
        document.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return document

    @staticmethod
    def _artifact(run: ExperimentRun, document: Path) -> wandb.Artifact:
        """The record as a versioned artifact, addressable as name:version."""
        import wandb

        artifact = wandb.Artifact(
            name=f"{run.experiment}-{run.id}",
            type=ARTIFACT_TYPE,
            metadata={
                "contract": run.contract,
                "commit": run.commit,
                "dataset": run.dataset,
                "dataset_digest": run.dataset_digest,
                "reproducible": run.is_reproducible,
                "status": run.status,
            },
        )
        artifact.add_file(str(document), name=RECORD_FILENAME)
        return artifact
