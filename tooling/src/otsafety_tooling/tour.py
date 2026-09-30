# tooling/src/otsafety_tooling/tour.py
"""One command that shows the repository, so nothing has to be remembered first.

SIXTY-SIX TASKS, ALPHABETICAL, IS A WALL. mise tasks prints every name and
description, which is honest and unusable cold: nothing says which three to run
first, which only read, and which deploy or tag something. 2026 practice met the
same problem at twenty-five tasks and regrouped them by the segment before the
first colon.

THE CONTENT IS IN THE OUTPUT. A command that told its reader to consult the
documentation first was followed none of eight times, so this prints what a
reader needs rather than where to find it.

DERIVED FROM mise.toml, never listed by hand: a task added tomorrow appears
without anyone remembering, and G.67 already refuses a task no plan step claims.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.paths import REPO_ROOT

# WHAT CHANGES SOMETHING OUTSIDE THIS CHECKOUT. A demonstration needs to know
# what is safe to run in front of someone: everything else only reads.
CHANGES_THE_WORLD = frozenset(
    {
        "commit",
        "commit:undo",
        "commit:unstage",
        "pr",
        "pr:merge",
        "deploy:site",
        "deps:merge",
        "release:promote",
        "release:version",
        "repo:configure",
        "sync",
        "branches:prune",
        "worktree:add",
        "worktree:remove",
        "worktree:refresh",
        "start:here",
        "start:switch",
        "setup",
        "deps:lock",
        "site:lock",
        "site:install",
        "e2e:install",
        "ml:install",
        "wandb:install",
        "wandb:sync",
        "contracts:generate",
        "fmt",
        "policy:inputs",
        "sheet:facts",
    }
)

# WHERE TO START: three commands, not sixty-six.
START_HERE: tuple[tuple[str, str], ...] = (
    ("mise run plan:report", "every step in every phase, with what is done and what each waits on"),
    ("mise run check", "all ten gates in one pass, every failure reported rather than the first"),
    ("mise run status", "this branch, its working tree, and how it stands against develop"),
)

# WHAT EACH GROUP IS FOR, so a heading says more than a prefix.
ABOUT: dict[str, str] = {
    "": "the daily loop",
    "plan": "the plan: intent, status observed from evidence, and the report",
    "policy": "the rules, proved present rather than remembered",
    "contracts": "Pydantic to JSON Schema to the site's Zod, drift-gated",
    "site": "the website: build, types, lint and its browser tests",
    "pdf": "the architecture sheet, rendered in a pinned image",
    "worktree": "sibling checkouts, one per branch",
    "start": "moving this shell between branches",
    "commit": "committing, and undoing what is not yet pushed",
    "pr": "pull requests and why CI refused",
    "release": "cutting a version from main",
    "deploy": "the live site",
    "repo": "GitHub's own settings, as a contract",
    "secrets": "scanning for credentials",
    "toolchain": "proving every tool is the pinned binary",
    "nix": "the reproducible environment",
    "deps": "dependency resolution",
    "branches": "branch state as data",
    "wandb": "Weights and Biases, beside MLflow",
    "ml": "the machine-learning extra",
    "e2e": "the browser the acceptance tests drive",
    "artifacts": "where evidence is written",
    "sheet": "what the architecture sheet reports, collected",
    "test": "the tests, hermetic and in a real browser",
}


def reads_only(task: str) -> bool:
    """Whether running this changes nothing outside the checkout."""
    return task not in CHANGES_THE_WORLD


def groups(tasks: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    """Tasks by the segment before the first colon, ungrouped ones under 'core'."""
    found: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name in sorted(tasks):
        prefix = name.split(":")[0] if ":" in name else "core"
        found[prefix].append((name, tasks[name]))
    return dict(found)


def render(root: Path = REPO_ROOT) -> str:
    """The whole repository, as something a person can read once."""
    declared = {
        name: (task.description or "")
        for name, task in read_toml(root / "mise.toml", MiseConfig).tasks.items()
    }
    out: list[str] = []
    rule = "=" * 100
    out.append(rule)
    out.append("  otsafety-gnn -- every command this repository offers")
    out.append(rule)
    out.append("  Does a biomedical knowledge graph predict drug-safety endpoints for protein")
    out.append("  targets beyond what node popularity alone explains? A negative result is a")
    out.append("  real finding here, and the apparatus is built to report one.")
    out.append("")
    out.append("  START HERE")
    for name, why in START_HERE:
        out.append(f"    {name:<26} {why}")
    out.append("")
    out.append("  Anything marked ! changes something outside this checkout.")
    out.append("  Add 'run' to record an execution: mise run run check")
    out.append("")

    for prefix, items in sorted(groups(declared).items()):
        about = ABOUT.get("" if prefix == "core" else prefix, "")
        out.append("-" * 100)
        out.append(f"  {prefix.upper():<14} {about}")
        out.append("-" * 100)
        for name, description in items:
            mark = " " if reads_only(name) else "!"
            out.append(f"  {mark} mise run {name:<20} {description[:63]}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    """Print the tour, and report what it showed."""
    from pydantic import BaseModel, ConfigDict

    from otsafety_tooling.cli import note, result

    class Shown(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")

        tasks: int
        groups: int
        read_only: int

    declared = {
        name: (task.description or "")
        for name, task in read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks.items()
    }
    note(render())
    safe = sum(1 for name in declared if reads_only(name))
    return result(
        "tour",
        "success",
        "tour_shown",
        f"{len(declared)} tasks in {len(groups(declared))} groups, {safe} of them read-only",
        Shown(tasks=len(declared), groups=len(groups(declared)), read_only=safe),
    )


if __name__ == "__main__":
    raise SystemExit(main())
