# tooling/tests/test_no_any.py
"""No Any: bare in a signature, refused by ruff; anywhere else, refused by mypy.

Both layers are tested by what they do, not by strings in their configuration,
as the environment ban is. mypy's layer became possible only with Pydantic's
plugin set to type the constructor it synthesises: without init_typed and
init_forbid_extra, every model class read as an explicit Any, 157 times here.
"""

from __future__ import annotations

import subprocess

import pytest

from otsafety_tooling.paths import REPO_ROOT

# THIS FILE PROVES G.25: the claim the requirement matrix joins on.
pytestmark = pytest.mark.requirement("G.25")


def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), input=stdin, capture_output=True, text=True, cwd=REPO_ROOT, check=False
    )


def test_ruff_refuses_any_in_a_signature() -> None:
    probe = "from typing import Any\n\n\ndef f(x: Any) -> None:\n    pass\n"
    run = _run(
        "uv",
        "run",
        "ruff",
        "check",
        "--stdin-filename",
        "tooling/src/otsafety_tooling/probe.py",
        "-",
        stdin=probe,
    )
    assert run.returncode != 0 and "ANN401" in run.stdout, run.stdout + run.stderr


def test_mypy_refuses_any_anywhere() -> None:
    probe = "from typing import Any\n\nvalue: dict[str, Any] = {}\n"
    run = _run("uv", "run", "--directory", "tooling", "mypy", "-c", probe)
    assert run.returncode != 0 and "explicit-any" in run.stdout, run.stdout + run.stderr


def test_a_model_class_is_not_reported() -> None:
    """The plugin types the synthesised constructor, so a model is not an explicit Any."""
    probe = "from pydantic import BaseModel\n\n\nclass M(BaseModel):\n    a: int\n\n\nM(a=1)\n"
    run = _run("uv", "run", "--directory", "tooling", "mypy", "-c", probe)
    assert run.returncode == 0, run.stdout + run.stderr
