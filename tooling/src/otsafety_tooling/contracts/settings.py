# tooling/src/otsafety_tooling/contracts/settings.py
"""project-settings/v1: every environment variable this project reads, defined once.

Configuration came in from the environment in three places -- raw os.environ
reads in Python, a raw process.env read in the site, and a bash script enforcing
"online needs an entity and a key" where no model or test could see it. This
model is the single source: Python reads it through settings(), the site parses
its environment through Zod generated from it, and raw reads are banned.

pydantic-settings reads names case-insensitively by default; these are exact
names, so case_sensitive is set. Each field is aliased to its variable, and the
exported schema carries those names. A person sets these, so the model is
exported as AUTHORED, optional fields intact.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from otsafety_tooling.cli import CommandRefused, note, result


class ProjectSettings(BaseSettings):
    AUTHORED: ClassVar[bool] = True
    # No serialised contract field: the environment has none. Declared here instead.
    CONTRACT_ID: ClassVar[str] = "project-settings/v1"

    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore", frozen=True)

    artifacts: Path | None = Field(
        default=None, alias="OTSAFETY_ARTIFACTS", description="Evidence root override."
    )
    wandb_mode: Literal["online", "offline", "disabled"] = Field(
        default="offline", alias="WANDB_MODE"
    )
    wandb_project: str | None = Field(default=None, alias="WANDB_PROJECT")
    wandb_entity: str | None = Field(default=None, alias="WANDB_ENTITY")
    wandb_api_key: SecretStr | None = Field(default=None, alias="WANDB_API_KEY")
    wandb_dir: Path | None = Field(default=None, alias="WANDB_DIR")

    @model_validator(mode="after")
    def _online_lands_somewhere(self) -> Self:
        """The rule the wandb:check script once held in bash, where nothing tested it."""
        if self.wandb_mode == "online":
            if not self.wandb_entity:
                raise ValueError(
                    "WANDB_MODE=online with no WANDB_ENTITY; runs would land in a personal project"
                )
            if self.wandb_api_key is None or not self.wandb_api_key.get_secret_value():
                raise ValueError("WANDB_MODE=online with no WANDB_API_KEY")
        return self


def settings() -> ProjectSettings:
    """The environment, read and validated; the one sanctioned reader of it."""
    return ProjectSettings()


class SettingsChecked(BaseModel):
    """The tracker settings, with the key reported as present or absent, never shown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    wandb_mode: str
    wandb_project: str | None
    wandb_entity: str | None
    wandb_api_key: str


def main(argv: list[str]) -> int:
    if argv != ["check"]:
        raise CommandRefused("usage", "usage: python -m otsafety_tooling.contracts.settings check")
    try:
        current = settings()
    except ValidationError as error:
        note(f"refusing: {error}")
        return result("wandb:check", "refused", "settings_invalid", str(error))
    key = "present" if current.wandb_api_key is not None else "absent"
    checked = SettingsChecked(
        wandb_mode=current.wandb_mode,
        wandb_project=current.wandb_project,
        wandb_entity=current.wandb_entity,
        wandb_api_key=key,
    )
    for line in (
        f"WANDB_MODE={current.wandb_mode}",
        f"WANDB_PROJECT={current.wandb_project or 'unset'}",
        f"WANDB_ENTITY={current.wandb_entity or 'unset'}",
        f"WANDB_API_KEY={key}",
    ):
        note(line)
    return result(
        "wandb:check",
        "success",
        "settings_read",
        f"mode {current.wandb_mode}, key {key}",
        checked,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
