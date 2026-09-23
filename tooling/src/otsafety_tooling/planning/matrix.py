# tooling/src/otsafety_tooling/planning/matrix.py
"""Build the requirement matrix: one row per id, from the plan, its trace and the commits.

Forward: does every requirement have evidence, and a file that names it? Backward:
is every requirement justified by an observation, and does every observation map to
a requirement that exists? The rules live in policy/requirements.rego; this only
observes, so the policy decides over typed data rather than over a script's opinion.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.cli import result
from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.contracts.plan_trace import PlanTrace
from otsafety_tooling.contracts.traceability import Requirement, RequirementMatrix
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.exemptions import candidates
from otsafety_tooling.policy.trailers import claimed_done, commits_since_cutoff, referenced

KINDS: tuple[tuple[Literal["step", "decision"], str], ...] = (
    ("step", "steps"),
    ("decision", "decisions"),
)


class _Payload(BaseModel):
    """A command's payload: named fields, checked where they are written.

    **kwargs cannot be checked -- a misspelt field would ship -- so each command
    declares what it carries, and a list stays a list because the model says so.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class MatrixWritten(_Payload):
    artifact: str
    requirements: int
    orphan_candidates: list[str]
    ref: str


def _evidence(step: object) -> tuple[str, ...]:
    out = []
    for item in getattr(step, "done_when", ()):
        for attribute in ("path", "name", "number", "tag"):
            value = getattr(item, attribute, None)
            if value is not None:
                out.append(f"{item.kind}:{value}")
    return tuple(out)


def build(root: Path = REPO_ROOT, ref: str = "HEAD") -> RequirementMatrix:
    """Observe every requirement's identity; the rules live in policy/requirements.rego."""
    plan = read_yaml(root / "context" / "plan.yaml", ProjectPlan)
    trace = read_yaml(root / "context" / "plan-trace.yaml", PlanTrace)
    justified: dict[str, list[str]] = {}
    known = {s.id for s in plan.steps} | {d.id for d in plan.decisions}
    orphans = []
    for candidate in trace.candidates:
        for target in candidate.maps_to:
            justified.setdefault(target, []).append(candidate.ref)
            if target not in known:
                orphans.append(f"{candidate.ref} -> {target}")
    named: dict[str, list[str]] = {}
    for relative in candidates(root):
        path = root / relative
        if not path.is_file() or path.suffix not in {".py", ".rego", ".ts"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for identifier in known:
            if identifier in text:
                named.setdefault(identifier, []).append(relative)
    # NOT `referenced`: that name is the imported reader of a message's trailers.
    references: dict[str, list[str]] = {}
    claimed: dict[str, list[str]] = {}
    for sha, message, _ in commits_since_cutoff(root):
        for identifier in referenced(message):
            references.setdefault(identifier, []).append(sha[:9])
        for identifier in claimed_done(message):
            claimed.setdefault(identifier, []).append(sha[:9])
    rows = [
        Requirement(
            id=item.id,
            title=item.title,
            thread=getattr(item, "thread", "-"),
            phase=getattr(item, "phase", "-"),
            kind=kind,
            evidence=_evidence(item),
            justified_by=tuple(justified.get(item.id, ())),
            named_in=tuple(sorted(named.get(item.id, ()))),
            referenced_by=tuple(references.get(item.id, ())),
            claimed_by=tuple(claimed.get(item.id, ())),
        )
        for kind, attribute in KINDS
        for item in getattr(plan, attribute)
    ]
    head = git("rev-parse", ref, cwd=root).stdout.strip()
    return RequirementMatrix(
        ref=head, requirements=tuple(rows), orphan_candidates=tuple(sorted(orphans))
    )


def main(argv: list[str]) -> int:
    matrix = build()
    out = (
        Path(argv[0]) if argv else artifacts_root(REPO_ROOT) / "policy" / "requirement-matrix.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(matrix.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return result(
        "plan:matrix",
        "success",
        "matrix_written",
        f"{len(matrix.requirements)} requirements observed at {matrix.ref[:9]}",
        MatrixWritten(
            artifact=str(out),
            requirements=len(matrix.requirements),
            orphan_candidates=list(matrix.orphan_candidates),
            ref=matrix.ref,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
