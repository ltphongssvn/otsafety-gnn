# tooling/src/otsafety_tooling/contracts/inventory.py
"""command-inventory/v1: every command this repository owns, and how it reports.

A COMMAND IS A MODULE WITH A main(). That is the definition the tree gives, so
the inventory cannot drift from the code the way a hand-kept list does.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class Command(BaseModel):
    """One command: where it lives, whether it emits an envelope, and why not."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module: str
    emits: bool
    # THE REASON, NOT A FLAG: an exception is only allowed when the code says at
    # its own line what makes it one -- a value a shell substitutes, or a wrapper
    # whose inner envelope is already the whole of stdout.
    exempt_because: str | None = None


class CommandInventory(BaseModel):
    """Every command found in the tree, for the policy to judge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CONTRACT_ID: ClassVar[str] = "command-inventory/v1"

    contract: str = Field(default="command-inventory/v1")
    commands: tuple[Command, ...]
