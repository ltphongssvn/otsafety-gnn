# tooling/src/otsafety_tooling/contracts/bunfig.py
"""apps/site/bunfig.toml: what bun may do while a gate is running.

A GATE THAT CAN REACH THE NETWORK CAN HANG. eslint-effective.ts imports eslint,
and in a worktree where setup has not run there is no node_modules -- so bun
resolved the import by auto-installing from the registry and stayed there for
forty-one minutes, holding the whole check and returning no prompt. A fetch has
no time bound; a missing dependency does.

These three settings make that impossible, and a test asserts each: auto-install
off, so an unresolvable import is an error; offline, so the registry is not
reachable; and a frozen lockfile, so a stale one fails rather than resolving
something new.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class InstallSettings(BaseModel):
    """[install] in bunfig.toml, as bun documents its keys."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    auto: Literal["auto", "force", "fallback", "disable"] = "auto"
    offline: bool = False
    frozen_lockfile: bool = Field(default=False, alias="frozenLockfile")


class BunfigFile(BaseModel):
    """The committed bunfig, validated."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    AUTHORED: ClassVar[bool] = True

    install: InstallSettings
