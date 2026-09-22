# tooling/src/otsafety_tooling/policy/trailers.py
"""Every commit names the plan steps it serves, in a Plan-Step trailer.

Git is the record of this repository's documentation and the plan the record of
its intent; the trailer binds each change to the steps it serves. One rule, read
from two places, as 2026 practice has it: the commit-msg hook checks a message
as it is written, and the test suite checks every commit since the cutoff, in
the pre-push hook and in CI.

The message is read as git will store it -- comment lines and everything below a
scissors line cut -- and parsed by git interpret-trailers, the parser behind
%(trailers). Ids resolve against the plan in the commit's own tree, so a commit
that adds a step can cite it. Merges git writes itself are exempt, recognised by
their parents rather than their subject.
"""

from __future__ import annotations

import re
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from otsafety_tooling.contracts.files import parse_yaml
from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.status import staged_facts, unmet

KEY = "Plan-Step"
# CLOSES, WHERE KEY ONLY REFERENCES: a claim of completion, proved by the step's evidence.
DONE = "Plan-Done"
# The first commit to carry the trailer; earlier history is exempt, not rewritten.
CUTOFF = "6aee540e376745f1980761f81063d541c946aafa"
SCISSORS = re.compile(r"^# -+ >8 -+$", re.M)


def _as_stored(message: str) -> str:
    cut = SCISSORS.search(message)
    kept = message[: cut.start()] if cut else message
    return "\n".join(line for line in kept.splitlines() if not line.startswith("#")) + "\n"


def _trailers(message: str) -> list[tuple[str, str]]:
    with tempfile.NamedTemporaryFile("w", suffix=".msg", delete=False, encoding="utf-8") as handle:
        handle.write(message)
    try:
        result = git("interpret-trailers", "--parse", handle.name, cwd=REPO_ROOT)
    finally:
        Path(handle.name).unlink()
    if result.returncode != 0:
        raise SystemExit(f"git interpret-trailers failed: {result.stderr.strip()}")
    pairs = [line.partition(":") for line in result.stdout.splitlines() if ":" in line]
    return [(key.strip(), value.strip()) for key, _, value in pairs]


def claimed_done(message: str) -> list[str]:
    """The steps a message claims to complete."""
    return [value for key, value in _trailers(_as_stored(message)) if key.lower() == DONE.lower()]


def problems(
    message: str,
    ids: frozenset[str],
    *,
    is_merge: bool = False,
    holds: Callable[[str], str | None] | None = None,
) -> list[str]:
    """Plan-Step references a step; Plan-Done claims it complete, and must be proved."""
    if is_merge:
        return []
    pairs = _trailers(_as_stored(message))
    named = [value for key, value in pairs if key.lower() == KEY.lower()]
    done = [value for key, value in pairs if key.lower() == DONE.lower()]
    if not named and not done:
        return [
            f"no {KEY} or {DONE} trailer: end the message with the plan steps it serves, "
            f"e.g. '{KEY}: G.29'"
        ]
    out = [
        f"{KEY}: {value} is not a step or decision in the plan"
        for value in named
        if value not in ids
    ]
    out += [f"{DONE}: {value} is not a step in the plan" for value in done if value not in ids]
    if holds is not None:
        for value in done:
            if value in ids and (reason := holds(value)):
                out.append(
                    f"{DONE}: {value} claims a step whose evidence does not hold -- {reason}"
                )
    return out


def plan_steps(root: Path, ref: str) -> frozenset[str]:
    """Step and decision ids in the plan at ref; ':' is the staged plan."""
    path = f"{ref}context/plan.yaml" if ref == ":" else f"{ref}:context/plan.yaml"
    shown = git("show", path, cwd=root)
    if shown.returncode != 0:
        return frozenset()
    plan = parse_yaml(shown.stdout, ProjectPlan)
    return frozenset(s.id for s in plan.steps) | frozenset(d.id for d in plan.decisions)


def commits_since_cutoff(root: Path) -> list[tuple[str, str, bool]]:
    """(sha, message, is_merge) for every commit from the cutoff to HEAD, inclusive."""
    shown = git("log", "--format=%H%x00%P%x00%B%x1e", f"{CUTOFF}^..HEAD", cwd=root)
    if shown.returncode != 0:
        raise SystemExit(f"cannot read history since {CUTOFF}: {shown.stderr.strip()}")
    out: list[tuple[str, str, bool]] = []
    for record in shown.stdout.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, parents, message = record.split("\x00", 2)
        out.append((sha, message, len(parents.split()) > 1))
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SystemExit("usage: python -m otsafety_tooling.policy.trailers <commit-message-file>")
    message = Path(argv[0]).read_text(encoding="utf-8")
    merge_head = git("rev-parse", "--git-path", "MERGE_HEAD", cwd=REPO_ROOT).stdout.strip()
    staged = git("show", ":context/plan.yaml", cwd=REPO_ROOT)
    plan = parse_yaml(staged.stdout, ProjectPlan) if staged.returncode == 0 else None
    facts = staged_facts(REPO_ROOT)

    def holds(step: str) -> str | None:
        return None if plan is None else ("; ".join(unmet(plan, facts, step)) or None)

    ids = plan_steps(REPO_ROOT, ":")
    found = problems(message, ids, is_merge=(REPO_ROOT / merge_head).exists(), holds=holds)
    if found:
        print("refusing: " + "; ".join(found), file=sys.stderr)  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
