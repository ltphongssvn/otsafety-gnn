# tooling/src/otsafety_tooling/git/prune.py
"""Prune merged remote branches, from evidence, with every decision recorded.

    newest branch-report/v1 (evidence)
        -> its B003 findings only (candidates)
        -> re-checked against origin now (decisions)
        -> planned, or deleted with --apply (outcomes)
        -> branch-prune/v1 in .artifacts/branch-prune/ -> exit code

NEVER BY GUESS. Branches are never chosen by name or pattern: only a branch the
latest report found merged-but-remaining is a candidate, and the report file is
named in the record.

RE-CHECKED AT DELETION TIME. A report is a snapshot. After fetching with pruning,
each candidate is kept if it is protected, already gone, or no longer an
ancestor of origin/develop (new work was pushed since). A git error while
checking also keeps the branch: an unverifiable deletion is not attempted.

A PLAN BY DEFAULT. Without --apply nothing is deleted; the record shows what
would be. With --apply each deletion's outcome, deleted or failed, is recorded.

EVIDENCE BEFORE EXIT. Every run is recorded, and only a pass exits 0.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.contracts.branch_prune import PruneDecision, PruneRecord, Verdict
from otsafety_tooling.contracts.branch_report import BranchReport
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

REMOTE = "origin"
INTEGRATION_REF = "refs/remotes/origin/develop"
PROTECTED_REMOTE = frozenset({"origin/develop", "origin/main"})


def _say(text: str) -> None:
    """One line of the command's output, flushed so logs keep their order."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def newest_report(reports: Path) -> Path | None:
    """The most recent branch report; timestamped names sort chronologically."""
    found = sorted(reports.glob("*.json")) if reports.is_dir() else []
    return found[-1] if found else None


def _remote_name(branch: str) -> str:
    return branch.removeprefix(f"{REMOTE}/")


def _exists(root: Path, branch: str) -> bool:
    ref = f"refs/remotes/{REMOTE}/{_remote_name(branch)}"
    return git("rev-parse", "--verify", "--quiet", ref, cwd=root).returncode == 0


def _merged(root: Path, branch: str) -> bool:
    ref = f"refs/remotes/{REMOTE}/{_remote_name(branch)}"
    return git("merge-base", "--is-ancestor", ref, INTEGRATION_REF, cwd=root).returncode == 0


def decide(root: Path, branch: str) -> PruneDecision:
    """Keep or delete one candidate, judged against origin as it is now."""
    if branch in PROTECTED_REMOTE:
        return PruneDecision(
            branch=branch,
            decision="keep",
            reason_code="KEEP_PROTECTED",
            message=f"{branch} is protected and is never pruned",
            outcome="not_applicable",
        )
    if not _exists(root, branch):
        return PruneDecision(
            branch=branch,
            decision="keep",
            reason_code="KEEP_ALREADY_GONE",
            message=f"{branch} no longer exists on {REMOTE}",
            outcome="not_applicable",
        )
    if not _merged(root, branch):
        return PruneDecision(
            branch=branch,
            decision="keep",
            reason_code="KEEP_NOT_MERGED",
            message=f"{branch} has commits {INTEGRATION_REF} lacks; it is not deleted",
            outcome="not_applicable",
        )
    return PruneDecision(
        branch=branch,
        decision="delete",
        reason_code="DELETE_MERGED",
        message=f"{branch} is merged into {INTEGRATION_REF}",
        outcome="planned",
    )


def execute(root: Path, decision: PruneDecision) -> PruneDecision:
    """Delete a planned branch on the remote, and record what happened."""
    if decision.outcome != "planned":
        return decision
    pushed = git("push", REMOTE, "--delete", _remote_name(decision.branch), cwd=root)
    if pushed.returncode == 0:
        return decision.model_copy(update={"outcome": "deleted"})
    _say(f"  could not delete {decision.branch}: {pushed.stderr.strip()}")
    return decision.model_copy(update={"outcome": "failed"})


def _verdict(source: str | None, decisions: tuple[PruneDecision, ...]) -> Verdict:
    if source is None:
        return "unknown"
    return "fail" if any(d.outcome == "failed" for d in decisions) else "pass"


def _record(
    records: Path,
    repository: str,
    source: str | None,
    applied: bool,
    decisions: tuple[PruneDecision, ...],
) -> int:
    record = PruneRecord(
        generated_at=datetime.now(UTC),
        repository=repository,
        source_report=source,
        applied=applied,
        decisions=decisions,
        verdict=_verdict(source, decisions),
    )
    records.mkdir(parents=True, exist_ok=True)
    path = records / f"{record.generated_at.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")

    mode = "applied" if applied else "plan"
    _say(f"branch prune ({mode}): {record.verdict}, evidence {source or '(none)'}")
    for d in decisions:
        _say(f"  {d.decision} {d.branch}: {d.reason_code} -> {d.outcome}")
    _say(f"  recorded: {path}")
    return 0 if record.verdict == "pass" else 1


def run_prune(root: Path, reports: Path, records: Path, *, apply: bool) -> int:
    """Decide from the newest report, act if asked, record, return 0 only on pass."""
    source = newest_report(reports)
    if source is None:
        _say(f"no branch report in {reports}; run `mise run branches` first")
        return _record(records, root.name, None, apply, ())
    try:
        report = BranchReport.model_validate_json(source.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        _say(f"the newest branch report {source.name} could not be read: {error}")
        return _record(records, root.name, None, apply, ())

    fetched = git("fetch", REMOTE, "--prune", "--quiet", cwd=root)
    if fetched.returncode != 0:
        _say(f"fetch failed; nothing can be verified: {fetched.stderr.strip()}")
        return _record(records, report.repository, None, apply, ())

    candidates = sorted({f.branch for f in report.findings if f.rule_id == "B003"})
    decisions = tuple(decide(root, branch) for branch in candidates)
    if apply:
        decisions = tuple(execute(root, decision) for decision in decisions)
    return _record(records, report.repository, source.name, apply, decisions)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ["--apply"]):
        raise SystemExit(f"usage: python -m otsafety_tooling.git.prune [--apply]  (got {args})")
    root = artifacts_root(REPO_ROOT)
    return run_prune(
        REPO_ROOT,
        root / "branch-report",
        root / "branch-prune",
        apply=args == ["--apply"],
    )


if __name__ == "__main__":
    raise SystemExit(main())
