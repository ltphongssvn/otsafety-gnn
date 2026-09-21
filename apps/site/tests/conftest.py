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
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SITE = REPO_ROOT / "apps" / "site"
BASE_URL = "http://localhost:4321"


def _seed_evidence(artifacts: Path) -> None:
    """Guarantee one failing verdict and one run record exist before the build.

    WRITTEN INTO THE TEST'S OWN ROOT, ALWAYS. An earlier version wrote into the
    real .artifacts/ and only when a folder was empty, which was wrong twice: it
    could plant fixtures among real evidence, and it made the tests depend on the
    machine -- fixtures on CI, whatever happened to exist on a laptop.

    The settings fixture is a FAILING verdict on purpose. The first real check
    found three S001 differences and recorded them before the fix; a page that
    can only render a pass cannot be trusted when it shows one.
    """
    import json

    seeds = {
        "repo-settings": {
            "contract": "repository-settings-check/v1",
            "verdict": "fail",
            "repository": "otsafety-gnn",
            "recorded_at": "2026-01-01T00:00:00Z",
            "findings": [
                {
                    "rule": "S001",
                    "code": "SETTING_DIFFERS",
                    "detail": "allow_squash_merge is True but the policy requires False",
                }
            ],
        },
        "runs": {
            "contract": "run-record/v1",
            "id": "000000000000",
            "task": "fixture",
            "arguments": [],
            "started_at": "2026-01-01T00:00:00Z",
            "duration_ms": 0,
            "exit_code": 1,
            "outcome": "failure",
            "repository": "otsafety-gnn",
            "branch": "fixture",
            "commit": "0" * 40,
            "output_bytes": 0,
            "output_sha256": "0" * 64,
            "truncated": False,
        },
    }
    for kind, record in seeds.items():
        folder = artifacts / kind
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "00000000T000000000000Z-fixture.json").write_text(json.dumps(record))


def _seed_experiments(artifacts: Path) -> None:
    """Experiment records covering every state the results page must render.

    SHAPED FROM A REAL RECORD. A probe ran track() through FileTracker and the
    page is designed against what it wrote: one seed per record, so a rung's five
    seeds are five files grouped by `experiment`, and every record carries the
    commit and dataset digest that make comparability checkable.

    INTO THE TEST'S OWN ROOT, UNCONDITIONALLY: the same data on every machine.
    """
    import json

    folder = artifacts / "experiments"
    folder.mkdir(parents=True, exist_ok=True)

    def record(experiment: str, seed: int, ap: float, digest: str) -> dict[str, Any]:
        return {
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
            "machine": "8f14e45f-ea8f-4b1a-9c3d-2b6b1a0f7e21",
        }

    same = "a" * 64
    rows = [("degree-null", s, 0.30 + 0.01 * s, same) for s in range(1, 6)]
    rows.append(("relation-aware", 1, 0.44, same))  # one seed only
    rows.append(("relation-agnostic", 1, 0.40, "c" * 64))  # different data
    for experiment, seed, ap, digest in rows:
        path = folder / f"20260921T000000{seed:06d}Z-{experiment}-{seed:012x}.json"
        path.write_text(json.dumps(record(experiment, seed, ap, digest)))


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
