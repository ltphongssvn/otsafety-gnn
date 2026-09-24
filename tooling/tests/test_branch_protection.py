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

import pytest
from pydantic import JsonValue

from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.repository_settings import BranchProtection, SettingsFile
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
