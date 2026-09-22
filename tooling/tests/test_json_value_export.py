# tooling/tests/test_json_value_export.py
"""A JSON value generates Zod 4's z.json(), not z.any().

Pydantic writes a JsonValue field as a reference to a definition named JsonValue,
whose body is {}. Inlining turned it into "no constraint", which generates
z.any() -- a trust boundary left unchecked. The export keeps the meaning as a
marker, and the generator turns the marker into z.json().
"""

from __future__ import annotations

from otsafety_tooling.contracts import schemas
from otsafety_tooling.paths import REPO_ROOT


def _markers(node: object) -> int:
    if isinstance(node, dict):
        return int(node.get("x-json-value") is True) + sum(_markers(v) for v in node.values())
    if isinstance(node, list):
        return sum(_markers(v) for v in node)
    return 0


def test_the_export_marks_each_json_value() -> None:
    assert _markers(schemas.json_schema("eslint-effective/v1")) >= 1
    assert _markers(schemas.json_schema("eslint-calculated-config/v1")) >= 1


def test_the_generator_writes_z_json() -> None:
    for name in ("eslint-effective.v1", "eslint-calculated-config.v1"):
        generated = (
            REPO_ROOT / "apps" / "site" / "src" / "contracts" / f"{name}.gen.ts"
        ).read_text()
        assert "z.json()" in generated and "z.any()" not in generated, name
