# tooling/src/otsafety_tooling/contracts/mise_config.py
"""mise.toml: this repository's tasks.

Three test modules each read it with their own helper, as untyped dicts. extra is
forbidden, so the model also enforces the file's own rule: no [tools] block,
because the toolchain is declared once, in toolchain.json.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MiseTask(_Strict):
    description: str = Field(min_length=1)
    run: str | tuple[str, ...]
    usage: str | None = None

    @property
    def scripts(self) -> tuple[str, ...]:
        """mise accepts a single script or a list; this is always the list."""
        return (self.run,) if isinstance(self.run, str) else self.run


class TaskConfig(_Strict):
    shell: str = Field(min_length=1)


class MiseConfig(_Strict):
    min_version: str = Field(min_length=1)
    env: dict[str, str]
    task_config: TaskConfig
    tasks: dict[str, MiseTask] = Field(min_length=1)


class MiseOverlay(_Strict):
    """mise.ood.toml: the overrides loaded when MISE_ENV=ood, on machines without Nix."""

    env: dict[str, str]
    task_config: TaskConfig
