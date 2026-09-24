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

from otsafety_tooling.contracts.files import read_toml, read_yaml
from otsafety_tooling.contracts.lefthook_config import LefthookConfig
from otsafety_tooling.contracts.mise_config import MiseConfig, MiseOverlay, MiseTask
from otsafety_tooling.contracts.release_config import Pyproject
from otsafety_tooling.contracts.workflow import Workflow
from otsafety_tooling.paths import REPO_ROOT

LOCKED_LEFTHOOK = '"$(git rev-parse --show-toplevel)/.venv/bin/lefthook"'


def _lefthook() -> LefthookConfig:
    return read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig)


def _gitignore() -> list[str]:
    """.gitignore IS a list of patterns, so its lines are its native structure."""
    return (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def _mise() -> MiseConfig:
    return read_toml(REPO_ROOT / "mise.toml", MiseConfig)


def _tasks() -> dict[str, MiseTask]:
    return _mise().tasks


def _script(name: str) -> str:
    return "\n".join(_tasks()[name].scripts)


def _usage(name: str) -> str:
    usage = _tasks()[name].usage
    assert usage is not None, f"the {name} task declares no usage"
    return usage


def test_hooks_call_the_checkouts_locked_lefthook() -> None:
    assert _lefthook().lefthook == LOCKED_LEFTHOOK


def test_a_missing_lefthook_fails_the_hook() -> None:
    """Without this, a hook whose executable is missing runs nothing and passes."""
    assert _lefthook().assert_lefthook_installed is True


def test_lefthook_is_pinned_exactly_in_the_workspace() -> None:
    """The executable the hooks run must be one exact, locked version."""
    dev = read_toml(REPO_ROOT / "pyproject.toml", Pyproject).dependency_groups["dev"]
    assert any(requirement.startswith("lefthook==") for requirement in dev)


def test_bytecode_is_written_outside_the_source_tree() -> None:
    """PYTHONPYCACHEPREFIX keeps __pycache__ from being created beside modules."""
    assert _mise().env["PYTHONPYCACHEPREFIX"] == "{{config_root}}/.cache/pycache"


def test_the_root_gitignore_covers_python_artifacts() -> None:
    """The first layer: a directory commit must not see bytecode at all."""
    lines = _gitignore()
    for pattern in (".cache/", "__pycache__/", "*.py[cod]"):
        assert pattern in lines


def test_ide_settings_are_ignored() -> None:
    assert ".idea/" in _gitignore()


def test_run_artifacts_are_ignored_by_the_committed_gitignore() -> None:
    """Every clone shares one scratch and evidence location, never committed."""
    assert ".artifacts/" in _gitignore()


def test_the_gitignore_names_its_own_path() -> None:
    """Every file opens with its repository path, for tracking."""
    assert _gitignore()[0] == "# .gitignore"


def test_start_here_creates_branches_without_an_upstream() -> None:
    """Same rule as worktree:add: only `pr` sets an upstream, by pushing."""
    assert "git switch --no-track -c feature/$slug origin/develop" in _script("start:here")


def test_the_test_task_accepts_optional_paths_defaulting_to_the_whole_suite() -> None:
    """The TDD inner loop runs one file; hooks and CI, passing none, run everything."""
    assert 'arg "[paths]..."' in _usage("test")
    assert "paths=(tooling)" in _script("test")


def test_no_task_script_opens_a_tera_comment() -> None:
    """`{#` starts a Tera comment, so mise cannot render a script containing it."""
    offending = sorted(
        name for name, task in _tasks().items() if any("{#" in script for script in task.scripts)
    )
    assert offending == []


def test_the_branches_task_records_the_branch_report() -> None:
    """Every operation is a task, so the report never needs a raw interpreter call."""
    assert _script("branches") == "uv run --no-sync python -m otsafety_tooling.git.branches"


def test_the_artifacts_path_task_prints_the_shared_evidence_root() -> None:
    """Shell commands in any worktree write logs where worktree removal cannot reach."""
    assert _script("artifacts:path") == "uv run --no-sync python -m otsafety_tooling.artifacts"


def test_repository_settings_are_checked_and_applied_through_tasks() -> None:
    """contracts/repository-settings.json is enforced by commands, never by clicks."""
    module = "uv run --no-sync python -m otsafety_tooling.github.settings"
    assert _script("repo:check") == f"{module} check"
    assert _script("repo:configure") == f"{module} configure"


def test_pruning_plans_unless_explicitly_told_to_apply() -> None:
    """Deleting shared branches needs a deliberate flag; the default is a plan."""
    assert 'flag "--apply"' in _usage("branches:prune")
    script = _script("branches:prune")
    assert "uv run --no-sync python -m otsafety_tooling.git.prune --apply" in script
    assert 'if [ "${usage_apply-}" = "true" ]; then' in script


def test_any_task_can_be_run_with_its_execution_recorded() -> None:
    """`mise run run <task> [args]` records run-record/v1 and returns the exit code."""
    usage = _usage("run")
    assert 'arg "<task>"' in usage
    assert 'arg "[arguments]..."' in usage
    assert "uv run --no-sync python -m otsafety_tooling.runs" in _script("run")


def test_returning_to_an_existing_branch_is_a_task() -> None:
    """start:here creates a branch; start:switch moves to one that exists."""
    assert 'arg "<branch>"' in _usage("start:switch")
    assert "otsafety_tooling.git.sync switch" in _script("start:switch")


def _tooling_workflow() -> Workflow:
    return read_yaml(REPO_ROOT / ".github" / "workflows" / "test-tooling.yml", Workflow)


def _workflow_runs(workflow: Workflow) -> str:
    return "\n".join(step.run or "" for job in workflow.jobs.values() for step in job.steps)


def test_continuous_integration_runs_the_tooling_gates() -> None:
    """335 tests had never run on GitHub; a Linux-only regression could merge.

    FAS OnDemand caught exactly such a bug by running them on Linux by hand.
    CI runs the same three gates, through the same tasks, so the definition of
    "passing" cannot differ between a laptop, a cluster and a runner.
    """
    runs = _workflow_runs(_tooling_workflow())
    for gate in ("mise run lint", "mise run types", "mise run test"):
        assert gate in runs, f"the workflow does not run `{gate}`"


def test_continuous_integration_bootstraps_from_the_committed_script() -> None:
    """The runner installs the toolchain the same way every other machine does."""
    assert "scripts/bootstrap.sh" in _workflow_runs(_tooling_workflow())


def test_the_tooling_workflow_runs_on_pull_requests() -> None:
    """Read from the parsed workflow: a substring check passed on a matching comment."""
    workflow = _tooling_workflow()
    assert workflow.runs_on("pull_request")
    assert all(job.runs_on == "ubuntu-latest" for job in workflow.jobs.values())


def test_the_gates_cover_every_python_directory() -> None:
    """scripts/ was checked by CI alone, so its failures appeared after a push.

    The bootstrap script failed the repository's own pre-commit job twice for
    reasons no local gate could report. ruff resolves configuration per file, so
    naming the directory here keeps tooling at its own width and scripts at the
    one that governs it.
    """
    for directory in ("scripts", "apps/site/tests"):
        for gate in ("lint", "fmt"):
            assert directory in _script(gate), f"the {gate} task does not cover {directory}/"
        assert directory in _script("types"), f"the types task does not cover {directory}/"


def test_the_cluster_keeps_its_package_cache_beside_the_environment() -> None:
    """FAS OnDemand copied all 81 wheels instead of hardlinking them.

    uv reported that the cache and the target were on different filesystems,
    which cost two minutes nineteen and twice the disk. A cache inside the
    checkout shares the filesystem with .venv.
    """
    overlay = read_toml(REPO_ROOT / "mise.ood.toml", MiseOverlay)
    assert overlay.env["UV_CACHE_DIR"] == "{{config_root}}/.cache/uv"
