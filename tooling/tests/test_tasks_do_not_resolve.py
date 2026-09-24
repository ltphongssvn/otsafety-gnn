# tooling/tests/test_tasks_do_not_resolve.py
"""No task modifies a tracked file merely by starting (G.50).

WHAT HAPPENED. mise run sync could not fast-forward a checkout eleven commits
behind. Its own `uv run` reconciled the lockfile against the current
pyproject.toml before the module started, adding a package the older lock did
not carry, and the merge then aborted on the change uv had just made. The task
was unable to run on exactly the checkout that needed it, and each diagnostic
command reproduced the condition it was diagnosing.

THE RULE. A task that reads or moves the repository runs frozen: uv uses the
environment as it is and resolves nothing. Only a task whose PURPOSE is to
change dependencies may resolve, and those are named here so the exception is
visible rather than assumed.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig, MiseTask
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.50")

# THE ONLY TASKS ALLOWED TO RESOLVE: each exists to change what is installed.
MAY_RESOLVE = frozenset({"setup", "ml:install", "wandb:install", "e2e:install"})


def _lines(task: MiseTask) -> list[str]:
    """Every uv invocation a task makes, however its run block is written."""
    run = task.run if isinstance(task.run, str) else "\n".join(task.run)
    return [line.strip() for line in run.splitlines() if "uv run" in line]


def test_every_task_that_is_not_installing_runs_frozen() -> None:
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    for name, task in tasks.items():
        if name in MAY_RESOLVE:
            continue
        for line in _lines(task):
            assert "--no-sync" in line or "--frozen" in line, (
                f"{name}: `{line}` may re-resolve and dirty uv.lock before the task starts"
            )


def test_the_installing_tasks_are_the_only_exceptions() -> None:
    """A name kept here after its task stopped installing would be a silent hole."""
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    for name in MAY_RESOLVE:
        assert name in tasks, f"{name} is declared an exception and no longer exists"
