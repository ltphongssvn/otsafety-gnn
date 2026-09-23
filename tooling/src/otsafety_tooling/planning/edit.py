# tooling/src/otsafety_tooling/planning/edit.py
"""One writer for the plan, from the model, so there is one canonical form.

WHY THIS EXISTS. Steps were added by building a YAML block in a throwaway script
and splicing it into the file. 2026 practice for a file a program owns is the
opposite: one writer, from the model, and a gate asserting the committed file
equals what that writer produces. Without it, every edit invents its own field
order and quoting, and the drift only shows up later across the file's history.

THE HEADER IS NOT PART OF THE MODEL. It explains what the file is, so the reader
hands it to the writer beside the model rather than the model carrying prose.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.plan import ProjectPlan, Step
from otsafety_tooling.paths import REPO_ROOT

PLAN = REPO_ROOT / "context" / "plan.yaml"


def load(path: Path = PLAN) -> ProjectPlan:
    """The plan, through its contract: a file that does not validate is not a plan."""
    return read_yaml(path, ProjectPlan)


def header_of(path: Path = PLAN) -> str:
    """The comment block the file opens with, up to the first line of data."""
    kept: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or (not line.strip() and kept):
            kept.append(line)
            continue
        break
    return "\n".join(kept).rstrip("\n") + "\n" if kept else ""


class _Dumper(yaml.SafeDumper):
    """Sequences indented under their key, as the plan has always been written."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


def canonical(plan: ProjectPlan, header: str = "") -> str:
    """The one serialization: what the writer produces for this plan, always.

    Leaf mappings in flow style and sequences indented, which is how the plan was
    written by hand; quoting is left to the emitter, so no edit can invent its own.
    """
    body = yaml.dump(
        plan.model_dump(mode="json", by_alias=True, exclude_none=True),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=120,
        default_flow_style=None,
    )
    return header + body


def add_step(plan: ProjectPlan, step: Step) -> ProjectPlan:
    """A new plan with the step appended; the id must not already exist."""
    taken = {existing.id for existing in plan.steps} | {d.id for d in plan.decisions}
    if step.id in taken:
        raise ValueError(f"{step.id} is already in the plan; ids are issued once and never reused")
    return plan.model_copy(update={"steps": (*plan.steps, step)})


def save(plan: ProjectPlan, path: Path = PLAN, header: str = "") -> Path:
    """Write the plan in its canonical form, and nothing else."""
    path.write_text(canonical(plan, header), encoding="utf-8")
    return path
