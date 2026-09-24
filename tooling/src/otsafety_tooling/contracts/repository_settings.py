# tooling/src/otsafety_tooling/contracts/repository_settings.py
"""repository-settings/v1: the merge policy the repository must have, as data.

POLICY AS DATA. contracts/repository-settings.json declares the settings; these
models make it impossible to state them loosely (a string "true", a misspelt
key) or to read GitHub's answer loosely.

THE MODELS
    MergeSettings        the five settings GitFlow depends on, strictly typed
    SettingsFile         the committed file that declares them
    ObservedSettings     what GitHub reported, where an ABSENT setting is None
    SettingFinding       one reason the repository does not match, as data
    SettingsCheckReport  one check, recorded: findings and the verdict they imply

A MISSING FIELD IS NOT FALSE. GitHub returns merge settings only to callers with
administrative read and omits them otherwise, rather than returning false.
Reading an omitted setting as disabled would report a drift that may not exist,
or hide one that does; None keeps "not visible" distinct.

THE VERDICT IS DERIVED, NOT CHOSEN
    any S001 (a visible setting differs)            -> fail
    otherwise any S002 or S003 (could not see)      -> unknown
    no findings                                     -> pass
A report whose verdict disagrees with its findings cannot be constructed.

SETTING_NAMES COMES FROM THE SettingName TYPE, via get_args, so it keeps the
literal types without a type-checker suppression. MergeSettings declares the
same five names as fields; a test requires the two to stay identical.

$comment. JSON has no comment syntax, so the committed file carries its path and
purpose in a `$comment` field (the JSON Schema comment keyword). It is not a
valid Python name, so the model stores it through an alias.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Final, Literal, Self, get_args

from pydantic import AwareDatetime, BaseModel, Field, StrictBool, model_validator

from otsafety_tooling.paths import REPO_ROOT

CONTRACT: Final = "repository-settings/v1"
CHECK_CONTRACT: Final = "repository-settings-check/v1"
DESIRED_PATH = REPO_ROOT / "contracts" / "repository-settings.json"

SettingName = Literal[
    "allow_merge_commit",
    "allow_squash_merge",
    "allow_rebase_merge",
    "allow_auto_merge",
    "delete_branch_on_merge",
]
SettingRule = Literal["S001", "S002", "S003"]
# PROTECTION HAS ITS OWN RULES: a ruleset is a different endpoint, and a finding
# that named a merge setting could not describe a branch.
ProtectionRule = Literal["P001", "P002"]
Verdict = Literal["pass", "fail", "unknown"]

SETTING_NAMES: Final[tuple[SettingName, ...]] = get_args(SettingName)

REASON_CODES: Final[dict[str, str]] = {
    "S001": "SETTING_DIFFERS",
    "S002": "SETTING_NOT_VISIBLE",
    "S003": "GITHUB_UNREACHABLE",
}

PROTECTION_CODES: Final[dict[str, str]] = {
    "P001": "PROTECTION_DIFFERS",
    "P002": "PROTECTION_NOT_VISIBLE",
}


class MergeSettings(BaseModel, frozen=True, extra="forbid"):
    """The merge policy: merge commits only, and merged branches deleted."""

    allow_merge_commit: StrictBool
    allow_squash_merge: StrictBool
    allow_rebase_merge: StrictBool
    allow_auto_merge: StrictBool
    delete_branch_on_merge: StrictBool


class BranchProtection(BaseModel, frozen=True, extra="forbid"):
    """What the remote must refuse on one branch, whatever a clone's hooks say.

    A SIBLING OF THE MERGE POLICY, NOT PART OF IT: a ruleset is a different
    endpoint with a different shape, and one model covering both would let a
    check report a verdict on settings it never read.
    """

    branch: str
    # THE THREE WAYS LINEAGE IS REWRITTEN, each refused at the remote: a force
    # push replaces published commits, a deletion discards them, and a direct
    # push bypasses the review that would have noticed either.
    allow_force_pushes: StrictBool = False
    allow_deletions: StrictBool = False
    require_pull_request: StrictBool = True


class ProtectionFinding(BaseModel, frozen=True, extra="forbid"):
    """One reason the remote does not refuse what this repository bans."""

    rule_id: ProtectionRule
    reason_code: str
    message: str = Field(min_length=1)
    branch: str = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.reason_code != PROTECTION_CODES[self.rule_id]:
            raise ValueError(f"{self.rule_id} must carry {PROTECTION_CODES[self.rule_id]}")
        return self


class SettingsFile(BaseModel, frozen=True, extra="forbid"):
    """contracts/repository-settings.json, as committed."""

    comment: str = Field(default="", alias="$comment")
    # AUTHORED BY A PERSON, who leaves defaults out: exported as Pydantic accepts it.
    AUTHORED: ClassVar[bool] = True
    contract: Literal["repository-settings/v1"]
    settings: MergeSettings
    protection: tuple[BranchProtection, ...] | None = None


class ObservedSettings(BaseModel, frozen=True, extra="ignore"):
    """The merge settings in GitHub's repository response; absent means not visible."""

    allow_merge_commit: StrictBool | None = None
    allow_squash_merge: StrictBool | None = None
    allow_rebase_merge: StrictBool | None = None
    allow_auto_merge: StrictBool | None = None
    delete_branch_on_merge: StrictBool | None = None


class RepositoryResponse(ObservedSettings, frozen=True, extra="ignore"):
    """GitHub's repository response: the merge settings, and the repository's name.

    A SUBCLASS, NOT A FIELD ON ObservedSettings, which is deliberately exactly the
    merge setting names -- two tests hold that. check() read the name from the raw
    response with an isinstance guard; it is now a validated field here instead.
    """

    full_name: str | None = None


class SettingFinding(BaseModel, frozen=True, extra="forbid"):
    """One reason the repository does not match its declared settings."""

    rule_id: SettingRule
    reason_code: str
    message: str = Field(min_length=1)
    setting: SettingName | None = None
    expected: StrictBool | None = None
    observed: StrictBool | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.reason_code != REASON_CODES[self.rule_id]:
            raise ValueError(f"{self.rule_id} must carry {REASON_CODES[self.rule_id]}")
        if self.rule_id == "S003":
            if self.setting is not None:
                raise ValueError("S003 concerns GitHub, not a setting")
            return self
        if self.setting is None or self.expected is None:
            raise ValueError(f"{self.rule_id} must name a setting and its expected value")
        if self.rule_id == "S001" and (self.observed is None or self.observed == self.expected):
            raise ValueError("S001 requires a visible value that differs from the expected one")
        if self.rule_id == "S002" and self.observed is not None:
            raise ValueError("S002 means the setting was not visible")
        return self


class SettingsCheckReport(BaseModel, frozen=True, extra="forbid"):
    """One settings check, recorded as data."""

    contract: Literal["repository-settings-check/v1"] = CHECK_CONTRACT
    generated_at: AwareDatetime
    repository: str = Field(min_length=1)
    findings: tuple[SettingFinding, ...] = ()
    # PROTECTION IS PART OF THE VERDICT: a repository whose merge settings match
    # while a force push still lands is not at its policy.
    protection: tuple[ProtectionFinding, ...] = ()
    verdict: Verdict

    @model_validator(mode="after")
    def _verdict_follows_the_findings(self) -> Self:
        rules = {finding.rule_id for finding in self.findings}
        guards = {finding.rule_id for finding in self.protection}
        if "S001" in rules or "P001" in guards:
            implied: Verdict = "fail"
        elif rules or guards:
            implied = "unknown"
        else:
            implied = "pass"
        if self.verdict != implied:
            raise ValueError(f"verdict is {self.verdict!r} but the findings imply {implied!r}")
        return self


def load_desired(path: Path = DESIRED_PATH) -> SettingsFile:
    """The committed settings file, validated."""
    return SettingsFile.model_validate_json(path.read_text(encoding="utf-8"))
