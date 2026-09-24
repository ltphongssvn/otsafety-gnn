# tooling/tests/test_gates_are_bounded.py
"""No gate reaches the network, and every gate is bounded in time (G.47).

WHAT THIS PROVES. eslint-effective.ts imports eslint. In a worktree where setup
has not run there is no node_modules, so bun resolved that import by
AUTO-INSTALLING from the registry and stayed there for forty-one minutes with an
HTTP client thread open -- holding check_all, printing nothing, returning no
prompt. A network fetch has no time bound, and subprocess.run carried no timeout.

TWO GUARDS, BECAUSE ONE WOULD ONLY FIX THIS FETCH. The bunfig makes a missing
dependency an error in under a second; the bound makes the NEXT hang, whatever it
is, report as that gate failing within ten minutes rather than silently forever.
"""

from __future__ import annotations

import ast
import subprocess

import pytest

from otsafety_tooling.contracts.bunfig import BunfigFile
from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.47")


def test_the_site_cannot_reach_the_registry_from_a_gate() -> None:
    """A GATE THAT CAN FETCH CAN HANG. Bun's documentation states the mechanism: with
    no node_modules it abandons Node-style resolution and AUTO-INSTALLS every
    imported package on the fly, falling back to `latest` from the registry. That is
    what held check_all for forty-one minutes with an HTTP client thread open,
    printing nothing. auto = "disable" is the documented off switch, and with
    node_modules moved aside the script now exits in under a second.

    offline WAS TOO BROAD, AND CI SAID SO. It applies to `bun install` as well, so
    the workflow's own install step refused every package on a runner with an empty
    cache. Installing must reach the registry; resolving an import while a gate runs
    must not. 2026 hardening practice agrees: frozenLockfile in bunfig, a frozen
    lockfile on the CI install, and no offline.
    """
    settings = read_toml(REPO_ROOT / "apps" / "site" / "bunfig.toml", BunfigFile).install
    assert settings.auto == "disable", "auto-install turns a missing import into a fetch"
    assert settings.frozen_lockfile is True, "a stale lockfile fails rather than resolving anew"
    assert settings.offline is False, "offline would break the install step that fills the cache"


def test_every_gate_carries_a_timeout() -> None:
    """A gate with no bound can hang the whole check and print nothing while it does."""
    source = (REPO_ROOT / "scripts" / "check_all.py").read_text(encoding="utf-8")
    runs = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and (
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        )
        == "run"
    ]
    assert runs, "check_all runs no subprocess at all, which cannot be right"
    for node in runs:
        assert any(keyword.arg == "timeout" for keyword in node.keywords), (
            f"check_all.py:{node.lineno}: an unbounded gate can hang the whole check"
        )


def test_a_timeout_is_a_failure_not_an_exception() -> None:
    """An exception here would discard every other gate's verdict, which is the
    failure this aggregate was written to prevent."""
    source = (REPO_ROOT / "scripts" / "check_all.py").read_text(encoding="utf-8")
    handlers = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler)
        and "TimeoutExpired" in ast.unparse(node.type or ast.Constant(value=None))
    ]
    assert handlers, "a timeout must be caught and reported as that gate failing"
    assert subprocess.TimeoutExpired is not None
