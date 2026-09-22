# tooling/tests/test_exemptions.py
"""Every exemption from a rule is declared once, with its reason, and checked both ways.

WHY THIS EXISTS. A suppression anyone can add without saying why is a rule that
holds only while people remember it. 43 inline suppressions gave no reason any
machine could check; 13 of them duplicated a per-file ignore and suppressed
nothing; and per-file ignores exempt whole directories with their reasons kept
only in comments. Ruff's RUF100 finds suppressions that suppress nothing, but no
tool requires a reason. The register does.

BOTH DIRECTIONS. A suppression with no entry fails, and so does an entry whose
suppression is gone: a stale reason is a false statement about the code. Scoped
entries mirror Ruff's per-file ignores, which Ruff cannot read from here, and
must equal them exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.exemptions import ExemptionRegister
from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.lefthook_config import LefthookConfig
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.exemptions import (
    REGISTER,
    inline_suppressions,
    per_file_ignores,
    problems,
)


def _register() -> ExemptionRegister:
    return read_yaml(REPO_ROOT / REGISTER, ExemptionRegister)


def test_the_register_validates() -> None:
    assert _register().inline


def test_an_empty_reason_is_refused() -> None:
    with pytest.raises(ValidationError):
        ExemptionRegister.model_validate(
            {
                "contract": "exemption-register/v1",
                "scoped": [],
                "inline": [{"path": "a.py", "rule": "T201", "count": 1, "reason": ""}],
            }
        )


def test_a_count_below_one_is_refused() -> None:
    with pytest.raises(ValidationError):
        ExemptionRegister.model_validate(
            {
                "contract": "exemption-register/v1",
                "scoped": [],
                "inline": [{"path": "a.py", "rule": "T201", "count": 0, "reason": "x"}],
            }
        )


def test_every_suppression_is_registered_and_every_entry_is_live() -> None:
    assert problems(REPO_ROOT, _register()) == []


def test_the_scan_finds_suppressions_to_check() -> None:
    assert inline_suppressions(REPO_ROOT), "no suppressions found; the gate would pass vacuously"
    assert per_file_ignores(REPO_ROOT), "no per-file ignores found; the mirror would pass vacuously"


def test_typescript_carries_no_inline_disables() -> None:
    assert not [
        key for key in inline_suppressions(REPO_ROOT) if key[1].startswith(("eslint:", "ts:"))
    ]


def test_the_floor_runs_the_same_rule() -> None:
    hook = read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig).pre_commit
    assert hook is not None
    assert any(job.run == "mise run policy:exemptions" for job in hook.jobs)


def test_an_untracked_file_is_scanned(tmp_path: Path) -> None:
    """A new, unstaged file's suppression is seen, not invisible until staging."""
    from otsafety_tooling.git.env import git

    assert git("init", "-q", cwd=tmp_path).returncode == 0
    # Assembled from fragments, so this file does not itself read as carrying one.
    (tmp_path / "new.py").write_text("print(1)  # " + "noqa: T201\n", encoding="utf-8")
    assert inline_suppressions(tmp_path)[("new.py", "T201")] == 1
