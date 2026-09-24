# tooling/tests/test_contract_schemas.py
"""The Pydantic contracts are the single source; the site derives from them.

WHY THIS EXISTS. The site hand-wrote TypeScript types beside the Python
contracts it reads, and they drifted: SettingsCheck named recorded_at, rule,
code and detail, where SettingsCheckReport writes generated_at, rule_id,
reason_code and message. Production rendered the real failing verdict as
"fail" followed by nothing -- no date, three empty findings -- and a `?? ""`
fallback hid it. The page meanwhile claimed a record not matching its contract
fails the build; a cast checks nothing.

THE PIPELINE. Each contract's JSON Schema is exported from its Pydantic model
and committed; the site generates Zod from those files and parses every record
at build time. This test is the drift gate on the first half: the committed
schema must equal what the model produces now.
"""

from __future__ import annotations

import json

import pytest
from pydantic import JsonValue

from otsafety_tooling.contracts import schemas
from otsafety_tooling.paths import REPO_ROOT


@pytest.mark.parametrize("contract", sorted(schemas.EXPORTED))
def test_the_committed_schema_matches_the_model(contract: str) -> None:
    """Regenerate with `mise run contracts:generate` when a model changes."""
    path = REPO_ROOT / schemas.schema_path(contract)
    assert path.is_file(), f"no committed schema at {path}"
    # EXEMPT: a drift gate compares the committed document itself; parsing it
    # into a model would test the model against itself.
    committed = json.loads(path.read_text(encoding="utf-8"))  # noqa: TID251
    assert committed == schemas.json_schema(contract), (
        f"{path.name} has drifted from its model; run mise run contracts:generate"
    )


def test_a_fixed_vocabulary_becomes_an_enum_the_site_can_check() -> None:
    """verdict and outcome were bare strings on the TypeScript side."""
    schema = schemas.json_schema("repository-settings-check/v1")
    verdict = schemas.at(schema, "properties", "verdict")
    assert verdict["enum"] == ["pass", "fail", "unknown"]


def _objects(node: object) -> list[dict[str, JsonValue]]:
    """Every object schema in the tree, however deeply nested."""
    found: list[dict[str, JsonValue]] = []
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            found.append(node)
        for value in node.values():
            found.extend(_objects(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_objects(value))
    return found


@pytest.mark.parametrize("contract", sorted(schemas.EXPORTED))
def test_references_are_inlined(contract: str) -> None:
    """json-schema-to-zod turned the $ref to SettingFinding into z.any()."""
    text = json.dumps(schemas.json_schema(contract))
    assert "$ref" not in text and "$defs" not in text


@pytest.mark.parametrize("contract", [c for c in schemas.EXPORTED if not schemas.is_authored(c)])
def test_the_reader_requires_every_field_and_fills_in_none(contract: str) -> None:
    """A default in the reader's schema becomes .default() in Zod, which fills a
    missing field instead of rejecting the record -- the `?? ""` mask again."""
    for obj in _objects(schemas.json_schema(contract)):
        props = obj["properties"]
        assert isinstance(props, dict)
        required = obj.get("required", [])
        assert isinstance(required, list)
        names = [name for name in required if isinstance(name, str)]
        assert sorted(names) == sorted(props), f"optional fields in {contract}"
    assert '"default"' not in json.dumps(schemas.json_schema(contract))


def test_a_finding_is_a_checked_object_not_anything() -> None:
    schema = schemas.json_schema("repository-settings-check/v1")
    items = schemas.at(schema, "properties", "findings", "items")
    assert items["type"] == "object"
    properties = items["properties"]
    assert isinstance(properties, dict)
    assert {"rule_id", "reason_code", "message"} <= set(properties)
