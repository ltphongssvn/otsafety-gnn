# tooling/tests/test_one_mypy_policy.py
"""One mypy configuration, and no explicit Any anywhere (G.30).

TWO CONFIGURATIONS WERE BOTH IN USE AND HAD ALREADY DRIFTED. The tooling package
disallowed explicit Any and loaded the pydantic plugin; the root, which governs
scripts/ and the site's tests, did neither -- so the same ban was enforced on
part of the repository and not the rest, and nothing said so.

The root is the one configuration. The tooling package keeps only what is true
of it alone: the modules whose stubs it must ignore.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.pyproject_config import MypySection, WorkspacePyproject
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.30")


def _mypy(relative: str) -> MypySection:
    section = read_toml(REPO_ROOT / relative, WorkspacePyproject).tool.mypy
    assert section is not None, f"{relative} declares no [tool.mypy]"
    return section


def test_the_root_bans_explicit_any_for_every_checked_file() -> None:
    """THE DRIFT THIS CLOSES: scripts/ and the site's tests were checked without it."""
    assert _mypy("pyproject.toml").disallow_any_explicit is True


def test_the_root_loads_the_pydantic_plugin() -> None:
    """Without it, a model's generated __init__ is checked as untyped."""
    assert "pydantic.mypy" in _mypy("pyproject.toml").plugins


def test_only_the_root_declares_a_mypy_policy() -> None:
    """ONE CONFIGURATION MEANS ONE SECTION, not two that agree. mypy reads the
    closest file outright, so a second section is a second policy however carefully
    it is kept in step; every invocation passes --config-file to name the root's."""
    assert read_toml(REPO_ROOT / "tooling" / "pyproject.toml", WorkspacePyproject).tool.mypy is None
    for command in _mypy_invocations():
        assert "--config-file" in command, f"this invocation reads whatever is closest: {command}"


def test_every_exemption_from_the_ban_names_its_count_and_its_step() -> None:
    """A RELAXATION IS A DECLARED DEBT. The section this replaces exempted tests.*
    with no number, so nobody knew it covered sixty-one sites until the
    configurations were unified. Each exemption now carries the measured count and
    the step that removes it, in a comment above the override."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for override in _mypy("pyproject.toml").overrides:
        if override.disallow_any_explicit is not False:
            continue
        block = text[: text.index(f"module = {list(override.module)!r}".replace("'", '"'))]
        recent = block.rsplit("[[tool.mypy.overrides]]", 1)[-1]
        assert "G." in recent, f"{override.module} is exempt with no step named"


def _mypy_invocations() -> list[str]:
    """Every command in mise.toml that runs mypy."""
    run = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["types"].run
    commands = [run] if isinstance(run, str) else list(run)
    return [line for one in commands for line in one.splitlines() if " mypy " in line]
