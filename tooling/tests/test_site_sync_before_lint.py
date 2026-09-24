# tooling/tests/test_site_sync_before_lint.py
"""The site's generated types exist before anything type-aware reads them (G.51).

WHAT HAPPENED. site:lint rejected content.config.ts with twenty-one no-unsafe
errors in a fresh worktree, and passed in the one it was written in. Astro writes
the types for astro:content and its environment ONLY when it syncs or builds, so
a checkout where nothing has synced has no .astro/types.d.ts -- and tsconfig.json
includes that file. Every import from astro:content then resolves to an error
type, and every type-aware rule fires.

WHY IT LOOKED FINE. site:types runs astro check, which syncs on its way past, so
any order that happened to run it first left the types in place for the linter.
The pre-commit hook runs site:lint alone. The ordering was accidental, and an
accident that holds on a developer's machine and breaks on a clean checkout is
the same shape as a gate that passed because node_modules was stale.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig, MiseTask
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.51")

TYPE_AWARE = ("site:lint", "site:types")


def _task(name: str) -> MiseTask:
    return read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks[name]


def _run(name: str) -> str:
    task = _task(name)
    return task.run if isinstance(task.run, str) else "\n".join(task.run)


def test_every_type_aware_site_task_syncs_first() -> None:
    """A task that reads astro:content types must generate them first.

    THE TASK'S OWN BODY, NOT A DECLARED DEPENDENCY. MiseTask models description,
    run and usage: mise's depends is not in the contract, so a test asking about
    it would be asserting on something the repository does not describe. Each
    task therefore runs the sync itself, which is also what makes it safe to run
    alone -- the pre-commit hook runs site:lint with nothing before it.
    """
    for name in TYPE_AWARE:
        body = _run(name)
        assert "site:sync" in body or "astro sync" in body, (
            f"{name}: nothing generates .astro/types.d.ts before it reads them"
        )


def test_the_sync_task_exists_and_only_syncs() -> None:
    """One task generates the types, so no caller repeats the command."""
    body = _run("site:sync")
    assert "astro sync" in body, "site:sync must generate Astro's types"
