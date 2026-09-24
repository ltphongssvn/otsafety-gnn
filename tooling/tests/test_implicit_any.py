# tooling/tests/test_implicit_any.py
"""The ban on Any cannot be reopened, and the implicit forms are caught (G.46).

WHAT THIS PROVES. mypy's disallow_any_explicit sees the word Any and nothing else.
Two shapes mean the same thing and pass it -- Callable[..., X] elides its
parameters, a bare container elides its members -- and ruff's ANN401 checks only a
function argument. Sixty-one explicit sites accumulated behind a module-wide
exemption that carried no count, so nobody had to look at what it permitted.

THE PROOF IS BEHAVIOURAL, NOT THE IMPLEMENTATION. Naming the scan module as this
requirement's evidence left it permanently unconfirmed: G.41 settled that a Python
file is confirmed by a test claiming the id, and a module that is not a test can
never do that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.pyproject_config import WorkspacePyproject
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.annotations import implicit_any

pytestmark = pytest.mark.requirement("G.46")


def test_the_repository_elides_no_type_it_could_name() -> None:
    assert implicit_any(REPO_ROOT) == []


def test_the_scan_sees_an_elided_parameter_list(tmp_path: Path) -> None:
    """The form that hid in two seams until a type error exposed it."""
    (tmp_path / "tooling" / "src").mkdir(parents=True)
    (tmp_path / "tooling" / "src" / "seam.py").write_text(
        "from collections.abc import Callable\n\n\ndef f(run: Callable[..., int]) -> None: ...\n",
        encoding="utf-8",
    )
    for other in ("tooling/tests", "scripts", "apps/site/tests"):
        (tmp_path / other).mkdir(parents=True)
    found = implicit_any(tmp_path)
    assert len(found) == 1 and "elides its parameters" in found[0]


def test_the_scan_sees_a_bare_container(tmp_path: Path) -> None:
    for where in ("tooling/src", "tooling/tests", "scripts", "apps/site/tests"):
        (tmp_path / where).mkdir(parents=True)
    (tmp_path / "scripts" / "loose.py").write_text(
        "def f(rows: dict) -> None: ...\n", encoding="utf-8"
    )
    found = implicit_any(tmp_path)
    assert len(found) == 1 and "elides its members" in found[0]


def test_no_override_may_reopen_the_ban() -> None:
    """THE HABIT, NOT THE INSTANCE: an exemption with no count permits whatever
    anyone writes next, and nobody has to look."""
    for relative in ("pyproject.toml", "tooling/pyproject.toml"):
        section = read_toml(REPO_ROOT / relative, WorkspacePyproject).tool.mypy
        if section is None:
            continue
        for override in section.overrides:
            assert override.disallow_any_explicit is not False, (
                f"{relative} exempts {override.module} from the ban"
            )
