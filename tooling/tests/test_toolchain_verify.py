# tooling/tests/test_toolchain_verify.py
"""Every task runs the pinned binary of each tool, and an impostor is refused.

The fakes prove each refusal by its reason: one reports the right version from
the wrong place, one sits in the bootstrap's place but reports the wrong version.
PATH comes from the sanctioned scrubbed_env(), since tests may not read os.environ.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.mise_config import MiseTask
from otsafety_tooling.contracts.toolchain import Toolchain
from otsafety_tooling.git.env import scrubbed_env
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.toolchain_verify import problems

CHAIN = read_json(REPO_ROOT / "toolchain.json", Toolchain)


def _fake(directory: Path, name: str, output: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(f"#!/bin/sh\necho '{output}'\n", encoding="utf-8")
    (directory / name).chmod(0o755)


def test_this_environment_runs_the_pinned_tools() -> None:
    assert problems(CHAIN) == []


def test_the_right_version_from_the_wrong_place_is_refused(tmp_path: Path) -> None:
    _fake(tmp_path, "regal", f"Version:       {CHAIN.regal.version}")
    found = problems(CHAIN, path=f"{tmp_path}:{scrubbed_env()['PATH']}")
    assert any(p.startswith("regal:") and "is not the pinned" in p for p in found), found


def test_the_wrong_version_from_the_right_place_is_refused(tmp_path: Path) -> None:
    _fake(tmp_path, "regal", "Version:       0.0.1")
    found = problems(CHAIN, path=f"{tmp_path}:{scrubbed_env()['PATH']}", bootstrap=tmp_path)
    assert any(p.startswith("regal:") and "not " + CHAIN.regal.version in p for p in found), found


def test_a_task_cannot_leave_the_pinned_shell() -> None:
    """Only task_config, and mise.ood.toml's overlay, may set a shell."""
    with pytest.raises(ValidationError):
        MiseTask.model_validate({"description": "x", "run": "true", "shell": "bash -c"})
