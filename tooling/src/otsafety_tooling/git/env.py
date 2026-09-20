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
        capture_output=True,
        text=True,
        check=False,
    )
    return listing.stdout.split() if listing.returncode == 0 else None


def scrubbed_env() -> dict[str, str]:
    """A copy of the environment with git's repository-local variables removed.

    FAILS CLOSED ON THE FALLBACK. If git cannot enumerate the variables, every
    GIT_ name is removed rather than a guessed subset: over-removing makes git
    resolve from cwd, which is what the caller asked for.
    """
    environment = dict(os.environ)
    names = _local_env_var_names()

    if names is None:
        return {key: value for key, value in environment.items() if not key.startswith("GIT_")}

    for name in names:
        environment.pop(name, None)

    return environment


def routing_overrides_present() -> dict[str, str]:
    """Which ROUTING variables are set right now, for diagnostics.

    A hijack that is silently corrected is still worth being able to see.
    NON_ROUTING_VARS is excluded so an ordinary hook run reports nothing.
    """
    names = _local_env_var_names()
    if names is None:
        names = [key for key in os.environ if key.startswith("GIT_")]
    return {
        name: os.environ[name]
        for name in names
        if name in os.environ and name not in NON_ROUTING_VARS
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
