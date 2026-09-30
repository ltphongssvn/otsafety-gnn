# tooling/src/otsafety_tooling/contracts/mise_config.py
"""mise.toml: this repository's tasks.

Three test modules each read it with their own helper, as untyped dicts. extra is
forbidden, so the model also enforces the file's own rule: no [tools] block,
because the toolchain is declared once, in toolchain.json.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _External(BaseModel):
    """A schema mise owns: read what is needed, ignore what is not."""

    model_config = ConfigDict(frozen=True, extra="ignore")


class MiseTask(_External):
    """A task as mise reads it, minus the one key a task may not carry."""

    @model_validator(mode="before")
    @classmethod
    def _the_shell_is_pinned_for_every_task(cls, data: object) -> object:
        if isinstance(data, dict) and "shell" in data:
            raise ValueError("a task may not set its own shell; task_config pins it for every task")
        return data

    description: str = Field(min_length=1)
    run: str | tuple[str, ...]
    usage: str | None = None

    @property
    def scripts(self) -> tuple[str, ...]:
        """mise accepts a single script or a list; this is always the list."""
        return (self.run,) if isinstance(self.run, str) else self.run


class TaskConfig(_External):
    shell: str = Field(min_length=1)


class MiseConfig(_External):
    min_version: str = Field(min_length=1)
    env: dict[str, str]
    task_config: TaskConfig
    tasks: dict[str, MiseTask] = Field(min_length=1)


class MiseOverlay(_External):
    """mise.ood.toml: the overrides loaded when MISE_ENV=ood, on machines without Nix."""

    env: dict[str, str]
    task_config: TaskConfig
