# tooling/tests/test_generated_zod_is_current.py
"""The site's Zod is generated here, in Zod 4's current API, and nothing else is accepted.

WHY THIS EXISTS. json-schema-to-zod, which generated every contract's Zod, stopped
being maintained in March 2026 and emitted z.string().datetime(), which Zod 4
deprecates -- seven times. astro check reported them as hints, and failed only on
errors, so nothing noticed. The generator is now otsafety_tooling.contracts.zod,
over the closed set of JSON Schema this repository exports; any keyword or format
it does not know is refused by name, so a new construct fails the export rather
than degrading. astro check now fails on any hint.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from otsafety_tooling.contracts.zod import UnsupportedSchemaError, expression
from otsafety_tooling.paths import REPO_ROOT

# THIS FILE PROVES G.32: the claim the requirement matrix joins on.
pytestmark = pytest.mark.requirement("G.32")

GENERATED = sorted((REPO_ROOT / "apps" / "site" / "src" / "contracts").glob("*.gen.ts"))
# Zod 3 forms that Zod 4 deprecates or replaces; none may appear in generated code.
DEPRECATED = re.compile(
    r"z\.string\(\)\.(datetime|date|time|email|url|uuid|ip|cidr|base64)\(|\.strict\(\)|\.passthrough\(\)|\.nonstrict\(\)|\.deepPartial\("
)


def test_a_datetime_is_zod_4s_iso_datetime_with_its_offset() -> None:
    assert (
        expression({"type": "string", "format": "date-time"}) == "z.iso.datetime({ offset: true })"
    )


def test_objects_strings_and_numbers() -> None:
    code = expression(
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["a"],
            "properties": {
                "a": {"type": "string", "minLength": 1, "pattern": "^x\\d$"},
                "b": {"type": "integer", "minimum": 0, "default": 3},
            },
        }
    )
    assert (
        code == 'z.strictObject({ "a": z.string().min(1).regex(new RegExp("^x\\\\d$")), '
        '"b": z.int().gte(0).default(3) })'
    )


def test_records_tuples_unions_and_json() -> None:
    assert (
        expression({"type": "object", "additionalProperties": {"type": "boolean"}})
        == "z.record(z.string(), z.boolean())"
    )
    assert (
        expression(
            {
                "type": "array",
                "items": [{"type": "string"}, {"type": "null"}],
                "minItems": 2,
                "maxItems": 2,
            }
        )
        == "z.tuple([z.string(), z.null()])"
    )
    assert (
        expression({"anyOf": [{"type": "string"}, {"type": "null"}]})
        == "z.union([z.string(), z.null()])"
    )
    assert expression({"x-json-value": True}) == "z.json()"
    assert expression({"type": "string", "enum": ["a", "b"]}) == 'z.enum(["a", "b"])'
    assert expression({"type": "string", "const": "v1"}) == 'z.literal("v1")'


def test_an_optional_property_without_a_default_is_optional() -> None:
    assert (
        expression({"type": "object", "properties": {"a": {"type": "boolean"}}})
        == 'z.object({ "a": z.boolean().optional() })'
    )


def test_an_unknown_keyword_is_refused_by_name() -> None:
    with pytest.raises(UnsupportedSchemaError, match="oneOf"):
        expression({"type": "string", "oneOf": []})


def test_an_unknown_format_is_refused_by_name() -> None:
    with pytest.raises(UnsupportedSchemaError, match="email"):
        expression({"type": "string", "format": "email"})


@pytest.mark.parametrize("path", GENERATED, ids=lambda p: p.name)
def test_no_generated_contract_uses_a_deprecated_api(path: Path) -> None:
    assert not DEPRECATED.search(path.read_text(encoding="utf-8")), path.name


def test_the_committed_zod_is_what_the_generator_produces(tmp_path: Path) -> None:
    """THE GATE THIS FILE'S NAME ALREADY CLAIMED (G.52).

    Twenty-four tests passed while every committed module was stale: they check
    for deprecated APIs and for loose shapes, and none regenerated and compared.
    A change to the generator's header therefore reached nothing, and a
    hand-edited module would have passed every one of them.

    The data export has had this check since the day it was written; its older
    sibling did not.
    """
    from otsafety_tooling.contracts.zod import TARGET, generate

    generate(tmp_path)
    fresh = sorted(tmp_path.glob("*.gen.ts"))
    assert fresh, "the generator wrote nothing, so this gate would pass vacuously"
    for written in fresh:
        committed = TARGET / written.name
        assert committed.is_file(), f"{written.name} is generated and not committed"
        assert committed.read_text(encoding="utf-8") == written.read_text(encoding="utf-8"), (
            f"{written.name} differs from the generator; run mise run contracts:generate"
        )
