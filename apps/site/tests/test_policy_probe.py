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

from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.policy_inputs import PolicyInput, PolicyInputs

REPO = Path(__file__).resolve().parents[3]
INPUTS_MANIFEST = REPO / "contracts" / "policy-inputs.json"


def _conftest() -> str:
    found = shutil.which("conftest")
    assert found is not None, "conftest is not on PATH; the toolchain installs it"
    return found


def _declared() -> tuple[PolicyInput, ...]:
    """The input set, read through its contract from the file the task reads.

    NOT A SECOND LIST. This probe kept its own, so adding an input to the policy
    left it judging a smaller world than the real run -- the divergence a single
    declared set removes.
    """
    return read_json(INPUTS_MANIFEST, PolicyInputs).inputs


def _world(tmp_path: Path) -> Path:
    for entry in _declared():
        if entry.generated:
            continue
        (tmp_path / entry.path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / entry.path, tmp_path / entry.path)
    for entry in _declared():
        if not entry.generated:
            continue
        target = tmp_path / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [*entry.generated.split(), str(target)],
            cwd=REPO,
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
            *[entry.path for entry in _declared()],
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
    world = _world(tmp_path)
    text = (world / "context" / "exemptions.yaml").read_text(encoding="utf-8")
    (world / "context" / "exemptions.yaml").write_text(
        text.split("\neslint:\n")[0] + "\n", encoding="utf-8"
    )
    run = _prove(world)
    assert run.returncode != 0 and "generate-contracts.ts: not enforced" in run.stdout, run.stdout
