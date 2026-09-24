# tooling/src/otsafety_tooling/contracts/zod.py
"""The site's Zod, generated from the contracts' JSON Schema, in Zod 4's current API.

WHY IT IS GENERATED HERE. json-schema-to-zod, which generated it before, stopped
being maintained in March 2026 and emitted APIs Zod 4 deprecates. The JSON Schema
this repository exports is a closed set -- schemas._prepare inlines every $ref and
normalizes tuples and unions -- so the generator covers exactly the keywords that
set uses, observed across every contract, and refuses any other by name and path.
A new construct therefore fails the export instead of degrading to something loose.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

from otsafety_tooling.paths import REPO_ROOT

SOURCE = REPO_ROOT / "contracts" / "json"
TARGET = REPO_ROOT / "apps" / "site" / "src" / "contracts"
KNOWN = frozenset(
    {
        "type",
        "format",
        "minLength",
        "maxLength",
        "pattern",
        "minimum",
        "exclusiveMinimum",
        "items",
        "minItems",
        "maxItems",
        "properties",
        "required",
        "additionalProperties",
        "minProperties",
        "anyOf",
        "enum",
        "const",
        "default",
        "description",
        "title",
        "writeOnly",
        "x-json-value",
    }
)
FORMATS = frozenset({"date-time", "path", "password"})


class UnsupportedSchemaError(ValueError):
    """A construct the generator does not know: refused, never approximated."""


def _literal(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False)


def _schema(node: JsonValue, where: str) -> dict[str, JsonValue]:
    if not isinstance(node, dict):
        raise UnsupportedSchemaError(f"{where}: expected a schema object")
    unknown = sorted(set(node) - KNOWN)
    if unknown:
        raise UnsupportedSchemaError(f"{where}: unsupported keyword {', '.join(unknown)}")
    return node


def _count(schema: dict[str, JsonValue], key: str, where: str) -> int:
    value = schema[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise UnsupportedSchemaError(f"{where}: {key} must be an integer")
    return value


def _nodes(schema: dict[str, JsonValue], key: str, where: str) -> list[JsonValue]:
    value = schema[key]
    if not isinstance(value, list):
        raise UnsupportedSchemaError(f"{where}: {key} must be a list")
    return value


def expression(node: JsonValue, where: str = "#") -> str:
    """The Zod expression for one schema node."""
    schema = _schema(node, where)
    code = _base(schema, where)
    if "default" in schema:
        code += f".default({_literal(schema['default'])})"
    description = schema.get("description")
    if isinstance(description, str):
        code += f".describe({_literal(description)})"
    return code


def _base(schema: dict[str, JsonValue], where: str) -> str:
    if schema.get("x-json-value") is True:
        return "z.json()"
    if "anyOf" in schema:
        parts = [
            expression(m, f"{where}/anyOf/{i}")
            for i, m in enumerate(_nodes(schema, "anyOf", where))
        ]
        return parts[0] if len(parts) == 1 else f"z.union([{', '.join(parts)}])"
    if "const" in schema:
        return f"z.literal({_literal(schema['const'])})"
    if "enum" in schema:
        values = _nodes(schema, "enum", where)
        if all(isinstance(v, str) for v in values):
            return f"z.enum([{', '.join(_literal(v) for v in values)}])"
        literals = [f"z.literal({_literal(v)})" for v in values]
        return literals[0] if len(literals) == 1 else f"z.union([{', '.join(literals)}])"
    kind = schema.get("type")
    if kind == "string":
        return _string(schema, where)
    if kind in ("integer", "number"):
        code = "z.int()" if kind == "integer" else "z.number()"
        if "minimum" in schema:
            code += f".gte({_literal(schema['minimum'])})"
        if "exclusiveMinimum" in schema:
            code += f".gt({_literal(schema['exclusiveMinimum'])})"
        return code
    if kind == "boolean":
        return "z.boolean()"
    if kind == "null":
        return "z.null()"
    if kind == "array":
        return _array(schema, where)
    if kind == "object":
        return _object(schema, where)
    raise UnsupportedSchemaError(f"{where}: no type, const, enum or anyOf to generate from")


def _string(schema: dict[str, JsonValue], where: str) -> str:
    fmt = schema.get("format")
    if fmt is not None and fmt not in FORMATS:
        raise UnsupportedSchemaError(f"{where}: unsupported format {fmt}")
    if fmt == "date-time":
        if {"minLength", "maxLength", "pattern"} & set(schema):
            raise UnsupportedSchemaError(f"{where}: a date-time carries no length or pattern")
        # The offset matches what Pydantic writes, and what the previous output accepted.
        return "z.iso.datetime({ offset: true })"
    code = "z.string()"
    if "minLength" in schema:
        code += f".min({_count(schema, 'minLength', where)})"
    if "maxLength" in schema:
        code += f".max({_count(schema, 'maxLength', where)})"
    pattern = schema.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise UnsupportedSchemaError(f"{where}: pattern must be a string")
        code += f".regex(new RegExp({_literal(pattern)}))"
    return code


def _array(schema: dict[str, JsonValue], where: str) -> str:
    items = schema.get("items")
    if isinstance(items, list):
        for key in ("minItems", "maxItems"):
            if key in schema and _count(schema, key, where) != len(items):
                raise UnsupportedSchemaError(f"{where}: a tuple's {key} must equal its length")
        members = ", ".join(
            expression(member, f"{where}/items/{index}") for index, member in enumerate(items)
        )
        return f"z.tuple([{members}])"
    if items is None:
        raise UnsupportedSchemaError(f"{where}: an array must say what its items are")
    code = f"z.array({expression(items, f'{where}/items')})"
    if "minItems" in schema:
        code += f".min({_count(schema, 'minItems', where)})"
    if "maxItems" in schema:
        code += f".max({_count(schema, 'maxItems', where)})"
    return code


def _object(schema: dict[str, JsonValue], where: str) -> str:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise UnsupportedSchemaError(f"{where}: properties must be an object")
    required = (
        {r for r in _nodes(schema, "required", where) if isinstance(r, str)}
        if "required" in schema
        else set()
    )
    extra = schema.get("additionalProperties")
    fields = []
    for key, value in properties.items():
        code = expression(value, f"{where}/properties/{key}")
        if key not in required and not (isinstance(value, dict) and "default" in value):
            code += ".optional()"
        fields.append(f"{_literal(key)}: {code}")
    body = "{ " + ", ".join(fields) + " }" if fields else "{}"
    if properties:
        if extra is False:
            code = f"z.strictObject({body})"
        elif extra is None:
            code = f"z.object({body})"
        elif extra is True:
            code = f"z.looseObject({body})"
        else:
            code = (
                f"z.object({body}).catchall({expression(extra, f'{where}/additionalProperties')})"
            )
    elif isinstance(extra, dict):
        code = f"z.record(z.string(), {expression(extra, f'{where}/additionalProperties')})"
    elif extra is False:
        code = "z.strictObject({})"
    else:
        raise UnsupportedSchemaError(
            f"{where}: an object with no properties must say what its values are"
        )
    if "minProperties" in schema:
        least = _count(schema, "minProperties", where)
        code += (
            f".refine((value) => Object.keys(value).length >= {least}, "
            f'{{ message: "at least {least} entries" }})'
        )
    return code


def module(file: Path) -> tuple[str, str]:
    """The generated TypeScript for one exported contract, and the name it exports."""
    stem = file.name.removesuffix(".schema.json")
    parts = re.split(r"[.-]", stem)
    name = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:]) + "Schema"
    schema: JsonValue = TypeAdapter(JsonValue).validate_json(file.read_text(encoding="utf-8"))
    header = (
        f"// GENERATED from contracts/json/{file.name} by otsafety_tooling.contracts.zod.\n"
        "// Do not edit: change the Pydantic model and run mise run contracts:generate.\n"
    )
    return (
        name,
        header + 'import { z } from "zod";\n\n' + f"export const {name} = {expression(schema)};\n",
    )


def generate(target: Path = TARGET) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for file in sorted(SOURCE.glob("*.schema.json")):
        name, code = module(file)
        out = target / f"{file.name.removesuffix('.schema.json')}.gen.ts"
        out.write_text(code, encoding="utf-8")
        written.append(f"wrote {out.name} ({name})")
    return written


def main(argv: list[str]) -> int:
    """An optional directory writes elsewhere, so a test can compare with the committed files."""
    written = generate(Path(argv[0]) if argv else TARGET)
    print("\n".join(written))  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
