# tooling/tests/test_the_package_is_a_workspace_member.py
"""python/otsafety is a workspace member, resolved and editable (9.1).

EVERY LATER STEP IMPORTS THIS. The contracts, the ingest, the splits, the audit
and the model card all live here, and until it exists none of them can be
written -- which is why it sat behind a policy release tag for no recorded
reason until G.73 cut that edge.

THE WORKSPACE RESOLVES IT, not a path dependency or a manual install. uv treats
a member as a local editable package, so a change is visible immediately and
the lockfile carries one resolution for the whole repository.

THE ROOT IS VIRTUAL, which removes the trap 2026 practice warns about: a root
with a [project] name equal to a member's makes uv refuse with two members of
the same name. This root declares no project at all.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("9.1")

PACKAGE = REPO_ROOT / "python" / "otsafety"


def test_the_member_is_declared_in_the_workspace() -> None:
    """A directory with a pyproject is not a member until the root says so."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.workspace import RootProject

    root = read_toml(REPO_ROOT / "pyproject.toml", RootProject)
    assert "python/otsafety" in root.tool.uv.workspace.members, (
        f"the workspace lists {list(root.tool.uv.workspace.members)}"
    )


def test_the_package_declares_itself() -> None:
    """Name, python floor and a src layout, as every member here does."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.workspace import MemberProject

    member = read_toml(PACKAGE / "pyproject.toml", MemberProject)
    assert member.project.name == "otsafety"
    assert member.project.requires_python.startswith(">=3.13")


def test_the_python_floor_agrees_with_the_pinned_interpreter() -> None:
    """A member resolving against a different floor is how a lock diverges."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.workspace import MemberProject

    pinned = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    member = read_toml(PACKAGE / "pyproject.toml", MemberProject)
    assert pinned.startswith("3.13"), f"the pinned interpreter moved to {pinned}"
    assert "3.13" in member.project.requires_python


def test_the_package_imports_and_names_its_release() -> None:
    """The first thing every later step does, done once here."""
    import otsafety

    assert otsafety.__version__


def test_ruff_sees_the_member_as_first_party() -> None:
    """Otherwise its own modules read as third-party imports."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.workspace import RootProject

    root = read_toml(REPO_ROOT / "pyproject.toml", RootProject)
    assert "python/otsafety/src" in root.tool.ruff.src, (
        f"ruff's first-party roots are {list(root.tool.ruff.src)}"
    )
