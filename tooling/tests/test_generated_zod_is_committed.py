# tooling/tests/test_generated_zod_is_committed.py
"""The committed Zod is what the generator produces (G.52).

Twenty-four tests passed while every committed module was stale: they check for
deprecated APIs and for loose shapes, and none regenerated and compared. A change
to the generator's header therefore reached nothing, and a hand-edited module
would have passed every one of them. The data export has had this check since the
day it was written; its older sibling did not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.requirement("G.52")


def test_the_committed_zod_is_what_the_generator_produces(tmp_path: Path) -> None:
    """THE GATE THIS FILE'S NAME ALREADY CLAIMED (G.52).

    Twenty-four tests passed while every committed module was stale: they check
    for deprecated APIs and for loose shapes, and none regenerated and compared.
    A change to the generator's header therefore reached nothing, and a
    hand-edited module would have passed every one of them.

    The data export has had this check since the day it was written; its older
    sibling did not.
    """
    from otsafety_tooling.contracts.zod import TARGET, generate

    generate(tmp_path)
    fresh = sorted(tmp_path.glob("*.gen.ts"))
    assert fresh, "the generator wrote nothing, so this gate would pass vacuously"
    for written in fresh:
        committed = TARGET / written.name
        assert committed.is_file(), f"{written.name} is generated and not committed"
        assert committed.read_text(encoding="utf-8") == written.read_text(encoding="utf-8"), (
            f"{written.name} differs from the generator; run mise run contracts:generate"
        )
