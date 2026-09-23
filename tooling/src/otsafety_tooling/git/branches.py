# tooling/src/otsafety_tooling/git/branches.py
"""Record every branch's state as data, then judge it against GitFlow.

    gather (git, as facts) -> evaluate (rules, as findings) -> verdict
        -> branch-report/v1 written to .artifacts/ -> exit code

WHY PYTHON AND NOT REGO. These rules judge LIVE repository state, not committed
files; the repository policy (Rego) will judge configuration. The rules are a
pure function over facts, so each is tested without running git.

THE RULES
    B001  PROTECTED_BRANCH_BEHIND        local develop/main behind its upstream
    B002  PROTECTED_BRANCH_AHEAD         local develop/main ahead of its upstream
    B003  MERGED_REMOTE_BRANCH_REMAINS   a merged branch still exists on origin
    B004  PROTECTED_BRANCH_DIVERGED      local develop/main both ahead and behind
    B005  MAIN_NOT_IN_DEVELOP            origin/main has commits origin/develop lacks

Local feature branches are not judged: cleaning them up is `sync`'s job.

EVIDENCE BEFORE EXIT. The report is written before the exit code is returned,
so a refusal always leaves its reasons behind. A report whose facts could not
be read is `unknown`, never `pass`.

WHERE REPORTS GO. Into the main checkout's .artifacts/branch-report/, from
every worktree, so removing a linked worktree never removes its reports. The
location is resolved when the command runs, not when the module is imported.

WHY %(ahead-behind:<ref>). It counts every ref against origin/develop in one
walk (git 2.41+), instead of one rev-list process per branch. FAS OnDemand
runs git 2.43; older git is refused rather than half-supported.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.cli import note
from otsafety_tooling.cli import result as emit_result
from otsafety_tooling.contracts.branch_report import (
    BranchFact,
    BranchReport,
    Divergence,
    Finding,
    Verdict,
)
from otsafety_tooling.contracts.outcome import Verdict as OutcomeVerdict
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

MINIMUM_GIT = (2, 41, 0)
INTEGRATION = "origin/develop"
RELEASE = "origin/main"
PROTECTED_LOCAL = frozenset({"develop", "main"})
REMOTE_PROTECTED = frozenset({INTEGRATION, RELEASE})
UNKNOWN_HEAD = "0" * 40
UNKNOWN_VERSION = "0.0"

_VERSION = re.compile(r"git version (\d+)\.(\d+)(?:\.(\d+))?")
_SEPARATOR = "\0"
_LOCAL_FORMAT = _SEPARATOR.join(
    [
        "%(refname)",
        "%(refname:short)",
        "%(objectname)",
        "%(upstream:short)",
        "%(upstream:track)",
        f"%(ahead-behind:{INTEGRATION})",
        "%(worktreepath)",
        "%(HEAD)",
    ]
).replace("\0", "%00")
_REMOTE_FORMAT = _SEPARATOR.join(
    [
        "%(refname)",
        "%(refname:short)",
        "%(objectname)",
        "%(symref)",
        f"%(ahead-behind:{INTEGRATION})",
    ]
).replace("\0", "%00")


class GatherError(RuntimeError):
    """The facts could not be read, so no verdict can be given."""


class _Payload(BaseModel):
    """A command's payload: named fields, checked where they are written.

    **kwargs cannot be checked -- a misspelt field would ship -- so each command
    declares what it carries, and a list stays a list because the model says so.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class BranchOutcome(_Payload):
    verdict: str
    branches: int
    findings: list[str]
    report: str
    problem: str | None


def default_artifacts() -> Path:
    """Where branch reports are recorded: the clone's shared evidence root."""
    return artifacts_root(REPO_ROOT) / "branch-report"


def parse_git_version(raw: str) -> tuple[int, int, int]:
    """(major, minor, patch) from `git --version` output, or raise."""
    match = _VERSION.search(raw)
    if match is None:
        raise ValueError(f"unrecognised git version output: {raw.strip()!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


# --- Rules (pure) --------------------------------------------------------------


def _judge_protected(fact: BranchFact) -> Finding | None:
    if fact.name not in PROTECTED_LOCAL or fact.vs_upstream is None:
        return None
    counts = fact.vs_upstream
    if counts.is_diverged:
        return Finding(
            rule_id="B004",
            reason_code="PROTECTED_BRANCH_DIVERGED",
            message=(
                f"{fact.name} has diverged from {fact.upstream}: "
                f"{counts.ahead} ahead, {counts.behind} behind"
            ),
            branch=fact.name,
        )
    if counts.behind:
        return Finding(
            rule_id="B001",
            reason_code="PROTECTED_BRANCH_BEHIND",
            message=f"{fact.name} is {counts.behind} commit(s) behind {fact.upstream}",
            branch=fact.name,
        )
    if counts.ahead:
        return Finding(
            rule_id="B002",
            reason_code="PROTECTED_BRANCH_AHEAD",
            message=(
                f"{fact.name} is {counts.ahead} commit(s) ahead of {fact.upstream}; "
                "protected branches change only through pull requests"
            ),
            branch=fact.name,
        )
    return None


def _judge_remote(fact: BranchFact) -> Finding | None:
    if fact.name == RELEASE:
        if fact.vs_develop is not None and fact.vs_develop.ahead:
            return Finding(
                rule_id="B005",
                reason_code="MAIN_NOT_IN_DEVELOP",
                message=(
                    f"{RELEASE} has {fact.vs_develop.ahead} commit(s) that {INTEGRATION} "
                    "lacks; a release or hotfix was not merged back"
                ),
                branch=fact.name,
            )
        return None
    if fact.name in REMOTE_PROTECTED or not fact.merged_into_develop:
        return None
    return Finding(
        rule_id="B003",
        reason_code="MERGED_REMOTE_BRANCH_REMAINS",
        message=f"{fact.name} is merged into {INTEGRATION} but still exists on the remote",
        branch=fact.name,
    )


def evaluate(facts: Iterable[BranchFact]) -> tuple[Finding, ...]:
    """Every rule the facts break, ordered by rule, then branch."""
    findings: list[Finding] = []
    for fact in facts:
        finding = _judge_protected(fact) if fact.kind == "local" else _judge_remote(fact)
        if finding is not None:
            findings.append(finding)
    return tuple(sorted(findings, key=lambda finding: (finding.rule_id, finding.branch)))


# --- Facts (git) ---------------------------------------------------------------


def _run(root: Path, *args: str) -> str:
    result = git(*args, cwd=root)
    if result.returncode != 0:
        raise GatherError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _divergence(text: str) -> Divergence:
    ahead, behind = text.split()
    return Divergence(ahead=int(ahead), behind=int(behind))


def _local_facts(root: Path, merged: set[str]) -> list[BranchFact]:
    facts: list[BranchFact] = []
    for line in _run(root, "for-each-ref", f"--format={_LOCAL_FORMAT}", "refs/heads").splitlines():
        ref, name, commit, upstream, track, versus, worktree, current = line.split(_SEPARATOR)
        live_upstream = upstream if upstream and track != "[gone]" else None
        vs_upstream = None
        if live_upstream is not None:
            counts = _run(root, "rev-list", "--left-right", "--count", f"{ref}...{live_upstream}")
            vs_upstream = _divergence(counts)
        facts.append(
            BranchFact(
                name=name,
                kind="local",
                commit=commit,
                upstream=live_upstream,
                vs_upstream=vs_upstream,
                vs_develop=_divergence(versus),
                merged_into_develop=ref in merged,
                checked_out=bool(worktree) or current == "*",
            )
        )
    return facts


def _remote_facts(root: Path, merged: set[str]) -> list[BranchFact]:
    facts: list[BranchFact] = []
    listing = _run(root, "for-each-ref", f"--format={_REMOTE_FORMAT}", "refs/remotes/origin")
    for line in listing.splitlines():
        ref, name, commit, symref, versus = line.split(_SEPARATOR)
        if symref:
            continue
        facts.append(
            BranchFact(
                name=name,
                kind="remote",
                commit=commit,
                vs_develop=_divergence(versus),
                merged_into_develop=ref in merged,
                checked_out=False,
            )
        )
    return facts


def _repository_name(root: Path) -> str:
    url = git("remote", "get-url", "origin", cwd=root).stdout.strip().rstrip("/")
    name = url.rsplit("/", 1)[-1].rsplit(":", 1)[-1].removesuffix(".git")
    return name or root.name


def gather(root: Path, *, fetch: bool) -> tuple[str, str, str, tuple[BranchFact, ...]]:
    """(git version, HEAD, repository name, facts), or raise GatherError."""
    try:
        version = parse_git_version(_run(root, "--version"))
    except ValueError as error:
        raise GatherError(str(error)) from error
    if version < MINIMUM_GIT:
        wanted = ".".join(map(str, MINIMUM_GIT))
        raise GatherError(f"git {'.'.join(map(str, version))} is older than {wanted}")

    if fetch:
        _run(root, "fetch", "origin", "--prune", "--quiet")
    _run(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/{INTEGRATION}")

    head = _run(root, "rev-parse", "HEAD").strip()
    merged = set(
        _run(
            root,
            "for-each-ref",
            f"--merged={INTEGRATION}",
            "--format=%(refname)",
            "refs/heads",
            "refs/remotes/origin",
        ).split()
    )
    facts = tuple(_local_facts(root, merged) + _remote_facts(root, merged))
    return ".".join(map(str, version)), head, _repository_name(root), facts


# --- Report --------------------------------------------------------------------


def write_report(report: BranchReport, artifacts: Path) -> Path:
    """Persist a report as JSON, named by its timestamp."""
    artifacts.mkdir(parents=True, exist_ok=True)
    stamp = report.generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    path = artifacts / f"{stamp}.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def run_report(root: Path, artifacts: Path, *, fetch: bool = True) -> int:
    """Gather, evaluate, record, then return 0 only for a `pass`."""
    generated_at = datetime.now(UTC)
    version, head, repository = UNKNOWN_VERSION, UNKNOWN_HEAD, root.name
    facts: tuple[BranchFact, ...] = ()
    findings: tuple[Finding, ...] = ()
    problem = ""
    try:
        version, head, repository, facts = gather(root, fetch=fetch)
        findings = evaluate(facts)
    except GatherError as error:
        problem = str(error)

    verdict: Verdict
    if problem or not facts:
        verdict = "unknown"
    elif findings:
        verdict = "fail"
    else:
        verdict = "pass"

    report = BranchReport(
        generated_at=generated_at,
        repository=repository,
        head=head,
        git_version=version,
        facts=facts,
        findings=findings,
        verdict=verdict,
    )
    path = write_report(report, artifacts)

    note(f"branch report: {verdict} ({len(facts)} branches)")
    if problem:
        note(f"  could not read the branches: {problem}")
    for finding in findings:
        note(f"  {finding.rule_id} {finding.reason_code}: {finding.message}")
    note(f"  recorded: {path}")

    # THE VERDICT DECIDES THE OUTCOME: a fail is a refusal -- the repository state
    # is wrong -- while unknown is a failure, because the facts could not be read.
    outcomes: dict[Verdict, tuple[OutcomeVerdict, str]] = {
        "pass": ("success", "branches_clean"),
        "fail": ("refused", "branches_failed"),
        "unknown": ("failed", "branches_unknown"),
    }
    outcome, code = outcomes[verdict]
    return emit_result(
        "branch:report",
        outcome,
        code,
        f"branch report: {verdict} ({len(facts)} branches, {len(findings)} findings)",
        BranchOutcome(
            verdict=verdict,
            branches=len(facts),
            findings=[f.rule_id for f in findings],
            report=str(path),
            problem=problem or None,
        ),
    )


def main() -> int:
    return run_report(REPO_ROOT, default_artifacts(), fetch=True)


if __name__ == "__main__":
    raise SystemExit(main())
