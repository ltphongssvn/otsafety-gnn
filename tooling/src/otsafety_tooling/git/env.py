# tooling/src/otsafety_tooling/git/env.py
"""A git environment that cannot be redirected by an inherited GIT_DIR.

THE PROBLEM, IN GIT'S OWN WORDS
"Environment variables, such as GIT_DIR, GIT_WORK_TREE, etc., are exported so
that Git commands run by the hook can correctly locate the repository. If your
hook needs to invoke Git commands in a foreign repository or in a different
working tree of the same repository, then it should clear these environment
variables so they do not interfere with Git operations at the foreign location."

Those variables OVERRIDE both `-C` and `cwd`, so any git call made from inside
a hook operates on the hook's repository regardless of where it was pointed.

WHY THIS REPOSITORY IS EXPOSED. Its hooks run from the laptop, from Lightning
AI and from FAS OnDemand, and from linked worktrees on each. Where a hook's
repository and the target differ, a raw subprocess call reads the wrong one --
passing while inspecting something else. In cscie103-olap-oltp the same
inheritance let a test fixture's `git commit` write into the real repository.

WHY `git rev-parse --local-env-vars` RATHER THAN A HARDCODED LIST
It is git's own enumeration, so it stays correct when git adds a variable. A
literal list is a second copy of something git already owns.

Ported from cscie103-olap-oltp (src/cscie103_olap_oltp/git/env.py).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# NOT EVERY LOCAL ENV VAR IS A ROUTING OVERRIDE. git exports GIT_PREFIX on every
# hook invocation (usually empty) to record the subdirectory a command ran from.
# It is still scrubbed, but reporting it as a hijack would make the diagnostic
# fire on the most ordinary hook run, which trains people to ignore it.
NON_ROUTING_VARS = frozenset({"GIT_PREFIX"})


def _local_env_var_names() -> list[str] | None:
    """Git's own enumeration of the repository-local variables, or None."""
    listing = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],  # noqa: S607
        env=inherited_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    return listing.stdout.split() if listing.returncode == 0 else None


def inherited_env() -> dict[str, str]:
    """The caller's environment, copied whole: named, so no child inherits it by omission."""
    return dict(os.environ)  # noqa: TID251


def scrubbed_env() -> dict[str, str]:
    """A copy of the environment, safe for a child that may run in another checkout.

    Git's repository-local variables are removed, so git resolves from cwd. FAILS
    CLOSED ON THE FALLBACK: if git cannot enumerate them, every GIT_ name goes.

    AN INHERITED VIRTUAL ENVIRONMENT IS REMOVED TOO. uv run exports VIRTUAL_ENV and
    puts its .venv/bin first on PATH, both the calling checkout's; a child spawned
    into another checkout would otherwise warn, find the wrong tools first, and --
    under uv pip -- install into the wrong environment silently.
    """
    environment = inherited_env()
    names = _local_env_var_names()
    if names is None:
        environment = {
            key: value for key, value in environment.items() if not key.startswith("GIT_")
        }
    else:
        for name in names:
            environment.pop(name, None)
    venv = environment.pop("VIRTUAL_ENV", None)
    environment.pop("UV_PROJECT_ENVIRONMENT", None)
    if venv:
        kept = [entry for entry in environment.get("PATH", "").split(":") if entry != f"{venv}/bin"]
        environment["PATH"] = ":".join(kept)
    return environment


def routing_overrides_present() -> dict[str, str]:
    """Which ROUTING variables are set right now, for diagnostics.

    A hijack that is silently corrected is still worth being able to see.
    NON_ROUTING_VARS is excluded so an ordinary hook run reports nothing.
    """
    names = _local_env_var_names()
    if names is None:
        names = [key for key in os.environ if key.startswith("GIT_")]  # noqa: TID251
    return {
        name: os.environ[name]  # noqa: TID251
        for name in names
        if name in os.environ and name not in NON_ROUTING_VARS  # noqa: TID251
    }


def git(*args: str, cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run git with a scrubbed environment, resolving the repository from cwd.

    check=False DELIBERATELY. Callers inspect returncode and stderr to decide
    what a failure MEANS; an exception collapses every cause into a traceback.

    S603 IS SUPPRESSED NARROWLY: `*args` makes the list computed. Call sites
    pass subcommands and refs as separate arguments, and there is no shell.
    """
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=scrubbed_env(),
    )
