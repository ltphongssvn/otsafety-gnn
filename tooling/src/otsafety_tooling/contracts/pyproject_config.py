# tooling/src/otsafety_tooling/contracts/pyproject_config.py
"""A read-only view of a workspace pyproject.toml: the Python it declares, and Ruff's target.

Separate from release_config.Pyproject, which models the release tool's own
isolated project and requires its semantic_release table. Only the two fields
the version gate compares are read; everything else is ignored.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Rest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class RuffLint(_Rest):
    per_file_ignores: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, alias="per-file-ignores"
    )


class RuffConfig(_Rest):
    target_version: str | None = Field(default=None, alias="target-version")
    src: tuple[str, ...] = ()
    lint: RuffLint | None = None


class _Workspace(_Rest):
    members: tuple[str, ...] = ()


class _Uv(_Rest):
    workspace: _Workspace | None = None


class PytestConfig(_Rest):
    """[tool.pytest.ini_options]: the markers a test may claim, as data.

    A marker is how a file CLAIMS a requirement -- 2026 traceability practice --
    and --strict-markers makes an unregistered one an error rather than a silent
    new marker, so a typo cannot quietly claim nothing.
    """

    markers: tuple[str, ...] = ()
    addopts: tuple[str, ...] = ()


class _Pytest(_Rest):
    ini_options: PytestConfig | None = None


class MypyOverride(_Rest):
    """One [[tool.mypy.overrides]] entry: the modules it names, and what it relaxes."""

    module: tuple[str, ...] = ()
    ignore_missing_imports: bool | None = None
    disallow_any_explicit: bool | None = None
    disable_error_code: tuple[str, ...] = ()


class MypySection(_Rest):
    """[tool.mypy], read as data so a gate can compare two of them."""

    strict: bool | None = None
    disallow_any_explicit: bool | None = None
    plugins: tuple[str, ...] = ()
    overrides: tuple[MypyOverride, ...] = ()


class _Tools(_Rest):
    ruff: RuffConfig | None = None
    uv: _Uv | None = None
    pytest: _Pytest | None = None
    mypy: MypySection | None = None


class _Project(_Rest):
    requires_python: str | None = Field(default=None, alias="requires-python")


class WorkspacePyproject(_Rest):
    project: _Project | None = None
    tool: _Tools = Field(default_factory=_Tools)
