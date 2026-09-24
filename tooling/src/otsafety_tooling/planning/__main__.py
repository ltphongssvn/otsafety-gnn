# tooling/src/otsafety_tooling/planning/__main__.py
"""plan:status -- observe the plan on the integration branch, record it, print it."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.cli import note, result
from otsafety_tooling.contracts.files import parse_yaml
from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.render import render
from otsafety_tooling.planning.status import derive, gather_facts

REF = "origin/develop"


class PlanObserved(BaseModel):
    """What the observation found, and where it was recorded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    steps: int
    done: int
    record: str


def main() -> int:
    fetched = git("fetch", "origin", "--prune", "--tags", "--quiet", cwd=REPO_ROOT)
    if fetched.returncode != 0:
        raise SystemExit(f"could not fetch from origin: {fetched.stderr.strip()}")
    shown = git("show", f"{REF}:context/plan.yaml", cwd=REPO_ROOT)
    if shown.returncode != 0:
        raise SystemExit(f"no context/plan.yaml on {REF}")
    plan = parse_yaml(shown.stdout, ProjectPlan)
    status = derive(plan, gather_facts(REPO_ROOT, REF))
    folder = artifacts_root(REPO_ROOT) / "plan-status"
    folder.mkdir(parents=True, exist_ok=True)
    record = folder / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    record.write_text(status.model_dump_json(), encoding="utf-8")
    note(render(plan, status))
    note(f"recorded: {record}")
    done = sum(1 for step in status.steps if step.state == "done")
    return result(
        "plan:status",
        "success",
        "status_observed",
        f"{done} of {len(status.steps)} steps done at {status.ref[:9]}",
        PlanObserved(ref=status.ref, steps=len(status.steps), done=done, record=str(record)),
    )


if __name__ == "__main__":
    raise SystemExit(main())
