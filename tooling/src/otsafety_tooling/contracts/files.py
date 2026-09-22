# tooling/src/otsafety_tooling/contracts/files.py
"""The one place a file is read into a model.

JSON needs no parser of ours: Pydantic parses and validates it in one step with
model_validate_json. YAML has no Pydantic parser, so this is the single sanctioned
yaml.safe_load, and its result goes straight into model_validate -- untyped YAML
never reaches a caller. ruff's banned-api rule forbids both calls everywhere else.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml
from pydantic import BaseModel


def read_json[M: BaseModel](path: Path, model: type[M]) -> M:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def read_yaml[M: BaseModel](path: Path, model: type[M]) -> M:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))  # noqa: TID251
    return model.model_validate(loaded)


def read_toml[M: BaseModel](path: Path, model: type[M]) -> M:
    loaded = tomllib.loads(path.read_text(encoding="utf-8"))  # noqa: TID251
    return model.model_validate(loaded)


# TEXT READ FROM A GIT REF, NOT A FILE ON DISK: plan:status observes the plan and
# the tasks on the integration branch, where the working tree may differ. The same
# sanctioned calls, so the policy's single place to parse stays single.
def parse_yaml[M: BaseModel](text: str, model: type[M]) -> M:
    return model.model_validate(yaml.safe_load(text))  # noqa: TID251


def parse_toml[M: BaseModel](text: str, model: type[M]) -> M:
    return model.model_validate(tomllib.loads(text))  # noqa: TID251
