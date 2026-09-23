# tooling/src/otsafety_tooling/contracts/outcome.py
"""What a command says when it finishes, as data.

WHY THIS EXISTS. Every command here printed prose, so a caller read it with grep:
presentation filtering, not evidence. 2026 practice for a command an agent may run
is stream separation -- stdout carries the payload and nothing else, stderr carries
progress, diagnostics and the error envelope -- with a contract field, a stable
machine code rather than prose, and deterministic exit codes.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

Verdict = Literal["success", "refused", "failed"]

# DETERMINISTIC: 0 succeeded, 2 the input or the repository state was refused,
# 1 the command itself broke. A caller branches on these without reading text.
EXIT_CODES: dict[Verdict, int] = {"success": 0, "failed": 1, "refused": 2}


class CommandOutcome(BaseModel):
    """One command's result: the only thing it writes to stdout."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    CONTRACT_ID: ClassVar[str] = "command-outcome/v1"

    contract: Literal["command-outcome/v1"] = "command-outcome/v1"
    command: str = Field(min_length=1)
    outcome: Verdict
    # A STABLE MACHINE TOKEN, never prose: a caller matches on this.
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    message: str = Field(min_length=1)
    data: dict[str, JsonValue] = Field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.outcome]
