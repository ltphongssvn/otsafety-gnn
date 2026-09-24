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

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.pyproject_config import WorkspacePyproject
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.annotations import implicit_any

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
    """THE PROBE NAMES THE CONFIGURATION, because mypy does not merge or inherit:
    its documentation says so outright. Run from tooling/ without --config-file it
    reads no policy at all, which is how this test caught the settings being moved
    to the root and the tooling silently disarmed."""
    probe = "from typing import Any\n\nvalue: dict[str, Any] = {}\n"
    run = _run("uv", "run", "mypy", "--config-file", str(REPO_ROOT / "pyproject.toml"), "-c", probe)
    assert run.returncode != 0 and "explicit-any" in run.stdout, run.stdout + run.stderr


def test_a_model_class_is_not_reported() -> None:
    """The plugin types the synthesised constructor, so a model is not an explicit Any."""
    probe = "from pydantic import BaseModel\n\n\nclass M(BaseModel):\n    a: int\n\n\nM(a=1)\n"
    run = _run("uv", "run", "--directory", "tooling", "mypy", "-c", probe)
    assert run.returncode == 0, run.stdout + run.stderr


IMPLICIT = (
    ("Callable[..., X]", "Callable[..., int]"),
    ("a bare container", "def f(x: dict) -> None: ..."),
)


def test_no_override_may_reopen_the_ban() -> None:
    """THE HABIT THAT LET SIXTY-ONE ACCUMULATE: a module-wide override with no
    count and no expiry, which permits whatever anyone writes next. The override
    is gone; this refuses a new one rather than trusting that it stays gone."""
    for relative in ("pyproject.toml", "tooling/pyproject.toml"):
        section = read_toml(REPO_ROOT / relative, WorkspacePyproject).tool.mypy
        if section is None:
            continue
        for override in section.overrides:
            assert override.disallow_any_explicit is not False, (
                f"{relative} exempts {override.module} from the ban on explicit Any"
            )


def test_the_annotation_rules_cover_every_python_surface() -> None:
    """ANN401 catches Any in an ARGUMENT, and nothing else. The rest of the family
    catches the missing annotations that leave a parameter implicitly untyped."""
    ruff = read_toml(REPO_ROOT / "pyproject.toml", WorkspacePyproject).tool.ruff
    assert ruff is not None and ruff.lint is not None
    for rule in ("ANN001", "ANN002", "ANN003", "ANN201", "ANN202", "ANN204"):
        assert rule in ruff.lint.select, f"ruff must select {rule}"


def test_no_source_elides_a_type_it_could_name() -> None:
    """IMPLICIT Any IS STILL Any. Callable[..., X] elides its parameters and a bare
    dict annotation elides its members; mypy's disallow_any_explicit sees neither,
    and one of these hid in this repository until a type error exposed it."""
    offenders = implicit_any(REPO_ROOT)
    assert offenders == [], f"these elide a type they could name: {offenders}"
