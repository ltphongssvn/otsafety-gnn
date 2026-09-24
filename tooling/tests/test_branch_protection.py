# tooling/tests/test_branch_protection.py
"""The remote refuses a rewrite, and says so as data (G.40).

WHY. Every guard against rewriting lineage lives in this clone: the pre-commit
hook refuses a protected branch, and no command calls rebase. A clone that never
ran setup has none of them, and the remote declared no ruleset at all -- so
develop and main were protected by convention. Protection is declared here beside
the merge policy, applied by repo:configure and verified by repo:check, and a
rewrite is refused by GitHub rather than by a local hook.

A SIBLING SECTION, NOT A WIDER MergeSettings: a ruleset is a different endpoint
with a different shape, and one model covering both would let a check report a
verdict on settings it never read.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import JsonValue

from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.repository_settings import (
    BranchProtection,
    RepositoryResponse,
    SettingsFile,
    load_desired,
)
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.40")

CONTRACT = REPO_ROOT / "contracts" / "repository-settings.json"


def test_protection_is_declared_for_every_protected_branch() -> None:
    declared = read_json(CONTRACT, SettingsFile).protection
    assert declared is not None, "the contract declares branch protection"
    assert {rule.branch for rule in declared} == {"develop", "main"}


def test_protection_refuses_the_rewrites_this_repository_bans() -> None:
    """The three ways lineage is rewritten, each refused by the remote."""
    for rule in read_json(CONTRACT, SettingsFile).protection or ():
        assert not rule.allow_force_pushes, (
            f"{rule.branch}: a force push rewrites published commits"
        )
        assert not rule.allow_deletions, f"{rule.branch}: deleting the branch discards its history"
        assert rule.require_pull_request, f"{rule.branch}: changes arrive through a reviewed merge"


def test_a_check_reports_protection_it_could_not_read() -> None:
    """UNKNOWN, NEVER PASS: GitHub shows rulesets only to an administrative reader."""
    from otsafety_tooling.github.settings import protection_findings

    findings = protection_findings(declared=(), observed=None)
    assert findings, "an unreadable ruleset is reported, not assumed to pass"
    assert findings[0].reason_code == "PROTECTION_NOT_VISIBLE"


def test_a_declared_rule_becomes_the_payload_github_documents() -> None:
    """THE SHAPE IS THE API'S, not one invented here: a branch-target ruleset whose
    three rules are the three ways lineage is rewritten."""
    from otsafety_tooling.github.settings import ruleset_payload

    rule = BranchProtection(branch="develop")
    payload = ruleset_payload(rule)
    assert payload["target"] == "branch" and payload["enforcement"] == "active"
    conditions = payload["conditions"]
    assert isinstance(conditions, dict)
    ref_name = conditions["ref_name"]
    assert isinstance(ref_name, dict)
    assert ref_name["include"] == ["refs/heads/develop"]
    rules = payload["rules"]
    assert isinstance(rules, list)
    assert {entry["type"] for entry in rules if isinstance(entry, dict)} == {
        "deletion",
        "non_fast_forward",
        "pull_request",
    }
    assert payload["bypass_actors"] == [], "nobody bypasses a rule this repository declares"


def test_githubs_answer_is_read_back_into_the_declared_shape() -> None:
    """What the remote holds, expressed as what the contract declares, so the two
    are compared as data rather than by eye."""
    from otsafety_tooling.github.settings import protection_observed

    answered: list[JsonValue] = [
        {
            "name": "Protect develop",
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/develop"], "exclude": []}},
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
        }
    ]
    observed = protection_observed(answered)
    assert [rule.branch for rule in observed] == ["develop"]
    # pull_request is absent, so a direct push is NOT refused: require_pull_request is False.
    assert observed[0].allow_force_pushes is False
    assert observed[0].allow_deletions is False
    assert observed[0].require_pull_request is False


def test_a_disabled_ruleset_protects_nothing() -> None:
    from otsafety_tooling.github.settings import protection_observed

    answered: list[JsonValue] = [
        {
            "name": "Protect develop",
            "target": "branch",
            "enforcement": "disabled",
            "conditions": {"ref_name": {"include": ["refs/heads/develop"], "exclude": []}},
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "pull_request"}],
        }
    ]
    assert protection_observed(answered) == (), "a disabled ruleset refuses nothing"


class _Remote:
    """A GitHub that holds rulesets in memory, so check and configure are exercised."""

    def __init__(self, rulesets: list[JsonValue] | None = None) -> None:
        self.held: list[JsonValue] = list(rulesets or [])
        self.created: list[JsonValue] = []

    def read(self) -> RepositoryResponse:
        return RepositoryResponse(
            full_name="owner/repo",
            allow_merge_commit=True,
            allow_squash_merge=False,
            allow_rebase_merge=False,
            allow_auto_merge=False,
            delete_branch_on_merge=True,
        )

    def update(self, changes: dict[str, bool]) -> RepositoryResponse:
        return self.read()

    def rulesets(self) -> tuple[JsonValue, ...]:
        """In full, as the adapter now returns them after following each id."""
        return tuple(self.held)

    def create_ruleset(self, payload: dict[str, JsonValue]) -> None:
        self.created.append(payload)
        self.held.append(payload)


def test_check_reports_an_unprotected_repository(tmp_path: Path) -> None:
    """THE STATE THIS REPOSITORY WAS IN: no ruleset at all, so a force push lands."""
    from otsafety_tooling.contracts.outcome import EXIT_CODES
    from otsafety_tooling.github.settings import check

    code = check(_Remote(), load_desired().settings, tmp_path, load_desired().protection or ())
    assert code == EXIT_CODES["refused"], "an unprotected branch is a refusal"
    report = sorted(tmp_path.glob("*.json"))[-1].read_text(encoding="utf-8")
    assert "develop has no ruleset" in report and "main has no ruleset" in report


def test_configure_creates_the_rulesets_it_declares(tmp_path: Path) -> None:
    from otsafety_tooling.github.settings import configure

    remote = _Remote()
    configure(remote, load_desired().settings, tmp_path, load_desired().protection or ())
    names = [payload["name"] for payload in remote.created if isinstance(payload, dict)]
    assert names == ["Protect develop", "Protect main"]


def test_configure_then_check_passes(tmp_path: Path) -> None:
    """OBSERVE, APPLY, OBSERVE AGAIN: the same sequence the merge settings use."""
    from otsafety_tooling.contracts.outcome import EXIT_CODES
    from otsafety_tooling.github.settings import check, configure

    remote = _Remote()
    configure(remote, load_desired().settings, tmp_path, load_desired().protection or ())
    assert check(remote, load_desired().settings, tmp_path, load_desired().protection or ()) == 0
    assert EXIT_CODES["success"] == 0


def test_configure_is_safe_to_run_twice(tmp_path: Path) -> None:
    """APPLYING DECLARED STATE IS IDEMPOTENT. The first run created both rulesets;
    the second met a name GitHub already holds and failed with 422, which read as
    GITHUB_UNREACHABLE -- a command that cannot be run twice is not applying state,
    it is issuing a one-off."""
    from otsafety_tooling.github.settings import configure

    remote = _Remote()
    first = configure(remote, load_desired().settings, tmp_path, load_desired().protection or ())
    second = configure(remote, load_desired().settings, tmp_path, load_desired().protection or ())
    assert first == 0 and second == 0
    assert len(remote.created) == 2, "the second run creates nothing: both already exist"


def test_a_ruleset_that_drifted_is_reported_not_duplicated(tmp_path: Path) -> None:
    """A ruleset that exists but no longer refuses what it should is a P001 finding,
    not a second ruleset with the same name."""
    from otsafety_tooling.contracts.outcome import EXIT_CODES
    from otsafety_tooling.github.settings import check

    weakened: list[JsonValue] = [
        {
            "name": "Protect develop",
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/develop"], "exclude": []}},
            "rules": [{"type": "deletion"}],
        }
    ]
    code = check(
        _Remote(weakened), load_desired().settings, tmp_path, load_desired().protection or ()
    )
    assert code == EXIT_CODES["refused"]
    report = sorted(tmp_path.glob("*.json"))[-1].read_text(encoding="utf-8")
    assert "allow_force_pushes is True but the policy requires False" in report


def test_a_summary_without_rules_is_not_read_as_unprotected() -> None:
    """THE LIST ENDPOINT ANSWERS SUMMARIES. Observed on the real repository: a list
    response carries id, name, enforcement and target, and NO conditions or rules --
    those come only from fetching a ruleset by id. Reading a summary as protection
    found no rules and reported every branch unprotected while both rulesets held
    all three, so the check could never pass."""
    from otsafety_tooling.github.settings import needs_detail, protection_observed

    summary: list[JsonValue] = [
        {
            "id": 23917733,
            "name": "Protect develop",
            "target": "branch",
            "enforcement": "active",
            "source_type": "Repository",
        }
    ]
    assert needs_detail(summary) == (23917733,), "a summary is fetched by id"
    assert protection_observed(summary) == (), "a summary states no protection either way"


def test_a_detailed_ruleset_reads_as_the_protection_it_holds() -> None:
    from otsafety_tooling.github.settings import protection_observed

    detailed: list[JsonValue] = [
        {
            "id": 23917733,
            "name": "Protect develop",
            "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/develop"], "exclude": []}},
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "pull_request"}],
        }
    ]
    held = protection_observed(detailed)
    assert [rule.branch for rule in held] == ["develop"]
    assert held[0].allow_force_pushes is False
    assert held[0].allow_deletions is False
    assert held[0].require_pull_request is True
