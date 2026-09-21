# tooling/tests/test_release.py
"""Releases are cut from main, by version, and only a release reaches production.

PORTED FROM FleetManagement, WHICH SOLVED THIS ALREADY. On a push to main,
semantic-release reads the Conventional Commits since the last tag, computes the
next version, and creates the tag and a GitHub Release. Nothing is committed
back to main: its .releaserc.json omits @semantic-release/git deliberately, and
the GitHub Release is the changelog of record.

ONE CHANGE, THE ENGINE. FleetManagement is a Node monorepo; this repository's
tooling is Python under uv, so python-semantic-release, pinned in uv.lock,
replaces the Node package. 2026 practice for Python projects: Conventional
Commits are only the input convention and do not imply a Node release stack.

THE DEPLOY IS TAG-GATED, and that is the root fix. The first production deploy
came from develop, because deploy:site checked only for a clean tree.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_toml, read_yaml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.release_config import Pyproject, SemanticReleaseConfig
from otsafety_tooling.contracts.workflow import Workflow
from otsafety_tooling.paths import REPO_ROOT


def _psr() -> SemanticReleaseConfig:
    return read_toml(REPO_ROOT / "pyproject.toml", Pyproject).tool.semantic_release


def _task(name: str) -> str:
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    assert name in tasks, f"no {name} task"
    return "\n".join(tasks[name].scripts)


def _workflow(name: str) -> Workflow:
    path = REPO_ROOT / ".github" / "workflows" / name
    if not path.is_file():
        pytest.fail(f"no workflow {name}")
    return read_yaml(path, Workflow)


def test_versions_come_from_conventional_commits_as_v_tags() -> None:
    psr = _psr()
    assert psr.commit_parser == "conventional"
    assert psr.tag_format == "v{version}"


def test_the_first_release_is_one_point_zero() -> None:
    """Stated, not defaulted: a default is what a tool upgrade changes."""
    assert _psr().allow_zero_version is False


def test_only_main_can_release() -> None:
    """The default matches (main|master); no master exists to be matched."""
    assert _psr().branches["main"].match == "^main$"


def test_a_release_tags_and_publishes_but_commits_nothing() -> None:
    run = _task("release:version")
    assert "--no-commit" in run, "nothing is committed back to main"
    assert "--no-changelog" in run, "a changelog nobody commits is a stray file"
    assert "--vcs-release" in run
    assert "--push" in run


def test_the_release_workflow_runs_on_main_through_the_task() -> None:
    wf = _workflow("release.yml")
    push = wf.on["push"]
    assert push is not None and push.branches == ("main",)
    steps = wf.jobs["release"].steps
    runs = " ".join(s.run or "" for s in steps)
    assert "mise run release:version" in runs, "through the task, not around it"
    checkout = next(s for s in steps if "actions/checkout" in (s.uses or ""))
    assert checkout.with_["fetch-depth"] == 0, "the last tag must be reachable"
    assert checkout.with_["persist-credentials"] is False
    assert wf.permissions == {}, "the workflow grants nothing by default"
    permissions = wf.jobs["release"].permissions
    assert permissions is not None and permissions["contents"] == "write"


def test_production_deploys_only_a_release_tag_on_main() -> None:
    """The first deploy came from develop because only a clean tree was checked."""
    run = _task("deploy:site")
    assert "--exact-match" in run, "HEAD must be exactly a release tag"
    assert "merge-base --is-ancestor HEAD origin/main" in run


def test_the_workflow_scan_runs_on_pushes_to_main() -> None:
    """zizmor.yml named master, which does not exist, so it never ran on a push."""
    push = _workflow("zizmor.yml").on["push"]
    assert push is not None
    branches = push.branches
    assert "master" not in branches
    assert "main" in branches


def test_the_release_tool_never_shares_the_projects_lock() -> None:
    """Added to the project, it rolled wandb back from 0.30.0 to 0.26.1.

    python-semantic-release constrains click to 8.1; uv resolved that silently by
    downgrading wandb, and a W&B test then failed on Linux, on develop. uv keeps
    one universal lock across every group and extra, so only a separate project
    with its own lockfile keeps the tool out.
    """
    project_lock = (REPO_ROOT / "uv.lock").read_text()
    assert 'name = "python-semantic-release"' not in project_lock
    tool_lock = (REPO_ROOT / "tools" / "release" / "uv.lock").read_text()
    assert 'name = "python-semantic-release"' in tool_lock
    for task in ("release:preview", "release:version"):
        assert "uv run --project tools/release semantic-release" in _task(task)
