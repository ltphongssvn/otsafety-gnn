# tooling/tests/test_plan_status_adapter.py
"""Facts are observed on the ref, never on the disk; the view is rendered from a status.

THE PROBE'S FAULTS, EACH PINNED. It read the working tree, so an uncommitted file
made a step look done; and it trusted any branch that existed, so an empty one
read as progress. Facts come from the named ref, and a branch counts only when
it holds commits beyond it.
"""

from __future__ import annotations

from pathlib import Path

from otsafety_tooling.contracts.plan import ProjectPlan
from otsafety_tooling.git.env import git as _run_git
from otsafety_tooling.planning.render import render
from otsafety_tooling.planning.status import derive, gather_facts

MISE = """min_version = "2026.9.9"
[env]
[task_config]
shell = "bash -c"
[tasks.x]
description = "a task"
run = "true"
"""


def _git(*args: str, cwd: Path) -> str:
    result = _run_git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _world(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)
    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    for root in (seed,):
        _git("config", "user.email", "test@example.invalid", cwd=root)
        _git("config", "user.name", "Test", cwd=root)
    (seed / "mise.toml").write_text(MISE)
    (seed / "a.py").write_text("")
    _git("add", "-A", cwd=seed)
    _git("commit", "-q", "-m", "base", cwd=seed)
    _git("tag", "v1.0.0", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", "v1.0.0", cwd=seed)
    repo = tmp_path / "repo"
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _git("config", "user.email", "test@example.invalid", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    _git("branch", "feature/empty", cwd=repo)
    _git("switch", "-q", "-c", "feature/work", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=repo)
    _git("switch", "-q", "develop", cwd=repo)
    (repo / "b.py").write_text("")
    return repo


def test_facts_come_from_the_ref_not_the_disk(tmp_path: Path) -> None:
    facts = gather_facts(_world(tmp_path), "origin/develop", merged_prs=lambda: frozenset({14}))
    assert "a.py" in facts.paths
    assert "b.py" not in facts.paths, "an untracked file on the disk made a step look done"
    assert "x" in facts.tasks
    assert "v1.0.0" in facts.tags
    assert facts.merged_prs == frozenset({14})


def test_a_branch_counts_only_with_commits_of_its_own(tmp_path: Path) -> None:
    facts = gather_facts(_world(tmp_path), "origin/develop", merged_prs=frozenset)
    assert "feature/work" in facts.branches_with_work
    assert "feature/empty" not in facts.branches_with_work


def test_the_view_is_rendered_from_a_status(tmp_path: Path) -> None:
    plan = ProjectPlan.model_validate(
        {
            "contract": "project-plan/v1",
            "threads": [{"id": "F", "title": "Release"}],
            "phases": [{"id": "8F", "title": "Release"}],
            "loops": [{"id": "promise", "code": "contracts", "data": "evidence"}],
            "steps": [
                {
                    "id": "F.1",
                    "title": "Pinned",
                    "thread": "F",
                    "phase": "8F",
                    "serves": [{"loop": "promise", "side": "code"}],
                    "done_when": [{"kind": "path", "path": "a.py"}],
                },
                {
                    "id": "F.2",
                    "title": "Verified",
                    "thread": "F",
                    "phase": "8F",
                    "depends_on": ["F.3"],
                    "serves": [{"loop": "promise", "side": "data"}],
                    "done_when": [{"kind": "path", "path": "c.py"}],
                },
                {
                    "id": "F.3",
                    "title": "Released",
                    "thread": "F",
                    "phase": "8F",
                    "serves": [{"loop": "promise", "side": "data"}],
                    "done_when": [{"kind": "path", "path": "d.py"}],
                },
            ],
        }
    )
    text = render(
        plan, derive(plan, gather_facts(_world(tmp_path), "origin/develop", merged_prs=frozenset))
    )
    assert "✅ F.1" in text
    assert "🔒 F.2" in text and "after F.3" in text
    assert "NOW" in text and "⬜ F.3" in text
