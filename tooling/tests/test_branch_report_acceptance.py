# tooling/tests/test_branch_report_acceptance.py
"""Acceptance: the branch report records GitFlow drift as data, then decides.

OUTSIDE-IN. These tests drive `run_report` on real repositories with a bare
remote, one scenario per rule, and read back the JSON it leaves in the
artifacts folder. They say nothing about how facts are gathered; the unit
tests for the contract and the rules do.

    B001  a protected branch is behind its upstream (only)
    B002  a protected branch is ahead of its upstream (only)
    B003  a merged feature branch still exists on the remote
    B004  a protected branch has diverged from its upstream
    B005  origin/main is not contained in origin/develop
"""

from pathlib import Path

from otsafety_tooling.contracts.branch_report import BranchReport
from otsafety_tooling.git.branches import run_report
from otsafety_tooling.git.env import git


def _git(*args: str, cwd: Path) -> str:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _identity(root: Path) -> None:
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)


def _world(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin with develop and main, a writer (seed) and a clone (repo).

    The clone has local develop and main, each tracking its remote branch, so
    a freshly built world is in sync and must pass.
    """
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)

    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _identity(seed)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", "HEAD:main", cwd=seed)

    repo = tmp_path / "repo"
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _identity(repo)
    _git("branch", "-q", "--track", "main", "origin/main", cwd=repo)
    return repo, seed


def _report(artifacts: Path) -> BranchReport:
    files = sorted(artifacts.glob("*.json"))
    assert len(files) == 1, files
    return BranchReport.model_validate_json(files[0].read_text(encoding="utf-8"))


def _rule_ids(report: BranchReport) -> set[str]:
    return {finding.rule_id for finding in report.findings}


def test_a_repository_in_sync_passes_and_is_recorded(tmp_path: Path) -> None:
    repo, _ = _world(tmp_path)
    artifacts = tmp_path / "artifacts"

    assert run_report(repo, artifacts, fetch=True) == 0

    report = _report(artifacts)
    assert report.contract == "branch-report/v1"
    assert report.verdict == "pass"
    assert report.findings == ()
    names = {fact.name for fact in report.facts}
    assert {"develop", "main", "origin/develop", "origin/main"} <= names


def test_develop_behind_its_upstream_is_b001(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "newer", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)
    artifacts = tmp_path / "artifacts"

    assert run_report(repo, artifacts, fetch=True) == 1

    report = _report(artifacts)
    assert report.verdict == "fail"
    assert _rule_ids(report) == {"B001"}
    assert report.findings[0].branch == "develop"


def test_develop_ahead_of_its_upstream_is_b002(tmp_path: Path) -> None:
    repo, _ = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "made on develop", cwd=repo)
    artifacts = tmp_path / "artifacts"

    assert run_report(repo, artifacts, fetch=True) == 1
    assert _rule_ids(_report(artifacts)) == {"B002"}


def test_a_merged_feature_branch_left_on_the_remote_is_b003(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("switch", "-q", "-c", "feature/done", cwd=seed)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=seed)
    _git("push", "-q", "origin", "feature/done", cwd=seed)
    _git("push", "-q", "origin", "feature/done:develop", cwd=seed)
    _git("pull", "-q", "--ff-only", cwd=repo)
    artifacts = tmp_path / "artifacts"

    assert run_report(repo, artifacts, fetch=True) == 1

    report = _report(artifacts)
    assert _rule_ids(report) == {"B003"}
    assert report.findings[0].branch == "origin/feature/done"


def test_a_diverged_develop_is_only_b004(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "local", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "remote", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", cwd=seed)
    artifacts = tmp_path / "artifacts"

    assert run_report(repo, artifacts, fetch=True) == 1
    assert _rule_ids(_report(artifacts)) == {"B004"}


def test_main_not_merged_back_into_develop_is_b005(tmp_path: Path) -> None:
    repo, seed = _world(tmp_path)
    _git("switch", "-q", "-c", "hotfix", "origin/main", cwd=seed)
    _git("commit", "-q", "--allow-empty", "-m", "hotfix", cwd=seed)
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)
    _git("fetch", "-q", "origin", "main:main", cwd=repo)
    artifacts = tmp_path / "artifacts"

    assert run_report(repo, artifacts, fetch=True) == 1

    report = _report(artifacts)
    assert _rule_ids(report) == {"B005"}
    assert report.findings[0].branch == "origin/main"


def test_the_report_is_written_before_a_failing_exit(tmp_path: Path) -> None:
    """Evidence first: a refusal that leaves nothing behind explains nothing."""
    repo, _ = _world(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "made on develop", cwd=repo)
    artifacts = tmp_path / "artifacts"

    assert run_report(repo, artifacts, fetch=True) == 1
    assert list(artifacts.glob("*.json"))
