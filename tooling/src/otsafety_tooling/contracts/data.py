# tooling/src/otsafety_tooling/contracts/data.py
"""The data of every context and conf file, exported for the site (G.20).

THE PIPELINE ALREADY CARRIES SHAPES: Pydantic to JSON Schema to generated Zod.
It did not carry the DATA, so the site restated parts of the plan in hand-written
TypeScript -- the duplication the schema-first policy removes everywhere else.

EACH FILE IS VALIDATED BY ITS OWN MODEL and written as that model's JSON. The
site reads it as a content collection and checks it again with the Zod generated
from the same model, so one source is validated on both sides and neither can
drift from the other without a gate saying so.

WHY JSON AND NOT THE YAML ITSELF. Astro's file() loader parses YAML natively
only when no parser is given, and these are nested documents rather than arrays
of entries. Exporting the validated data means the site needs no YAML parser and
no second copy of the rules for reading it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from otsafety_tooling.contracts.architecture import Architecture
from otsafety_tooling.contracts.exemptions import ExemptionRegister
from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.opentargets_config import OpenTargetsConfig
from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.contracts.plan_trace import PlanTrace
from otsafety_tooling.contracts.traceability import IdLedger
from otsafety_tooling.paths import REPO_ROOT

TARGET = Path("apps/site/src/content")


@dataclass(frozen=True)
class Source:
    """One committed file, and the model that says what it may contain."""

    name: str
    path: Path
    model: type[BaseModel]


SOURCES: tuple[Source, ...] = (
    Source("plan", REPO_ROOT / "context" / "plan.yaml", ProjectPlan),
    Source("plan-trace", REPO_ROOT / "context" / "plan-trace.yaml", PlanTrace),
    Source("architecture", REPO_ROOT / "context" / "architecture.yaml", Architecture),
    Source("plan-ids", REPO_ROOT / "context" / "plan-ids.yaml", IdLedger),
    Source("exemptions", REPO_ROOT / "context" / "exemptions.yaml", ExemptionRegister),
    Source("config", REPO_ROOT / "conf" / "config.yaml", OpenTargetsConfig),
)


def export(source: Source) -> str:
    """The file's data as its model serialises it, ending in a newline."""
    return read_yaml(source.path, source.model).model_dump_json(indent=2) + "\n"


def main() -> int:
    """Write every export, and say what was written."""
    from otsafety_tooling.cli import note, result

    target = REPO_ROOT / TARGET
    target.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for source in SOURCES:
        path = target / f"{source.name}.json"
        path.write_text(export(source), encoding="utf-8")
        written.append(str(path.relative_to(REPO_ROOT)))
        note(f"wrote {path.relative_to(REPO_ROOT)}")
    return result(
        "contracts:data",
        "success",
        "data_exported",
        f"{len(written)} context files exported for the site",
        Exported(files=written),
    )


class Exported(BaseModel):
    """Which files the export wrote."""

    files: list[str]


if __name__ == "__main__":
    raise SystemExit(main())
