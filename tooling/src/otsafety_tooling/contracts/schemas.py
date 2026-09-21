# tooling/src/otsafety_tooling/contracts/schemas.py
"""The JSON Schema of every contract the site reads, exported from its model.

THE PYDANTIC MODEL IS THE SINGLE SOURCE. The site used to hand-write TypeScript
types beside these contracts, and they drifted: four of five repository-settings
fields had the wrong names, and production rendered the real failing verdict with
no date and three empty findings. Now each model exports its JSON Schema, the
site generates Zod from the committed file, and a test fails when either side
diverges from the model.

THE SCHEMA DESCRIBES WHAT PRODUCERS WRITE, NOT WHAT PYDANTIC WOULD ACCEPT. A
producer serialises every field, so the reader requires every property and fills
in nothing: a default would become Zod's .default(), which supplies a missing
field instead of rejecting the record -- the `?? ""` in the template that hid
the drift, moved into the validator. References are inlined because
json-schema-to-zod does not follow $ref into $defs: the nested finding shape,
exactly the one that rendered blank, came out as z.any(). extra="forbid" on every
model becomes additionalProperties: false, so an unknown field fails the build.

Cross-field rules -- a failure needs an error_type, S001 needs an observation --
live in model validators and cannot be expressed in JSON Schema. The producer
enforces them when it writes; the site checks shape and vocabulary when it reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from otsafety_tooling.contracts.experiment_run import ExperimentRun
from otsafety_tooling.contracts.repository_settings import SettingsCheckReport
from otsafety_tooling.contracts.run_record import RunRecord
from otsafety_tooling.paths import REPO_ROOT

EXPORTED: dict[str, type[BaseModel]] = {
    "run-record/v1": RunRecord,
    "repository-settings-check/v1": SettingsCheckReport,
    "experiment-run/v1": ExperimentRun,
}
SCHEMA_DIR = Path("contracts") / "json"


def schema_path(contract: str) -> Path:
    """contracts/json/<name>.<version>.schema.json, relative to the repository."""
    name, version = contract.split("/")
    return SCHEMA_DIR / f"{name}.{version}.schema.json"


def _for_reader(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline every $ref, require every property, and drop every default."""
    definitions: dict[str, Any] = schema.get("$defs", {})

    def walk(node: Any, seen: frozenset[str]) -> Any:
        if isinstance(node, list):
            return [walk(item, seen) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = str(node["$ref"]).removeprefix("#/$defs/")
            if name in seen:
                raise ValueError(f"recursive reference to {name} cannot be inlined")
            merged = dict(definitions[name])
            merged.update({k: v for k, v in node.items() if k != "$ref"})
            return walk(merged, seen | {name})
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in ("$defs", "default"):
                continue
            if key == "properties":
                # A mapping of names to schemas: a property named "default" is kept.
                out[key] = {name: walk(sub, seen) for name, sub in value.items()}
            else:
                out[key] = walk(value, seen)
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
        return out

    result: dict[str, Any] = walk(schema, frozenset())
    return result


def json_schema(contract: str) -> dict[str, Any]:
    return _for_reader(EXPORTED[contract].model_json_schema(mode="validation"))


def main() -> int:
    """Write every schema; the committed files are what the site generates from."""
    for contract in sorted(EXPORTED):
        path = REPO_ROOT / schema_path(contract)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(json_schema(contract), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(REPO_ROOT)}")  # noqa: T201 -- this is the command's output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
