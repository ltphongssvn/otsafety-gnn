# tooling/src/otsafety_tooling/contracts/workflow.py
"""A GitHub Actions workflow, as far as this repository reads one.

GitHub owns the schema and it is far larger than this, so extra keys are
ignored rather than refused -- the stance ObservedSettings takes for the same
reason. What is read is validated: pr.required_checks() and the release tests.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _External(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)


class Trigger(_External):
    branches: tuple[str, ...] = ()


class Step(_External):
    name: str | None = None
    uses: str | None = None
    run: str | None = None
    with_: dict[str, str | int | bool] = Field(default_factory=dict, alias="with")


class Job(_External):
    name: str | None = None
    if_: str | None = Field(default=None, alias="if")
    permissions: dict[str, str] | None = None
    steps: tuple[Step, ...] = ()


class Workflow(_External):
    name: str | None = None
    on: dict[str, Trigger | None]
    permissions: dict[str, str] | None = None
    jobs: dict[str, Job]

    @model_validator(mode="before")
    @classmethod
    def _yaml_one_one(cls, data: Any) -> Any:
        """PyYAML follows YAML 1.1, where a bare `on` key loads as the boolean
        true. A trigger may also be a bare name or a list of names."""
        if not isinstance(data, dict):
            return data
        data = {("on" if key is True else key): value for key, value in data.items()}
        on = data.get("on")
        if isinstance(on, str):
            data["on"] = {on: None}
        elif isinstance(on, list):
            data["on"] = dict.fromkeys(on)
        return data

    def runs_on(self, event: str) -> bool:
        return event in self.on
