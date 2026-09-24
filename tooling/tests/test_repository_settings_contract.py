# tooling/tests/test_repository_settings_contract.py
"""The repository settings contract: what the repository MUST be, as data.

POLICY AS DATA. contracts/repository-settings.json is the single declaration of
the merge policy GitFlow needs; the models make it impossible to state that
policy loosely or to read GitHub's answer loosely.

A MISSING FIELD IS NOT FALSE. GitHub returns merge settings only to callers with
administrative read, and omits them otherwise. An observed setting that is
absent therefore stays None -- "not visible" -- so nothing downstream can mistake
an unreadable setting for a disabled one.

ONE LIST OF NAMES. The SettingName type and the models each spell out the five
settings; the last test fails if they ever disagree.
"""

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.repository_settings import (
    SETTING_NAMES,
    MergeSettings,
    ObservedSettings,
    SettingsFile,
    load_desired,
)

POLICY: dict[str, bool] = {
    "allow_merge_commit": True,
    "allow_squash_merge": False,
    "allow_rebase_merge": False,
    "allow_auto_merge": False,
    "delete_branch_on_merge": True,
}


def test_the_committed_file_states_the_gitflow_merge_policy() -> None:
    desired = load_desired()
    assert desired.contract == "repository-settings/v1"
    assert desired.settings.model_dump() == POLICY


def test_unknown_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        MergeSettings.model_validate({**POLICY, "allow_forking": True})


def test_settings_must_be_real_booleans() -> None:
    with pytest.raises(ValidationError):
        MergeSettings.model_validate({**POLICY, "delete_branch_on_merge": "true"})


def test_the_file_names_its_contract() -> None:
    with pytest.raises(ValidationError):
        SettingsFile.model_validate({"contract": "something/v9", "settings": POLICY})


def test_an_observed_response_keeps_only_the_merge_settings() -> None:
    response: dict[str, object] = {**POLICY, "name": "otsafety-gnn", "private": False}
    observed = ObservedSettings.model_validate(response)
    assert observed.model_dump() == POLICY


def test_a_setting_github_did_not_return_is_not_visible_rather_than_false() -> None:
    response = {key: value for key, value in POLICY.items() if key != "allow_auto_merge"}
    observed = ObservedSettings.model_validate(response)
    assert observed.allow_auto_merge is None
    assert observed.allow_merge_commit is True


def test_recorded_settings_cannot_be_changed() -> None:
    settings = MergeSettings.model_validate(POLICY)
    with pytest.raises(ValidationError, match="frozen"):
        settings.allow_squash_merge = True  # type: ignore[misc]


def test_the_setting_names_are_declared_identically_everywhere() -> None:
    """The type, the policy model and the observed model name the same settings."""
    assert SETTING_NAMES == tuple(POLICY)
    assert tuple(MergeSettings.model_fields) == SETTING_NAMES
    assert tuple(ObservedSettings.model_fields) == SETTING_NAMES
