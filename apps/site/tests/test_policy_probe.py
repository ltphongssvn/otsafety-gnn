# apps/site/tests/test_policy_probe.py
"""The Rego proof denies each thing it guards when that thing is removed.

Each probe copies the real inputs into a temporary directory, removes exactly one
guarded thing, and requires Conftest to deny it by name. The unmodified copy must
pass, so a probe cannot succeed merely because the setup is broken.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from otsafety_tooling.contracts.eslint_config import EffectiveConfig
from otsafety_tooling.contracts.files import read_json

REPO = Path(__file__).resolve().parents[3]
INPUTS = [
    "pyproject.toml",
    "tooling/pyproject.toml",
    "lefthook.yml",
    ".github/workflows/test-site.yml",
    ".github/workflows/test-tooling.yml",
    ".github/workflows/zizmor.yml",
    "context/exemptions.yaml",
]


def _conftest() -> str:
    found = shutil.which("conftest")
    assert found is not None, "conftest is not on PATH; the toolchain installs it"
    return found


def _world(tmp_path: Path) -> Path:
    for rel in INPUTS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, tmp_path / rel)
    out = tmp_path / "policy" / "eslint-effective.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "bun",
            "--bun",
            "run",
            "--cwd",
            str(REPO / "apps" / "site"),
            "scripts/eslint-effective.ts",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return tmp_path


def _prove(world: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _conftest(),
            "test",
            "--combine",
            "--namespace",
            "policy",
            "--policy",
            str(REPO / "policy"),
            *INPUTS,
            "policy/eslint-effective.json",
        ],
        cwd=world,
        capture_output=True,
        text=True,
        check=False,
    )


def _remove(world: Path, rel: str, old: str, new: str = "") -> None:
    path = world / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{rel}: the probe's anchor was not found exactly once"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_the_real_configuration_passes(tmp_path: Path) -> None:
    run = _prove(_world(tmp_path))
    assert run.returncode == 0, run.stdout


def test_removing_a_ban_is_denied(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _remove(world, "pyproject.toml", ', "RUF100", "ANN401"]', ', "RUF100"]')
    run = _prove(world)
    assert run.returncode != 0 and "ruff must select ANN401" in run.stdout, run.stdout


def test_removing_a_floor_is_denied(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _remove(world, "lefthook.yml", "      run: mise run site:lint\n", "      run: echo skipped\n")
    run = _prove(world)
    assert run.returncode != 0 and "pre-commit must run mise run site:lint" in run.stdout, (
        run.stdout
    )


def test_an_undeclared_eslint_exemption_is_denied(tmp_path: Path) -> None:
    """A protected rule relaxed for one file, with no register entry, is denied by name."""
    world = _world(tmp_path)
    path = world / "policy" / "eslint-effective.json"
    effective = read_json(path, EffectiveConfig)
    target = "apps/site/src/data/evidence.ts"
    file = effective.files[target]
    relaxed = file.rules["no-restricted-syntax"].model_copy(update={"severity": "off"})
    rules = {**file.rules, "no-restricted-syntax": relaxed}
    files = {**effective.files, target: file.model_copy(update={"rules": rules})}
    path.write_text(
        effective.model_copy(update={"files": files}).model_dump_json(indent=2), encoding="utf-8"
    )
    run = _prove(world)
    assert run.returncode != 0 and "evidence.ts: not enforced" in run.stdout, run.stdout
