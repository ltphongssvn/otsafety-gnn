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


class _Tools(_Rest):
    ruff: RuffConfig | None = None
    uv: _Uv | None = None
    pytest: _Pytest | None = None


class _Project(_Rest):
    requires_python: str | None = Field(default=None, alias="requires-python")


class WorkspacePyproject(_Rest):
    project: _Project | None = None
    tool: _Tools = Field(default_factory=_Tools)
