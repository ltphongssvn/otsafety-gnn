# tooling/tests/test_tooling_tests_hold_no_any.py
"""The tooling's tests hold no explicit Any (G.45).

SIXTY-ONE SITES, ACROSS EIGHTEEN FILES, behind a module-wide exemption that
carried no count. They are gone and the exemption with them; this is what holds
that, over the whole suite rather than over the one adapter test where the work
happened to land.

G.45 BORROWED ANOTHER REQUIREMENT'S EVIDENCE. Its proof was test_wandb_tracker,
which belongs to D.2 -- Weights and Biases as a first-class adapter -- and a
module carries one claim, so the two collided. A claim about every test in the
suite is not proved by one adapter's test whatever that test contains.
"""

from __future__ import annotations

import ast

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.45")

SUITE = REPO_ROOT / "tooling" / "tests"


def test_no_test_in_the_suite_names_any() -> None:
    """Explicit Any, anywhere under the tooling's tests."""
    offenders: list[str] = []
    for path in sorted(SUITE.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "Any":
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert offenders == [], f"{len(offenders)} explicit Any in the suite: {offenders[:6]}"


def test_the_suite_is_large_enough_for_this_to_mean_something() -> None:
    """A scan over an empty directory passes and proves nothing."""
    assert len(list(SUITE.rglob("test_*.py"))) > 50
