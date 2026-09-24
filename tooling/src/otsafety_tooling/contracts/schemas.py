# tooling/src/otsafety_tooling/contracts/schemas.py
"""The JSON Schema of every contract, discovered from the models and exported.

THE PYDANTIC MODEL IS THE SINGLE SOURCE, AND SO IS THE LIST OF CONTRACTS. This
exported three contracts named in a hand-written dict, the duplication the
schema-first policy removes everywhere else, so the plan, its trace and
plan-status/v1 never reached the site. A contract is any model whose `contract`
field is a literal; EXPORTED is derived from exactly that, and two models
claiming one id is refused.

TWO KINDS, TWO RULES. A record is written by code that serialises every field,
so its reader requires every field and fills in nothing: a default would become
Zod's .default(), supplying a missing field instead of rejecting the record. An
authored file is written by a person who leaves defaults out, so a model marked
AUTHORED is exported as Pydantic accepts it. Both have references inlined, since
json-schema-to-zod does not follow $ref, and discriminator mappings dropped,
since after inlining they would point at definitions that no longer exist.

Cross-field rules live in model validators and cannot be expressed in JSON
Schema. The producer enforces them when it writes; the site checks shape.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import typing
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue

import otsafety_tooling.contracts as _package
from otsafety_tooling.cli import note, result
from otsafety_tooling.paths import REPO_ROOT

SCHEMA_DIR = Path("contracts") / "json"


def _discover() -> dict[str, type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for info in pkgutil.iter_modules(_package.__path__):
        if info.name == "schemas":
            continue
        module = importlib.import_module(f"{_package.__name__}.{info.name}")
        for obj in vars(module).values():
            if not (isinstance(obj, type) and issubclass(obj, BaseModel)):
                continue
            # A contract declares its id as a literal `contract` field or, where nothing
            # serialises one -- the environment -- as a CONTRACT_ID class variable.
            declared = getattr(obj, "CONTRACT_ID", None)
            annotation = (
                obj.model_fields["contract"].annotation if "contract" in obj.model_fields else None
            )
            ids = ((declared,) if isinstance(declared, str) else ()) + (
                typing.get_args(annotation)
                if typing.get_origin(annotation) is typing.Literal
                else ()
            )
            for contract in ids:
                if found.get(contract, obj) is not obj:
                    raise RuntimeError(f"two models declare {contract}")
                found[contract] = obj
    return dict(sorted(found.items()))


EXPORTED: dict[str, type[BaseModel]] = _discover()


def is_authored(contract: str) -> bool:
    return bool(getattr(EXPORTED[contract], "AUTHORED", False))


def schema_path(contract: str) -> Path:
    """contracts/json/<name>.<version>.schema.json, relative to the repository."""
    name, version = contract.split("/")
    return SCHEMA_DIR / f"{name}.{version}.schema.json"


def _object(value: JsonValue, what: str) -> dict[str, JsonValue]:
    """Narrow a JSON value that must be an object, or say which one was not."""
    if not isinstance(value, dict):
        raise TypeError(f"{what} is not a JSON object")
    return value


def _prepare(schema: dict[str, JsonValue], *, authored: bool) -> dict[str, JsonValue]:
    """Inline every $ref and drop discriminators; for a record, require all and default nothing."""
    definitions = _object(schema.get("$defs", {}), "$defs")
    dropped = {"$defs", "discriminator"} | (set() if authored else {"default"})

    def walk(node: JsonValue, seen: frozenset[str]) -> JsonValue:
        if isinstance(node, list):
            return [walk(item, seen) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = str(node["$ref"]).removeprefix("#/$defs/")
            # A JSON VALUE KEEPS ITS MEANING. Pydantic names it JsonValue, whose body is
            # {}; inlined, it would read as "no constraint" and generate z.any(). The
            # marker becomes Zod 4's own z.json() in the generator.
            if name == "JsonValue":
                return {"x-json-value": True}
            if name in seen:
                raise ValueError(f"recursive reference to {name} cannot be inlined")
            merged = dict(_object(definitions[name], name))
            merged.update({k: v for k, v in node.items() if k != "$ref"})
            return walk(merged, seen | {name})
        out: dict[str, JsonValue] = {}
        # 2020-12 TUPLES AND DISCRIMINATED UNIONS, rewritten into forms the generator
        # reads. prefixItems became z.any() elements; a discriminated oneOf became
        # z.any().superRefine(), which validates but types as any. The array form of
        # items becomes z.tuple, and anyOf a typed z.union: exact here, because
        # Pydantic emits oneOf only with a discriminator, whose literal field makes
        # the options mutually exclusive.
        if "prefixItems" in node:
            node = {
                **{k: v for k, v in node.items() if k != "prefixItems"},
                "items": node["prefixItems"],
            }
        if "oneOf" in node and "discriminator" in node:
            node = {**{k: v for k, v in node.items() if k != "oneOf"}, "anyOf": node["oneOf"]}
        for key, value in node.items():
            if key in dropped:
                continue
            if key == "properties":
                # A mapping of names to schemas: a property named "default" is kept.
                out[key] = {name: walk(sub, seen) for name, sub in _object(value, key).items()}
            else:
                out[key] = walk(value, seen)
        if not authored and out.get("type") == "object" and "properties" in out:
            required: list[JsonValue] = [*_object(out["properties"], "properties")]
            out["required"] = required
        return out

    return _object(walk(schema, frozenset()), "the schema")


def json_schema(contract: str) -> dict[str, JsonValue]:
    model = EXPORTED[contract]
    return _prepare(model.model_json_schema(mode="validation"), authored=is_authored(contract))


class SchemasWritten(BaseModel):
    """Which contracts were exported, and where each one landed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contracts: list[str]
    files: list[str]


def main() -> int:
    """Write every schema; the committed files are what the site generates from."""
    written: list[str] = []
    for contract in EXPORTED:
        path = REPO_ROOT / schema_path(contract)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(json_schema(contract), indent=2) + "\n", encoding="utf-8")
        written.append(str(path.relative_to(REPO_ROOT)))
        note(f"wrote {path.relative_to(REPO_ROOT)}")
    return result(
        "contracts:export",
        "success",
        "schemas_written",
        f"{len(written)} contracts exported",
        SchemasWritten(contracts=sorted(EXPORTED), files=written),
    )


if __name__ == "__main__":
    raise SystemExit(main())
