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
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.contracts.repository_settings import (
    REASON_CODES,
    SETTING_NAMES,
    MergeSettings,
    ObservedSettings,
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
    """Write one line of the command's output, flushed so logs keep their order."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


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
    return 0 if report.verdict == "pass" else 1


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
