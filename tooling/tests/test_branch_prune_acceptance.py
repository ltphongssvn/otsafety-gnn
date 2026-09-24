# tooling/tests/test_branch_prune_acceptance.py
"""Acceptance: merged remote branches are pruned from evidence, never by guess.

OUTSIDE-IN, ON REAL REPOSITORIES. Each scenario builds a bare remote, produces
the branch report with the real `run_report` (or, for the protected case, a
report no rule would produce), runs `run_prune`, and then asks the REMOTE
whether the branch still exists.

THE SAFETY PROPERTIES
    a plan deletes nothing
    only B003 findings are candidates
    each candidate is re-checked at deletion time: protected, already gone and
    no-longer-merged branches are kept
    every run is recorded, with the report it acted on
"""

from datetime import UTC, datetime
from pathlib import Path

from otsafety_tooling.contracts.branch_prune import PruneRecord
from otsafety_tooling.contracts.branch_report import BranchReport, Finding
from otsafety_tooling.contracts.outcome import EXIT_CODES
from otsafety_tooling.git.branches import run_report, write_report
from otsafety_tooling.git.env import git
from otsafety_tooling.git.prune import run_prune


def _git(*args: str, cwd: Path) -> str:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _identity(root: Path) -> None:
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)


def _world(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A bare origin whose feature/done is merged into develop but not deleted."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "develop", str(origin), cwd=tmp_path)

    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _identity(seed)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=seed)
    _git("push", "-q", "origin", "HEAD:develop", "HEAD:main", cwd=seed)
    _git("switch", "-q", "-c", "feature/done", cwd=seed)
    _git("commit", "-q", "--allow-empty", "-m", "work", cwd=seed)
    _git("push", "-q", "origin", "feature/done", "feature/done:develop", cwd=seed)

    repo = tmp_path / "repo"
    _git("clone", "-q", str(origin), str(repo), cwd=tmp_path)
    _identity(repo)
    _git("branch", "-q", "--track", "main", "origin/main", cwd=repo)
    return origin, seed, repo


def _on_remote(origin: Path, branch: str) -> bool:
    return bool(_git("ls-remote", "--heads", str(origin), branch, cwd=origin.parent).strip())


def _record(records: Path) -> PruneRecord:
    files = sorted(records.glob("*.json"))
    assert len(files) == 1, files
    return PruneRecord.model_validate_json(files[0].read_text(encoding="utf-8"))


def _summary(record: PruneRecord) -> list[tuple[str, str, str]]:
    return [(d.branch, d.reason_code, d.outcome) for d in record.decisions]


def test_without_a_branch_report_nothing_is_decided(tmp_path: Path) -> None:
    _, _, repo = _world(tmp_path)
    records = tmp_path / "records"
    # UNKNOWN IS A FAILURE, NOT A REFUSAL: with no report, nothing was judged.
    assert run_prune(repo, tmp_path / "reports", records, apply=True) == EXIT_CODES["failed"]
    record = _record(records)
    assert (record.verdict, record.source_report, record.decisions) == ("unknown", None, ())


def test_a_plan_decides_but_deletes_nothing(tmp_path: Path) -> None:
    origin, _, repo = _world(tmp_path)
    reports, records = tmp_path / "reports", tmp_path / "records"
    run_report(repo, reports, fetch=True)

    assert run_prune(repo, reports, records, apply=False) == 0

    record = _record(records)
    assert (record.applied, record.verdict) == (False, "pass")
    assert _summary(record) == [("origin/feature/done", "DELETE_MERGED", "planned")]
    assert _on_remote(origin, "feature/done")


def test_apply_deletes_the_merged_branch_on_the_remote(tmp_path: Path) -> None:
    origin, _, repo = _world(tmp_path)
    reports, records = tmp_path / "reports", tmp_path / "records"
    run_report(repo, reports, fetch=True)

    assert run_prune(repo, reports, records, apply=True) == 0

    assert _summary(_record(records)) == [("origin/feature/done", "DELETE_MERGED", "deleted")]
    assert not _on_remote(origin, "feature/done")


def test_a_branch_deleted_since_the_report_is_kept_as_gone(tmp_path: Path) -> None:
    _, seed, repo = _world(tmp_path)
    reports, records = tmp_path / "reports", tmp_path / "records"
    run_report(repo, reports, fetch=True)
    _git("push", "-q", "origin", "--delete", "feature/done", cwd=seed)

    assert run_prune(repo, reports, records, apply=True) == 0
    assert _summary(_record(records)) == [
        ("origin/feature/done", "KEEP_ALREADY_GONE", "not_applicable")
    ]


def test_new_unmerged_work_since_the_report_is_never_deleted(tmp_path: Path) -> None:
    origin, seed, repo = _world(tmp_path)
    reports, records = tmp_path / "reports", tmp_path / "records"
    run_report(repo, reports, fetch=True)
    _git("commit", "-q", "--allow-empty", "-m", "more work", cwd=seed)
    _git("push", "-q", "origin", "feature/done", cwd=seed)

    assert run_prune(repo, reports, records, apply=True) == 0

    assert _summary(_record(records)) == [
        ("origin/feature/done", "KEEP_NOT_MERGED", "not_applicable")
    ]
    assert _on_remote(origin, "feature/done")


def _handmade_report(reports: Path, *findings: Finding) -> None:
    report = BranchReport.model_validate(
        {
            "generated_at": datetime.now(UTC),
            "repository": "repo",
            "head": "0" * 40,
            "git_version": "2.55.0",
            "facts": [
                {
                    "name": "origin/develop",
                    "kind": "remote",
                    "commit": "0" * 40,
                    "vs_develop": {"ahead": 0, "behind": 0},
                    "merged_into_develop": True,
                    "checked_out": False,
                }
            ],
            "findings": [finding.model_dump() for finding in findings],
            "verdict": "fail",
        }
    )
    write_report(report, reports)


def test_a_protected_branch_is_never_deleted_whatever_the_report_says(tmp_path: Path) -> None:
    origin, _, repo = _world(tmp_path)
    reports, records = tmp_path / "reports", tmp_path / "records"
    finding = Finding(
        rule_id="B003",
        reason_code="MERGED_REMOTE_BRANCH_REMAINS",
        message="origin/develop is merged",
        branch="origin/develop",
    )
    _handmade_report(reports, finding)

    assert run_prune(repo, reports, records, apply=True) == 0

    assert _summary(_record(records)) == [("origin/develop", "KEEP_PROTECTED", "not_applicable")]
    assert _on_remote(origin, "develop")


def test_only_merged_branch_findings_are_candidates(tmp_path: Path) -> None:
    _, _, repo = _world(tmp_path)
    reports, records = tmp_path / "reports", tmp_path / "records"
    finding = Finding(
        rule_id="B002",
        reason_code="PROTECTED_BRANCH_AHEAD",
        message="develop is ahead",
        branch="develop",
    )
    _handmade_report(reports, finding)

    assert run_prune(repo, reports, records, apply=True) == 0
    assert _record(records).decisions == ()


def test_the_newest_report_is_the_evidence(tmp_path: Path) -> None:
    origin, seed, repo = _world(tmp_path)
    reports, records = tmp_path / "reports", tmp_path / "records"
    run_report(repo, reports, fetch=True)
    _git("push", "-q", "origin", "--delete", "feature/done", cwd=seed)
    run_report(repo, reports, fetch=True)
    newest = sorted(reports.glob("*.json"))[-1].name

    assert run_prune(repo, reports, records, apply=True) == 0

    record = _record(records)
    assert (record.source_report, record.decisions) == (newest, ())
    assert not _on_remote(origin, "feature/done")
