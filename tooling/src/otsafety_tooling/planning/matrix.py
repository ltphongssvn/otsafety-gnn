# tooling/src/otsafety_tooling/planning/matrix.py
"""Build the requirement matrix: one row per id, from the plan, its trace and the commits.

Forward: does every requirement have evidence, and a file that names it? Backward:
is every requirement justified by an observation, and does every observation map to
a requirement that exists? The rules live in policy/requirements.rego; this only
observes, so the policy decides over typed data rather than over a script's opinion.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
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


def claims(path: Path) -> set[str]:
    """The requirement ids a file CLAIMS, read from its pytest markers.

    A CLAIM, NOT A MENTION. Scanning a file for an id cannot tell the two apart:
    G.25's id appeared in a file that told its story and not in the test that
    proves it. A claim is pytest.mark.requirement("G.25"), and nothing else.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        inner = node.func.value
        if node.func.attr != "requirement" or not (
            isinstance(inner, ast.Attribute) and inner.attr == "mark"
        ):
            continue
        found |= {
            a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)
        }
    return found


def unconfirmed(
    identifier: str, evidence: Sequence[str], root: Path = REPO_ROOT
) -> tuple[str, ...]:
    """The evidence entries that do not confirm this id, by the kind each one is.

    2026 practice for a traceability gate: refuse to verify a link unless the
    evidence itself can be confirmed. A Python file is confirmed by CLAIMING the
    id through the registered marker -- a mention in prose is not a claim. Any
    other file is confirmed by inspection: it must contain the id. A task, a pull
    request and a release are confirmed by plan:status, not here.
    """
    out: list[str] = []
    for item in evidence:
        kind, _, value = item.partition(":")
        if kind != "path":
            continue
        path = root / value
        if not path.is_file():
            out.append(item)
            continue
        if value.endswith(".py"):
            if identifier not in claims(path):
                out.append(item)
            continue
        try:
            if identifier not in path.read_text(encoding="utf-8"):
                out.append(item)
        except (OSError, UnicodeDecodeError):
            out.append(item)
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
        if not path.is_file() or path.suffix != ".py":
            continue
        for identifier in sorted(claims(path) & known):
            named.setdefault(identifier, []).append(relative)
    # NOT `referenced`: that name is the imported reader of a message's trailers.
    references: dict[str, list[str]] = {}
    claimed: dict[str, list[str]] = {}
    for sha, message, _, _author in commits_since_cutoff(root):
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
            unconfirmed=unconfirmed(item.id, _evidence(item), root),
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
