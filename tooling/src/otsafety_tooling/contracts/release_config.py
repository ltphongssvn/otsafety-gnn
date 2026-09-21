# tooling/src/otsafety_tooling/contracts/release_config.py
"""[tool.semantic_release] in pyproject.toml, the release engine's configuration.

The section read is strict; the rest of pyproject.toml belongs to other tools and
is ignored rather than modelled.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _Rest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class ReleaseBranch(_Strict):
    match: str
    prerelease: bool


class SemanticReleaseConfig(_Strict):
    commit_parser: Literal["conventional"]
    tag_format: str
    allow_zero_version: bool
    major_on_zero: bool
    branches: dict[str, ReleaseBranch]


class _Tool(_Rest):
    semantic_release: SemanticReleaseConfig


class Pyproject(_Rest):
    tool: _Tool
    dependency_groups: dict[str, tuple[str, ...]] = Field(alias="dependency-groups")
