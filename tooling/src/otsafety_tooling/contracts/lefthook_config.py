# tooling/src/otsafety_tooling/contracts/lefthook_config.py
"""lefthook.yml, as far as this repository's tests read it.

LEFTHOOK OWNS THE SCHEMA AND VALIDATES IT ITSELF: `lefthook validate` runs in the
lint task, against the schema the tool ships. This model reads only the keys the
tests assert, and ignores the rest. The tests had matched the file line by line,
which breaks on a re-indent and passes on a matching comment.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _External(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)


class LefthookJob(_External):
    name: str
    run: str
    stage_fixed: bool = False


class LefthookHook(_External):
    piped: bool = False
    jobs: tuple[LefthookJob, ...] = ()


class LefthookConfig(_External):
    lefthook: str
    assert_lefthook_installed: bool = False
    pre_commit: LefthookHook | None = Field(default=None, alias="pre-commit")
    pre_push: LefthookHook | None = Field(default=None, alias="pre-push")
    commit_msg: LefthookHook | None = Field(default=None, alias="commit-msg")
