# apps/site/tests/conftest.py
"""The built site, served for the duration of a test session.

THE FIXTURE MOVED HERE THE MOMENT A SECOND MODULE NEEDED IT. Importing it across
test modules is a relative import with no parent package, which pytest reports
as a collection error -- a broken test rather than a failing one, and a broken
test proves nothing about the thing under test.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SITE = REPO_ROOT / "apps" / "site"
BASE_URL = "http://localhost:4321"
MACHINE = "8f14e45f-ea8f-4b1a-9c3d-2b6b1a0f7e21"


def _seed_evidence(artifacts: Path) -> None:
    """One failing settings verdict and one failed run, built from the contracts.

    FROM THE PYDANTIC MODELS, NEVER AS DICTS. These fixtures were once written to
    match the site's hand-written TypeScript type instead of the contract, so the
    tests passed against fields -- recorded_at, rule, detail -- that no producer
    writes, while production rendered real records as blanks. The run fixture was
    even invalid: a failure with no error_type. Constructing the models means a
    fixture the producer could not write cannot exist.

    The settings verdict FAILS on purpose: a page that can only render a pass
    cannot be trusted when it shows one.
    """
    from datetime import UTC, datetime

    from otsafety_tooling.contracts.repository_settings import (
        SettingFinding,
        SettingsCheckReport,
    )
    from otsafety_tooling.contracts.run_record import RunRecord

    at = datetime(2026, 1, 1, tzinfo=UTC)
    records = {
        "repo-settings": SettingsCheckReport(
            generated_at=at,
            repository="otsafety-gnn",
            verdict="fail",
            findings=(
                SettingFinding(
                    rule_id="S001",
                    reason_code="SETTING_DIFFERS",
                    message="allow_squash_merge is True but the policy requires False",
                    setting="allow_squash_merge",
                    expected=False,
                    observed=True,
                ),
            ),
        ),
        "runs": RunRecord(
            id="000000000000",
            task="fixture",
            started_at=at,
            ended_at=at,
            duration_ms=0,
            exit_code=1,
            outcome="failure",
            error_type="ExitCode",
            repository="otsafety-gnn",
            branch="fixture",
            commit="0" * 40,
            machine=MACHINE,
            output_file="00000000T000000000000Z-fixture.log",
            output_bytes=0,
            output_sha256="0" * 64,
        ),
    }
    for kind, record in records.items():
        folder = artifacts / kind
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "00000000T000000000000Z-fixture.json").write_text(record.model_dump_json())


def _seed_experiments(artifacts: Path) -> None:
    """Experiment records covering every state the results page must render.

    SHAPED FROM A REAL RECORD. A probe ran track() through FileTracker and the
    page is designed against what it wrote: one seed per record, so a rung's five
    seeds are five files grouped by `experiment`, and every record carries the
    commit and dataset digest that make comparability checkable.

    INTO THE TEST'S OWN ROOT, UNCONDITIONALLY: the same data on every machine.
    """

    folder = artifacts / "experiments"
    folder.mkdir(parents=True, exist_ok=True)

    from otsafety_tooling.contracts.experiment_run import ExperimentRun

    def record(experiment: str, seed: int, ap: float, digest: str) -> ExperimentRun:
        return ExperimentRun.model_validate(
            {
                "contract": "experiment-run/v1",
                "id": f"{seed:012x}",
                "experiment": experiment,
                "started_at": "2026-09-21T00:00:00Z",
                "ended_at": "2026-09-21T00:00:01Z",
                "duration_ms": 1000,
                "status": "completed",
                "error_type": None,
                "commit": "0" * 40,
                "working_tree_clean": True,
                "dataset": "opentargets-26.03",
                "dataset_digest": digest,
                "seeds": {"python": seed},
                "deterministic": True,
                "python_version": "3.13.15",
                "packages": {"x": "1"},
                "params": {},
                "metrics": {"average_precision": ap},
                "artifacts": {},
                "machine": MACHINE,
            }
        )

    same = "a" * 64
    rows = [("degree-null", s, 0.30 + 0.01 * s, same) for s in range(1, 6)]
    rows.append(("relation-aware", 1, 0.44, same))  # one seed only
    rows.append(("relation-agnostic", 1, 0.40, "c" * 64))  # different data
    for experiment, seed, ap, digest in rows:
        path = folder / f"20260921T000000{seed:06d}Z-{experiment}-{seed:012x}.json"
        path.write_text(record(experiment, seed, ap, digest).model_dump_json())


@pytest.fixture(scope="session")
def site_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Build the site against a disposable evidence root, and serve it.

    THE REAL .artifacts/ IS NEVER READ OR WRITTEN HERE. OTSAFETY_ARTIFACTS points
    the build at a session temp directory the seeders fill, so the tests are
    hermetic and cannot plant fixtures among real evidence.
    """
    artifacts = tmp_path_factory.mktemp("artifacts")
    _seed_evidence(artifacts)
    _seed_experiments(artifacts)
    env = {**os.environ, "OTSAFETY_ARTIFACTS": str(artifacts)}
    if not (SITE / "package.json").is_file():
        pytest.fail(f"no site at {SITE}: run `mise run site:install` after scaffolding")

    subprocess.run(["bun", "run", "build"], cwd=SITE, check=True, env=env)  # noqa: S603, S607
    proc = subprocess.Popen(  # noqa: S603, S607
        ["bun", "run", "preview", "--port", "4321"], cwd=SITE, env=env
    )
    try:
        for _ in range(60):
            if proc.poll() is not None:
                pytest.fail("the preview server exited before it served anything")
            try:
                import urllib.request

                urllib.request.urlopen(BASE_URL, timeout=1)  # noqa: S310
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            pytest.fail(f"the preview server never answered on {BASE_URL}")
        yield BASE_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)
