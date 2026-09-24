# tooling/src/otsafety_tooling/github/settings.py
"""Repository settings: declared as data, applied, verified, and recorded.

    contracts/repository-settings.json (desired, as code)
        -> GitHub (observed) -> findings -> verdict
        -> repository-settings-check/v1 in .artifacts/repo-settings/ -> exit code

THE PORT. GitHub is reached through GitHubRepository, a two-method protocol:
GhRepository speaks `gh api` in production, and the tests use an in-memory
repository. Everything else here runs identically in both.

THE RULES
    S001  SETTING_DIFFERS      a visible setting is not the declared value -> fail
    S002  SETTING_NOT_VISIBLE  GitHub omitted the setting                   -> unknown
    S003  GITHUB_UNREACHABLE   GitHub could not be read or updated          -> unknown

GitHub returns merge settings only to callers with administrative read, and
omits them otherwise: an omission is S002, never a disabled setting.

EVIDENCE BEFORE EXIT. Every run -- including one that could not reach GitHub --
writes its report before the exit code is returned, and only a pass exits 0.

CONFIGURE ENDS WITH CHECK. After the update, the settings are read back and
judged, so the recorded verdict describes what GitHub actually holds, not what
was requested.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.cli import note, result
from otsafety_tooling.contracts.outcome import Verdict as Outcome
from otsafety_tooling.contracts.repository_settings import (
    PROTECTION_CODES,
    REASON_CODES,
    SETTING_NAMES,
    BranchProtection,
    MergeSettings,
    ObservedSettings,
    ProtectionFinding,
    RepositoryResponse,
    SettingFinding,
    SettingsCheckReport,
    Verdict,
    load_desired,
)
from otsafety_tooling.git.ghcli import GhError, gh_json
from otsafety_tooling.paths import REPO_ROOT

UNKNOWN_REPOSITORY = "unknown"
_API_PATH = "repos/{owner}/{repo}"


class GitHubRepository(Protocol):
    """The two operations settings management needs from GitHub."""

    def read(self) -> RepositoryResponse: ...

    def update(self, changes: dict[str, bool]) -> RepositoryResponse: ...


class GhRepository:
    """The production adapter: the current checkout's repository, via `gh api`."""

    def read(self) -> RepositoryResponse:
        return gh_json(RepositoryResponse, "api", _API_PATH)

    def update(self, changes: dict[str, bool]) -> RepositoryResponse:
        fields: list[str] = []
        for name, value in changes.items():
            # -F, not -f: gh sends "true"/"false" as JSON booleans only with -F.
            fields += ["-F", f"{name}={'true' if value else 'false'}"]
        return gh_json(RepositoryResponse, "api", "-X", "PATCH", _API_PATH, *fields)


def _say(text: str) -> None:
    """One line of the command's report: stderr, because stdout carries the envelope."""
    note(text)


def compare(desired: MergeSettings, observed: ObservedSettings) -> tuple[SettingFinding, ...]:
    """Every declared setting GitHub did not show, or showed with another value."""
    findings: list[SettingFinding] = []
    for name in SETTING_NAMES:
        expected: bool = getattr(desired, name)
        actual: bool | None = getattr(observed, name)
        if actual is None:
            findings.append(
                SettingFinding(
                    rule_id="S002",
                    reason_code=REASON_CODES["S002"],
                    message=f"{name} was not returned; administrative read is needed to see it",
                    setting=name,
                    expected=expected,
                )
            )
        elif actual != expected:
            findings.append(
                SettingFinding(
                    rule_id="S001",
                    reason_code=REASON_CODES["S001"],
                    message=f"{name} is {actual} but the policy requires {expected}",
                    setting=name,
                    expected=expected,
                    observed=actual,
                )
            )
    return tuple(findings)


# THE THREE RULES THIS REPOSITORY BANS, in GitHub's own vocabulary: a force push
# replaces published commits, a deletion discards them, and a direct push bypasses
# the review that would have caught either.
RULE_FOR = {
    "allow_force_pushes": "non_fast_forward",
    "allow_deletions": "deletion",
    "require_pull_request": "pull_request",
}


def ruleset_payload(rule: BranchProtection) -> dict[str, JsonValue]:
    """One declared protection as the ruleset GitHub's API documents.

    NOBODY BYPASSES IT: bypass_actors is empty, so the rule holds for every actor
    including an administrator. A rule with an exception is a rule that reports
    protection it does not provide.
    """
    rules: list[JsonValue] = []
    if not rule.allow_deletions:
        rules.append({"type": "deletion"})
    if not rule.allow_force_pushes:
        rules.append({"type": "non_fast_forward"})
    if rule.require_pull_request:
        rules.append({"type": "pull_request"})
    return {
        "name": f"Protect {rule.branch}",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": [f"refs/heads/{rule.branch}"], "exclude": []}},
        "rules": rules,
    }


def protection_observed(answered: Sequence[JsonValue]) -> tuple[BranchProtection, ...]:
    """What the remote actually refuses, expressed as the contract declares it.

    A DISABLED OR EVALUATING RULESET REFUSES NOTHING, so it is not read as
    protection: reporting one as protective would call a repository safe while a
    force push still succeeds.
    """
    held: list[BranchProtection] = []
    for answer in answered:
        # GITHUB'S ANSWER IS JSON, narrowed rather than declared as Any: a shape
        # that is not what the API documents contributes no protection.
        if not isinstance(answer, Mapping):
            continue
        if answer.get("enforcement") != "active" or answer.get("target") != "branch":
            continue
        rules = answer.get("rules")
        kinds = {
            entry.get("type")
            for entry in (rules if isinstance(rules, Sequence) else ())
            if isinstance(entry, Mapping)
        }
        conditions = answer.get("conditions")
        ref_name = conditions.get("ref_name") if isinstance(conditions, Mapping) else None
        included = ref_name.get("include") if isinstance(ref_name, Mapping) else None
        for ref in included if isinstance(included, Sequence) else ():
            held.append(
                BranchProtection(
                    branch=str(ref).removeprefix("refs/heads/"),
                    allow_force_pushes="non_fast_forward" not in kinds,
                    allow_deletions="deletion" not in kinds,
                    require_pull_request="pull_request" in kinds,
                )
            )
    return tuple(held)


def protection_findings(
    declared: Sequence[BranchProtection], observed: Sequence[BranchProtection] | None
) -> tuple[ProtectionFinding, ...]:
    """Every declared protection the remote does not hold, or would not show.

    UNKNOWN, NEVER PASS: GitHub returns rulesets only to an administrative reader,
    and an empty answer is indistinguishable from none declared. A caller that read
    nothing gets P002 for every branch rather than a clean verdict.
    """
    if observed is None:
        return tuple(
            ProtectionFinding(
                rule_id="P002",
                reason_code=PROTECTION_CODES["P002"],
                message=(
                    f"the ruleset protecting {rule.branch} was not returned; "
                    "administrative read is needed to see it"
                ),
                branch=rule.branch,
            )
            for rule in declared
        ) or (
            ProtectionFinding(
                rule_id="P002",
                reason_code=PROTECTION_CODES["P002"],
                message="no ruleset was returned; administrative read is needed to see them",
                branch="*",
            ),
        )
    held = {rule.branch: rule for rule in observed}
    findings: list[ProtectionFinding] = []
    for rule in declared:
        actual = held.get(rule.branch)
        if actual is None:
            findings.append(
                ProtectionFinding(
                    rule_id="P001",
                    reason_code=PROTECTION_CODES["P001"],
                    message=f"{rule.branch} has no ruleset; a force push is not refused",
                    branch=rule.branch,
                )
            )
            continue
        for field in ("allow_force_pushes", "allow_deletions", "require_pull_request"):
            want, got = getattr(rule, field), getattr(actual, field)
            if want != got:
                findings.append(
                    ProtectionFinding(
                        rule_id="P001",
                        reason_code=PROTECTION_CODES["P001"],
                        message=f"{rule.branch}: {field} is {got} but the policy requires {want}",
                        branch=rule.branch,
                    )
                )
    return tuple(findings)


def _unreachable(error: Exception) -> SettingFinding:
    return SettingFinding(
        rule_id="S003",
        reason_code=REASON_CODES["S003"],
        message=f"GitHub could not be used: {error}",
    )


def _verdict(findings: tuple[SettingFinding, ...]) -> Verdict:
    rules = {finding.rule_id for finding in findings}
    if "S001" in rules:
        return "fail"
    return "unknown" if rules else "pass"


class SettingsOutcome(BaseModel):
    """The verdict on GitHub's settings, and where the record of it was written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: str
    repository: str
    findings: list[str]
    record: str


def _record(repository: str, findings: tuple[SettingFinding, ...], artifacts: Path) -> int:
    report = SettingsCheckReport(
        generated_at=datetime.now(UTC),
        repository=repository,
        findings=findings,
        verdict=_verdict(findings),
    )
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / f"{report.generated_at.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

    _say(f"repository settings: {report.verdict} ({repository})")
    for finding in findings:
        _say(f"  {finding.rule_id} {finding.reason_code}: {finding.message}")
    _say(f"  recorded: {path}")
    outcomes: dict[str, tuple[Outcome, str]] = {
        "pass": ("success", "settings_match"),
        "fail": ("refused", "settings_differ"),
        "unknown": ("failed", "settings_unreadable"),
    }
    outcome, code = outcomes[report.verdict]
    return result(
        "repo:check",
        outcome,
        code,
        f"repository settings: {report.verdict} ({repository})",
        SettingsOutcome(
            verdict=report.verdict,
            repository=repository,
            findings=[f"{f.rule_id} {f.reason_code}" for f in findings],
            record=str(path),
        ),
    )


def check(repository: GitHubRepository, desired: MergeSettings, artifacts: Path) -> int:
    """Read GitHub, judge its settings, record the result, return 0 only on pass."""
    try:
        observed = repository.read()
    except (GhError, OSError, ValidationError) as error:
        return _record(UNKNOWN_REPOSITORY, (_unreachable(error),), artifacts)

    return _record(observed.full_name or UNKNOWN_REPOSITORY, compare(desired, observed), artifacts)


def configure(repository: GitHubRepository, desired: MergeSettings, artifacts: Path) -> int:
    """Apply every declared setting, then check what GitHub actually holds."""
    try:
        repository.update(desired.model_dump())
    except (GhError, OSError) as error:
        return _record(UNKNOWN_REPOSITORY, (_unreachable(error),), artifacts)
    return check(repository, desired, artifacts)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    artifacts = artifacts_root(REPO_ROOT) / "repo-settings"
    desired = load_desired().settings
    match args:
        case ["check"]:
            return check(GhRepository(), desired, artifacts)
        case ["configure"]:
            return configure(GhRepository(), desired, artifacts)
        case other:
            raise SystemExit(
                f"usage: python -m otsafety_tooling.github.settings check|configure (got {other})"
            )


if __name__ == "__main__":
    raise SystemExit(main())
