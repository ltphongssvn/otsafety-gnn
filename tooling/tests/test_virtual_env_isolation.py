# tooling/tests/test_virtual_env_isolation.py
"""A child process spawned into another checkout inherits no virtual environment.

WHY THIS EXISTS. worktree:add runs setup in the new checkout. The task runs under
uv run, which exports VIRTUAL_ENV and puts its .venv/bin first on PATH -- both
the ORIGINATING checkout's. run_setup spawned mise with no env=, so the new
checkout's setup saw them: uv warned three times, and a uv pip install there
would have written into the other checkout's environment without a word. 2026
practice: "the fix is a clean environment rather than a suppressed warning", and
"unsetting is the only option". scrubbed_env() now removes VIRTUAL_ENV,
UV_PROJECT_ENVIRONMENT and that environment's bin from PATH, and every subprocess
call in tooling/src names its environment, so none can inherit one by omission.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from otsafety_tooling.git.env import scrubbed_env
from otsafety_tooling.git.worktree import run_setup
from otsafety_tooling.paths import REPO_ROOT

# THIS FILE PROVES G.22: the claim the requirement matrix joins on.
pytestmark = pytest.mark.requirement("G.22")

ELSEWHERE = "/elsewhere/checkout/.venv"
CALLS = {"run", "Popen", "call", "check_call", "check_output"}


def test_scrubbed_env_removes_an_inherited_virtual_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = scrubbed_env()["PATH"]
    monkeypatch.setenv("VIRTUAL_ENV", ELSEWHERE)
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", ELSEWHERE)
    monkeypatch.setenv("PATH", f"{ELSEWHERE}/bin:{original}")
    env = scrubbed_env()
    assert "VIRTUAL_ENV" not in env and "UV_PROJECT_ENVIRONMENT" not in env
    assert f"{ELSEWHERE}/bin" not in env["PATH"].split(":")


def test_setup_in_a_new_checkout_sees_no_inherited_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake, out = tmp_path / "bin", tmp_path / "seen"
    fake.mkdir()
    (fake / "mise").write_text(
        '#!/bin/sh\nprintf "%s|%s" "${VIRTUAL_ENV-}" "$PATH" > "$PROBE_OUT"\n', encoding="utf-8"
    )
    (fake / "mise").chmod(0o755)
    original = scrubbed_env()["PATH"]
    monkeypatch.setenv("PROBE_OUT", str(out))
    monkeypatch.setenv("VIRTUAL_ENV", ELSEWHERE)
    monkeypatch.setenv("PATH", f"{ELSEWHERE}/bin:{fake}:{original}")
    run_setup(tmp_path)
    venv, path = out.read_text(encoding="utf-8").split("|", 1)
    assert venv == "" and f"{ELSEWHERE}/bin" not in path.split(":")


def test_every_subprocess_call_names_its_environment() -> None:
    """The gate: a call with no env= inherits whatever the caller had, silently."""
    silent = []
    for path in sorted((REPO_ROOT / "tooling" / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in CALLS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and not any(k.arg == "env" for k in node.keywords)
            ):
                silent.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert silent == []
