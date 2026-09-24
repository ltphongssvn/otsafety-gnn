# tooling/tests/test_secrets_scanned.py
"""Secrets scanned in the hooks and across the full history (G.15).

TWO LAYERS, BECAUSE ONE IS BYPASSABLE. A pre-commit hook scans what is staged
and stops an honest mistake at zero latency; it is also skipped by --no-verify
and by anything that commits without running hooks at all. 2026 practice is
blunt about the consequence: the server-side scan over the whole history is the
authoritative gate, and the local hook is the fast path that defers to it.

A SHALLOW CLONE HIDES WHAT A HISTORY SCAN EXISTS TO SEE. The default checkout
depth on GitHub Actions is one commit, so a full-history scan there reads a
single tree and passes. fetch-depth: 0 is not an optimisation to skip.

NO BROAD ALLOWLIST. A configuration that suppresses widely blinds the scanner,
which is the second of the two root causes reported this year; this one extends
the default ruleset and adds nothing that hides a class of finding.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_json, read_toml, read_yaml
from otsafety_tooling.contracts.lefthook_config import LefthookConfig
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.toolchain import Toolchain
from otsafety_tooling.contracts.workflow import Workflow
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.15")


def test_gitleaks_is_pinned_like_every_other_tool() -> None:
    """An unpinned scanner changes its rules under you; the toolchain pins the rest."""
    toolchain = read_json(REPO_ROOT / "toolchain.json", Toolchain)
    assert toolchain.gitleaks.version, "gitleaks must be pinned in toolchain.json"


def test_the_commit_hook_scans_what_is_staged() -> None:
    """The fast path: a secret is caught before it becomes a commit."""
    config = read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig)
    assert config.pre_commit is not None, "there is no pre-commit hook at all"
    runs = [job.run for job in config.pre_commit.jobs]
    assert any("secrets:staged" in run for run in runs), (
        "no hook scans the staged changes before they become a commit"
    )


def test_a_task_scans_the_whole_history() -> None:
    """The authoritative gate, which the bypassable hook defers to."""
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    assert "secrets:scan" in tasks, "no task scans the full history"
    body = tasks["secrets:scan"].run
    text = body if isinstance(body, str) else "\n".join(body)
    assert "--redact" in text, "a finding must not print the secret it found"


def test_ci_scans_the_history_it_can_actually_see() -> None:
    """A shallow checkout reads one commit and passes, which is worse than no scan."""
    workflow = read_yaml(REPO_ROOT / ".github" / "workflows" / "test-tooling.yml", Workflow)
    scanning = [
        job for job in workflow.jobs.values() if any("secrets" in (s.run or "") for s in job.steps)
    ]
    assert scanning, "no CI job scans for secrets"
    for job in scanning:
        checkout = next(step for step in job.steps if "checkout" in (step.uses or ""))
        assert (checkout.with_ or {}).get("fetch-depth") == 0, (
            "a history scan on a shallow checkout sees one commit"
        )


def test_the_configuration_hides_no_class_of_finding() -> None:
    """A broad allowlist is the second root cause reported this year."""
    text = (REPO_ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
    assert "useDefault = true" in text, "the default ruleset is the floor"
    assert "[[rules.allowlist]]" not in text, "a rule-wide allowlist blinds the scanner"
