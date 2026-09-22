# tooling/tests/test_settings_model.py
"""Environment variables are read through one settings model, and nowhere else.

WHY THIS EXISTS. Configuration came in from the environment in three places: raw
os.environ reads in Python, a raw process.env read in the site, and a bash script
enforcing "online needs an entity and a key" where no model or test could see
it. OTSAFETY_ARTIFACTS is read on both sides of the language boundary with no
shared definition. One pydantic-settings model now defines every variable; the
site parses its environment through Zod generated from it; raw reads are banned.

pydantic-settings reads names case-insensitively by default and validates
defaults, unlike BaseModel; the model sets case_sensitive, since these are exact
names.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts import schemas
from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.settings import settings
from otsafety_tooling.paths import REPO_ROOT

VARIABLES = (
    "WANDB_MODE",
    "WANDB_ENTITY",
    "WANDB_API_KEY",
    "WANDB_PROJECT",
    "WANDB_DIR",
    "OTSAFETY_ARTIFACTS",
    "wandb_mode",
)


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_offline_is_the_default() -> None:
    assert settings().wandb_mode == "offline"


@pytest.mark.parametrize(
    ("missing", "present"), [("WANDB_ENTITY", "WANDB_API_KEY"), ("WANDB_API_KEY", "WANDB_ENTITY")]
)
def test_online_is_refused_without_what_it_needs(
    monkeypatch: pytest.MonkeyPatch, missing: str, present: str
) -> None:
    monkeypatch.setenv("WANDB_MODE", "online")
    monkeypatch.setenv(present, "x")
    with pytest.raises(ValidationError, match=missing):
        settings()


def test_an_unknown_mode_is_refused_naming_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_MODE", "sometimes")
    with pytest.raises(ValidationError, match="WANDB_MODE"):
        settings()


def test_names_are_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("wandb_mode", "online")
    assert settings().wandb_mode == "offline"


def test_the_artifacts_override_is_a_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTSAFETY_ARTIFACTS", str(tmp_path))
    assert settings().artifacts == tmp_path


def test_the_api_key_never_prints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "do-not-print-me")
    assert "do-not-print-me" not in repr(settings())


def test_ruff_refuses_a_raw_environment_read() -> None:
    """The ban tested by what it does, not by a string in its configuration."""
    probe = 'import os\n\nvalue = os.environ.get("X")\n'
    run = subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            "--select",
            "TID251",
            "--stdin-filename",
            "tooling/src/otsafety_tooling/probe.py",
            "-",
        ],
        input=probe,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert run.returncode != 0 and "TID251" in run.stdout, run.stdout + run.stderr


def test_the_site_reads_the_same_contract() -> None:
    assert "project-settings/v1" in schemas.EXPORTED
    schema: dict[str, Any] = schemas.json_schema("project-settings/v1")
    assert "OTSAFETY_ARTIFACTS" in schema["properties"]


def test_the_wandb_check_task_asks_the_model() -> None:
    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["wandb:check"]
    assert "otsafety_tooling.contracts.settings" in "\n".join(task.scripts)
