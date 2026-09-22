# tooling/tests/test_python_version.py
"""Ruff is configured once, and every declaration names the same Python.

WHY THIS EXISTS. Two ruff configurations kept one policy by hand, with identical
banned-api tables, because Ruff does not merge configuration files: the closest
one wins outright. Merging them into the root exposed a second fault. Ruff infers
its target from requires-python beside its configuration, and the virtual
workspace root has none, so it fell back to Python 3.9 and re-sorted tomllib out
of the standard library in 43 files. The interpreter pin, the package's range
and Ruff's target are three facts about one version; nothing checked they agree.
"""

from __future__ import annotations

import re
import subprocess

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.pyproject_config import WorkspacePyproject
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.markdown import tracked


def _minor(text: str) -> str:
    found = re.search(r"(\d+)\.?(\d+)", text.replace("py3", "3."))
    assert found, f"no Python version in {text!r}"
    return f"{found.group(1)}.{found.group(2)}"


def test_ruff_is_configured_exactly_once() -> None:
    files = tracked(REPO_ROOT)
    assert not [f for f in files if f.endswith(("ruff.toml", ".ruff.toml"))], (
        "a ruff.toml would be a second policy"
    )
    configured = [
        f
        for f in files
        if f.endswith("pyproject.toml")
        and read_toml(REPO_ROOT / f, WorkspacePyproject).tool.ruff is not None
    ]
    assert configured == ["pyproject.toml"]


def test_every_declaration_names_the_same_python() -> None:
    pinned = _minor((REPO_ROOT / ".python-version").read_text(encoding="utf-8"))
    package = read_toml(REPO_ROOT / "tooling" / "pyproject.toml", WorkspacePyproject).project
    ruff = read_toml(REPO_ROOT / "pyproject.toml", WorkspacePyproject).tool.ruff
    assert package is not None and package.requires_python is not None
    assert ruff is not None and ruff.target_version is not None, (
        "Ruff would fall back to its default Python"
    )
    assert {pinned, _minor(package.requires_python), _minor(ruff.target_version)} == {pinned}


def test_ruff_resolves_the_declared_python() -> None:
    """Behaviour, not configuration text: what Ruff actually uses for a tooling file."""
    shown = subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            "--show-settings",
            "tooling/src/otsafety_tooling/contracts/files.py",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    ).stdout
    target = re.search(r"linter\.unresolved_target_version = (\S+)", shown)
    assert target and target.group(1) == _minor(
        (REPO_ROOT / ".python-version").read_text(encoding="utf-8")
    )


def test_first_party_sources_mirror_the_workspace() -> None:
    """Ruff does not read uv workspace members, so its src must list each, and each src/."""
    root = read_toml(REPO_ROOT / "pyproject.toml", WorkspacePyproject)
    assert (
        root.tool.ruff is not None
        and root.tool.uv is not None
        and root.tool.uv.workspace is not None
    )
    members = root.tool.uv.workspace.members
    assert members, "no workspace members; the mirror would pass vacuously"
    missing = [p for m in members for p in (m, f"{m}/src") if p not in root.tool.ruff.src]
    assert missing == []
