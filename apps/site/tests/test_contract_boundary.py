# apps/site/tests/test_contract_boundary.py
"""A record that does not match its contract fails the build.

The evidence page has said so since it was written, while every file was cast
with `as T`, which checks nothing. This proves the claim from the failing side:
a gate only ever seen passing is not a gate.

THE RECORD IS THE ONE THAT DRIFTED. It is the shape the old fixture wrote --
recorded_at, rule, code, detail -- matching the site's hand-written type rather
than the contract. Production rendered such fields as blanks. Now the build
refuses it, naming the file.

--outDir keeps this build out of the dist/ the shared preview server serves.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from otsafety_tooling.git.env import scrubbed_env

SITE = Path(__file__).resolve().parents[1]

DRIFTED_SETTINGS = {
    "contract": "repository-settings-check/v1",
    "verdict": "fail",
    "repository": "otsafety-gnn",
    "recorded_at": "2026-01-01T00:00:00Z",
    "findings": [{"rule": "S001", "code": "SETTING_DIFFERS", "detail": "differs"}],
}


def test_the_drifted_shape_fails_the_build(tmp_path: Path) -> None:
    folder = tmp_path / "artifacts" / "repo-settings"
    folder.mkdir(parents=True)
    (folder / "drifted.json").write_text(json.dumps(DRIFTED_SETTINGS))

    built = subprocess.run(  # noqa: S603
        ["bun", "x", "astro", "build", "--outDir", str(tmp_path / "dist")],  # noqa: S607
        cwd=SITE,
        env={**scrubbed_env(), "OTSAFETY_ARTIFACTS": str(tmp_path / "artifacts")},
        capture_output=True,
        text=True,
        check=False,
    )
    output = built.stdout + built.stderr
    assert built.returncode != 0, "a record off its contract was published"
    assert "drifted.json" in output, "the failure must name the file"
    assert "does not match its contract" in output


def test_the_committed_zod_is_what_the_schemas_generate(tmp_path: Path) -> None:
    """A hand-edited .gen.ts would pass every other test; this is its gate."""
    generated = subprocess.run(  # noqa: S603
        ["bun", "run", "scripts/generate-contracts.ts", str(tmp_path)],  # noqa: S607
        cwd=SITE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    committed = sorted((SITE / "src" / "contracts").glob("*.gen.ts"))
    assert committed, "no generated contracts are committed"
    for path in committed:
        fresh = (tmp_path / path.name).read_text(encoding="utf-8")
        assert path.read_text(encoding="utf-8") == fresh, (
            f"{path.name} differs from its schema; run mise run contracts:generate"
        )
