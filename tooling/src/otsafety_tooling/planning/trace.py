# tooling/src/otsafety_tooling/planning/trace.py
"""The one writer for plan-trace.yaml, as the plan and the ledger each have one.

THE TRACE HAD NO WRITER. It is read in three places -- the matrix, the data
export, its own contract -- and written only by whatever script happened to be
editing it, each with its own yaml.safe_dump arguments. Two writers of one file
is how serialization drifts, and a file nothing owns carries no header, which is
how this one failed the header gate.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from otsafety_tooling.contracts.plan_trace import PlanTrace
from otsafety_tooling.paths import REPO_ROOT

HEADER = "# context/plan-trace.yaml\n"


def trace_path(root: Path = REPO_ROOT) -> Path:
    """Beside the plan, because it records where the plan came from."""
    return root / "context" / "plan-trace.yaml"


def canonical(trace: PlanTrace) -> str:
    """The one serialization, matching the plan's and the ledger's."""
    body = yaml.safe_dump(
        trace.model_dump(mode="json", by_alias=True, exclude_none=True),
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
    return HEADER + body


def save_trace(trace: PlanTrace, path: Path | None = None) -> Path:
    """Write the trace in its canonical form, and nothing else."""
    target = path or trace_path()
    target.write_text(canonical(trace), encoding="utf-8")
    return target
