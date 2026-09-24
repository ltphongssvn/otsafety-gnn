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
    settings = read_toml(REPO_ROOT / "apps" / "site" / "bunfig.toml", BunfigFile).install
    assert settings.auto == "disable", "auto-install turns a missing dependency into a fetch"
    assert settings.offline is True, "the registry is not reachable while a gate runs"
    assert settings.frozen_lockfile is True, "a stale lockfile fails rather than resolving anew"


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
