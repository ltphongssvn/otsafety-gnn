# tooling/tests/test_sheet_versions_are_kept.py
"""Every render of the sheet is kept, stamped with when it was made (G.57).

EACH RENDER OVERWROTE THE LAST. Two versions could never be compared, so a
layout that regressed left no trace of what it replaced -- and this sheet has
already had one divergence that only showed up as a page count, with nothing to
diff against.

A STABLE NAME STILL POINTS AT THE NEWEST, because the gates and anyone opening
the file expect one path. The stamped copies accumulate beside it.
"""

from __future__ import annotations

import re

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.57")

OUT = REPO_ROOT / "build" / "onepager"
STAMPED = re.compile(r"^project-architecture-\d{8}T\d{6}Z\.pdf$")


def test_the_generator_stamps_each_render() -> None:
    from importlib import util

    spec = util.spec_from_file_location(
        "build_arch_onepager", REPO_ROOT / "scripts" / "build_arch_onepager.py"
    )
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    name = module.stamped_name()
    assert STAMPED.match(name), f"{name} does not carry a UTC stamp"


def test_a_render_leaves_a_stamped_copy_beside_the_stable_name() -> None:
    if not (OUT / "project-architecture.pdf").is_file():
        pytest.skip("no sheet built; run mise run pdf:render")
    kept = [p.name for p in OUT.glob("project-architecture-*.pdf") if STAMPED.match(p.name)]
    assert kept, "no stamped version was kept beside the stable name"
