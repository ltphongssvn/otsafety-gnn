# tooling/src/otsafety_tooling/planning/__main__.py
"""plan:status -- observe the plan on the integration branch, record it, print it."""

from __future__ import annotations

from datetime import UTC, datetime

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.contracts.files import parse_yaml
from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.planning.render import render
from otsafety_tooling.planning.status import derive, gather_facts

REF = "origin/develop"


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
    print(render(plan, status))  # noqa: T201 -- this is the command's output
    print(f"\nrecorded: {record}")  # noqa: T201 -- this is the command's output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
