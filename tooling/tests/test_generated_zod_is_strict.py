# tooling/tests/test_generated_zod_is_strict.py
"""Generated Zod holds no z.any() or z.unknown().

WHY THIS EXISTS. json-schema-to-zod, the generator before G.32, wrote z.any()
wherever it meets a construct
it does not read -- a $ref once, 2020-12 prefixItems tuples now -- and the build
still passes, because z.any() accepts everything. A shape the generator cannot
express is a trust boundary left unchecked, so it fails here instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from otsafety_tooling.paths import REPO_ROOT

GENERATED = sorted((REPO_ROOT / "apps" / "site" / "src" / "contracts").glob("*.gen.ts"))


def test_there_is_generated_zod_to_check() -> None:
    assert GENERATED, "no generated contracts found; the gate would pass vacuously"


@pytest.mark.parametrize("path", GENERATED, ids=lambda p: p.name)
def test_no_generated_shape_is_left_loose(path: Path) -> None:
    loose = re.findall(r"z\.(?:any|unknown)\(\)", path.read_text(encoding="utf-8"))
    assert not loose, f"{path.name} accepts anything in {len(loose)} place(s)"
