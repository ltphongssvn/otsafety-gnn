# tooling/src/otsafety_tooling/contracts/workspace.py
"""The workspace as data: what the root declares, and what a member declares.

THE ROOT IS VIRTUAL. It has no [project] table, which removes the trap 2026
practice warns about -- a root whose project name equals a member's makes uv
refuse with two members of the same name -- and means the root exists only to
declare members, the shared tool settings, and the lockfile they all resolve
into.

READ THROUGH A MODEL RATHER THAN A RAW PARSE, as G.3 requires of every
configuration this repository judges. A test asserting a member is declared has
to read that declaration, and reading it as an untyped dict is how the site's
hand-written types drifted from the contracts they read.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class Workspace(BaseModel):
    """Which directories uv resolves as local editable packages."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    members: tuple[str, ...] = Field(min_length=1)


class UvSettings(BaseModel):
    """The uv table, of which only the workspace is read here."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    workspace: Workspace


class RuffSettings(BaseModel):
    """Ruff's first-party source roots.

    A MEMBER MISSING FROM src READS AS THIRD PARTY, so its own imports sort
    into the wrong block and the formatter rewrites them on every run.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    src: tuple[str, ...] = Field(min_length=1)


class RootTools(BaseModel):
    """The tool table of the workspace root."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    uv: UvSettings
    ruff: RuffSettings


class RootProject(BaseModel):
    """The virtual root: members and the settings they share."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    CONTRACT_ID: ClassVar[str] = "workspace-root/v1"

    tool: RootTools


class MemberMetadata(BaseModel):
    """What a member says about itself."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    requires_python: str = Field(alias="requires-python", min_length=2)


class MemberProject(BaseModel):
    """A workspace member's own pyproject."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    CONTRACT_ID: ClassVar[str] = "workspace-member/v1"

    project: MemberMetadata
