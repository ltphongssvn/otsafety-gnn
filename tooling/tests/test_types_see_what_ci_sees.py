# tooling/tests/test_types_see_what_ci_sees.py
"""The type check sees the same packages on every machine (G.30).

THE LAPTOP AND THE RUNNER CHECKED DIFFERENT ENVIRONMENTS. The laptop's .venv
had every optional extra installed; the runner type-checks before installing
any. So an optional import nobody declared to mypy passed here and failed
there -- every time, after the push. The override list grew five times that
way, each entry added after a red runner, which is the treadmill.

ONE ENVIRONMENT, BUILT FROM THE LOCK. The type check runs in an isolated
environment holding every workspace member and no extras -- exactly what the
runner has -- so a missing declaration fails on the laptop, before the push.
The working .venv, with its extras, is untouched.

EVERY WORKSPACE MEMBER, NOT JUST TOOLING. A first attempt built the isolated
environment from tooling/ alone and missed python/otsafety, reporting an error
the runner never sees. A check disagreeing with CI in the other direction gets
bypassed just as surely.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.30")


def _type_runs() -> list[str]:
    """Every mypy invocation in the types task.

    ALL OF THEM, NOT THE TWO OVER tooling. The third checks scripts/ and
    apps/site/tests, which import Playwright from an extra -- the same
    mismatch in a place a narrower rule would have left alone.
    """
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig
    from otsafety_tooling.paths import REPO_ROOT

    run = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["types"].run or ""
    commands = (run,) if isinstance(run, str) else run
    return [
        line
        for command in commands
        for line in command.splitlines()
        if line.startswith("uv run") and "mypy" in line
    ]


def test_the_type_check_runs_somewhere() -> None:
    """THE CONTROL: no matching line would make every rule below vacuous."""
    assert len(_type_runs()) == 3, "expected two tooling runs and one over scripts"


def test_the_type_check_builds_an_isolated_environment() -> None:
    """Not the working .venv, whose extras the runner never has."""
    for line in _type_runs():
        assert "--isolated" in line, f"checks the working environment: {line}"
        assert "--no-sync" not in line, f"reuses the working environment: {line}"


def test_every_workspace_member_is_present() -> None:
    """The runner installs the whole workspace; so must the check."""
    for line in _type_runs():
        assert "--all-packages" in line, f"misses a workspace member: {line}"
        if "--directory tooling" in line:
            assert "--project .." in line, f"discovers the project from tooling/ alone: {line}"


def test_no_optional_extra_is_installed_for_it() -> None:
    """THE POINT: the runner type-checks before any extra, so this must too."""
    for line in _type_runs():
        assert "--extra" not in line and "--all-extras" not in line, line


def test_it_stays_offline_and_holds_the_lock() -> None:
    """No gate reaches the network, and none may resolve anything new."""
    for line in _type_runs():
        assert "--offline" in line, f"may reach the network: {line}"
        assert "--frozen" in line, f"may resolve past the lock: {line}"


def test_the_runner_installs_through_a_task_not_around_one() -> None:
    """ONE CACHE FOR THE INSTALL AND THE GATES.

    The workflow ran uv sync as a raw command, outside mise, so on the runner
    it wrote to uv's default cache while every gate -- run through mise under
    the ood profile -- read UV_CACHE_DIR from inside the checkout. Two steps of
    one job, two caches: the offline type check found none of the wheels the
    install had just downloaded. The workflow's own header already names the
    rule this broke -- through the tasks, not around them.
    """
    from otsafety_tooling.paths import REPO_ROOT

    workflow = (REPO_ROOT / ".github" / "workflows" / "test-tooling.yml").read_text(
        encoding="utf-8"
    )
    commands = [
        line.strip()
        for line in workflow.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert "run: mise run deps:install" in commands, "the environment is not installed by task"
    raw = [line for line in commands if "uv sync" in line]
    assert raw == [], f"an install bypasses mise and its cache: {raw}"


def test_the_install_task_holds_the_lock() -> None:
    """The task installs exactly what the lock names, resolving nothing."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig
    from otsafety_tooling.paths import REPO_ROOT

    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["deps:install"]
    run = task.run if isinstance(task.run, str) else " ".join(task.run or ())
    assert "uv sync --frozen" in run
