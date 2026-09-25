# tooling/tests/test_contract_export.py
"""Every contract is exported, discovered from the models rather than listed.

WHY THIS EXISTS. schemas.py exported three contracts named in a hand-written dict
-- the duplication the schema-first policy removes everywhere else -- so the plan,
its trace and plan-status/v1 never reached the site. A contract is any model whose
`contract` field is a literal; the export is derived from exactly that.

TWO KINDS, TWO RULES. A record is written by code that serialises every field, so
its reader requires every field and fills in nothing. An authored file is written
by a person who leaves defaults out -- a root step has no depends_on -- so it is
exported as Pydantic accepts it. Under the record rule the site would reject the
plan itself.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import typing

import pytest
from pydantic import BaseModel

import otsafety_tooling.contracts as contracts_pkg
from otsafety_tooling.contracts import schemas
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.8")


def _declared() -> set[str]:
    found: set[str] = set()
    for info in pkgutil.iter_modules(contracts_pkg.__path__):
        module = importlib.import_module(f"{contracts_pkg.__name__}.{info.name}")
        for obj in vars(module).values():
            if not (isinstance(obj, type) and issubclass(obj, BaseModel)):
                continue
            # An independent oracle for discovery: a literal contract field, or a
            # CONTRACT_ID class variable where nothing serialises one.
            declared = getattr(obj, "CONTRACT_ID", None)
            if isinstance(declared, str):
                found.add(declared)
            if "contract" in obj.model_fields:
                annotation = obj.model_fields["contract"].annotation
                if typing.get_origin(annotation) is typing.Literal:
                    found.update(typing.get_args(annotation))
    return found


def test_every_declared_contract_is_exported() -> None:
    assert set(schemas.EXPORTED) == _declared()


def test_the_status_record_is_exported_and_committed() -> None:
    assert "plan-status/v1" in schemas.EXPORTED
    assert (REPO_ROOT / schemas.schema_path("plan-status/v1")).is_file()


def test_a_record_requires_every_field() -> None:
    schema = schemas.json_schema("plan-status/v1")
    declared = schema.get("required", [])
    assert isinstance(declared, list)
    assert {"contract", "ref", "steps", "threads"} <= set(declared)


def test_an_authored_file_keeps_what_a_person_leaves_out() -> None:
    """A root step omits depends_on; the site must still accept the plan."""
    plan = schemas.json_schema("project-plan/v1")
    step = schemas.at(plan, "properties", "steps", "items")
    required = step.get("required", [])
    assert isinstance(required, list)
    assert "depends_on" not in required
    assert "branch" not in required


def test_no_discriminator_points_at_a_removed_definition() -> None:
    text = json.dumps(schemas.json_schema("project-plan/v1"))
    assert "$defs" not in text and "#/$defs" not in text
