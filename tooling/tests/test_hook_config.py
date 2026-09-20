# tooling/tests/test_hook_config.py
"""Repository configuration that other machines depend on, checked by tests.

WHY THESE ARE TESTS FOR NOW. Until the repository policy (Rego) exists, these
keep committed configuration from being removed or weakened unnoticed:

  - the git hooks run the checkout's locked lefthook, whatever PATH holds (a
    global mise lefthook 2.1.10 once sat first on PATH, shadowing uv.lock's
    2.1.14);
  - bytecode, IDE settings and run artifacts never reach a commit;
  - new branches start without an upstream;
  - the test task can run a single file during the TDD inner loop, while hooks
    and CI still run the whole suite;
  - no task script contains Tera comment syntax;
  - the branch report runs as a task, like every other operation;
  - the shared evidence root is available to shell commands as a task;
  - repository settings are checked and applied through tasks;
  - merged remote branches are pruned through a task that only plans unless
    told to apply;
  - any task can be run with its execution recorded as data;
  - returning to an existing branch is a task, like creating one;
  - continuous integration runs the same three gates, through the same tasks;
  - every Python file in the repository is covered by those gates;
  - the cluster's package cache shares a filesystem with the environment.

.artifacts/ IS THE SHARED SCRATCH AND EVIDENCE LOCATION. PR bodies, commit
messages, gate logs and run records are written there instead of /tmp, which
is private to snap-confined tools, per-session on FAS OnDemand, and gone with a
container. The rule lives in the committed .gitignore, not in
.git/info/exclude, so every clone -- teammates, Lightning AI, FAS OnDemand --
gets the same location with no per-machine setup.

MISE RENDERS EVERY TASK SCRIPT AS A TERA TEMPLATE before bash runs it, and in
Tera `{#` opens a comment. The bash array length `${#paths[@]}` therefore made
the test task fail with "Closing comment tag `#}` not found" before bash saw a
single line.
"""

import tomllib
from typing import Any

from otsafety_tooling.paths import REPO_ROOT

PINNED = """lefthook: '"$(git rev-parse --show-toplevel)/.venv/bin/lefthook"'"""


def _config() -> list[str]:
    return (REPO_ROOT / "lefthook.yml").read_text(encoding="utf-8").splitlines()


def _gitignore() -> list[str]:
    return (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def _tasks() -> dict[str, Any]:
    document = tomllib.loads((REPO_ROOT / "mise.toml").read_text(encoding="utf-8"))
    tasks: dict[str, Any] = document["tasks"]
    return tasks


def _scripts(task: dict[str, Any]) -> list[str]:
    """A task's run value as a list of scripts; mise accepts a string or a list."""
    run = task.get("run", [])
    return [run] if isinstance(run, str) else list(run)


def test_hooks_call_the_checkouts_locked_lefthook() -> None:
    assert PINNED in _config()


def test_a_missing_lefthook_fails_the_hook() -> None:
    """Without this, a hook whose executable is missing runs nothing and passes."""
    assert "assert_lefthook_installed: true" in _config()


def test_lefthook_is_pinned_exactly_in_the_workspace() -> None:
    """The executable the hooks run must be one exact, locked version."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"lefthook==' in pyproject


def test_bytecode_is_written_outside_the_source_tree() -> None:
    """PYTHONPYCACHEPREFIX keeps __pycache__ from being created beside modules."""
    mise = (REPO_ROOT / "mise.toml").read_text(encoding="utf-8")
    assert 'PYTHONPYCACHEPREFIX = "{{config_root}}/.cache/pycache"' in mise


def test_the_root_gitignore_covers_python_artifacts() -> None:
    """The first layer: a directory commit must not see bytecode at all."""
    lines = _gitignore()
    for pattern in (".cache/", "__pycache__/", "*.py[cod]"):
        assert pattern in lines


def test_start_here_creates_branches_without_an_upstream() -> None:
    """Same rule as worktree:add: only `pr` sets an upstream, by pushing."""
    mise = (REPO_ROOT / "mise.toml").read_text(encoding="utf-8")
    assert "git switch --no-track -c feature/$slug origin/develop" in mise


def test_ide_settings_are_ignored() -> None:
    assert ".idea/" in _gitignore()


def test_run_artifacts_are_ignored_by_the_committed_gitignore() -> None:
    """Every clone shares one scratch and evidence location, never committed."""
    assert ".artifacts/" in _gitignore()


def test_the_gitignore_names_its_own_path() -> None:
    """Every file opens with its repository path, for tracking."""
    assert _gitignore()[0] == "# .gitignore"


def test_the_test_task_accepts_optional_paths_defaulting_to_the_whole_suite() -> None:
    """The TDD inner loop runs one file; hooks and CI, passing none, run everything."""
    test = _tasks()["test"]
    assert 'arg "[paths]..."' in test["usage"]
    assert "paths=(tooling)" in test["run"]


def test_no_task_script_opens_a_tera_comment() -> None:
    """`{#` starts a Tera comment, so mise cannot render a script containing it."""
    offending = sorted(
        name for name, task in _tasks().items() if any("{#" in script for script in _scripts(task))
    )
    assert offending == []


def test_the_branches_task_records_the_branch_report() -> None:
    """Every operation is a task, so the report never needs a raw interpreter call."""
    assert _tasks()["branches"]["run"] == "uv run python -m otsafety_tooling.git.branches"


def test_the_artifacts_path_task_prints_the_shared_evidence_root() -> None:
    """Shell commands in any worktree write logs where worktree removal cannot reach."""
    assert _tasks()["artifacts:path"]["run"] == "uv run python -m otsafety_tooling.artifacts"


def test_repository_settings_are_checked_and_applied_through_tasks() -> None:
    """contracts/repository-settings.json is enforced by commands, never by clicks."""
    tasks = _tasks()
    module = "uv run python -m otsafety_tooling.github.settings"
    assert tasks["repo:check"]["run"] == f"{module} check"
    assert tasks["repo:configure"]["run"] == f"{module} configure"


def test_pruning_plans_unless_explicitly_told_to_apply() -> None:
    """Deleting shared branches needs a deliberate flag; the default is a plan."""
    prune = _tasks()["branches:prune"]
    assert 'flag "--apply"' in prune["usage"]
    script = prune["run"]
    assert "uv run python -m otsafety_tooling.git.prune --apply" in script
    assert 'if [ "${usage_apply-}" = "true" ]; then' in script


def test_any_task_can_be_run_with_its_execution_recorded() -> None:
    """`mise run run <task> [args]` records run-record/v1 and returns the exit code."""
    wrapper = _tasks()["run"]
    assert 'arg "<task>"' in wrapper["usage"]
    assert 'arg "[arguments]..."' in wrapper["usage"]
    assert "uv run python -m otsafety_tooling.runs" in wrapper["run"]


def test_returning_to_an_existing_branch_is_a_task() -> None:
    """start:here creates a branch; start:switch moves to one that exists."""
    switch = _tasks()["start:switch"]
    assert 'arg "<branch>"' in switch["usage"]
    assert "otsafety_tooling.git.sync switch" in switch["run"]


def _tooling_workflow() -> str:
    return (REPO_ROOT / ".github" / "workflows" / "test-tooling.yml").read_text(encoding="utf-8")


def test_continuous_integration_runs_the_tooling_gates() -> None:
    """335 tests had never run on GitHub; a Linux-only regression could merge.

    FAS OnDemand caught exactly such a bug by running them on Linux by hand.
    CI runs the same three gates, through the same tasks, so the definition of
    "passing" cannot differ between a laptop, a cluster and a runner.
    """
    workflow = _tooling_workflow()
    for gate in ("mise run lint", "mise run types", "mise run test"):
        assert gate in workflow, f"the workflow does not run `{gate}`"


def test_continuous_integration_bootstraps_from_the_committed_script() -> None:
    """The runner installs the toolchain the same way every other machine does."""
    assert "scripts/bootstrap.sh" in _tooling_workflow()


def test_the_tooling_workflow_runs_on_pull_requests() -> None:
    workflow = _tooling_workflow()
    assert "pull_request:" in workflow
    assert "runs-on: ubuntu-latest" in workflow


def test_the_gates_cover_every_python_directory() -> None:
    """scripts/ was checked by CI alone, so its failures appeared after a push.

    The bootstrap script failed the repository's own pre-commit job twice for
    reasons no local gate could report. ruff resolves configuration per file, so
    naming the directory here keeps tooling at its own width and scripts at the
    one that governs it.
    """
    tasks = _tasks()
    for directory in ("scripts", "apps/site/tests"):
        for gate in ("lint", "fmt"):
            assert directory in tasks[gate]["run"], f"the {gate} task does not cover {directory}/"
        assert directory in tasks["types"]["run"], f"the types task does not cover {directory}/"


def test_the_cluster_keeps_its_package_cache_beside_the_environment() -> None:
    """FAS OnDemand copied all 81 wheels instead of hardlinking them.

    uv reported that the cache and the target were on different filesystems,
    which cost two minutes nineteen and twice the disk. A cache inside the
    checkout shares the filesystem with .venv.
    """
    ood = (REPO_ROOT / "mise.ood.toml").read_text(encoding="utf-8")
    assert "UV_CACHE_DIR" in ood
