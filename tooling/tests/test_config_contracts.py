# tooling/tests/test_config_contracts.py
"""Every configuration file this repository reads validates against its model.

The models replace dict access that read the same files in several places. A
file failing here is caught at the gate, before any reader trusts it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.files import read_json, read_yaml
from otsafety_tooling.contracts.opentargets_config import OpenTargetsConfig
from otsafety_tooling.contracts.railway_config import RailwayConfig
from otsafety_tooling.contracts.toolchain import BinaryTool, Toolchain
from otsafety_tooling.contracts.workflow import Workflow
from otsafety_tooling.paths import REPO_ROOT

WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))


def test_the_toolchain_file_validates() -> None:
    toolchain = read_json(REPO_ROOT / "toolchain.json", Toolchain)
    assert set(toolchain.binaries) == {"uv", "bun", "gh", "mise", "railway"}


def test_a_toolchain_entry_with_an_unknown_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        BinaryTool.model_validate(
            {"version": "1", "binaries": ["x"], "artifacts": {}, "typo": True}
        )


def test_the_railway_config_validates() -> None:
    read_json(REPO_ROOT / "deploy" / "site" / "railway.json", RailwayConfig)


def test_the_ingestion_config_validates() -> None:
    read_yaml(REPO_ROOT / "conf" / "config.yaml", OpenTargetsConfig)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_validates(path: Path) -> None:
    assert read_yaml(path, Workflow).jobs


def test_a_bare_on_key_is_read_as_triggers_not_as_true() -> None:
    """YAML 1.1 loads `on:` as the boolean true; the model restores it."""
    workflow = Workflow.model_validate({True: {"pull_request": None}, "jobs": {}})
    assert workflow.runs_on("pull_request")
