# apps/site/tests/test_site_type_probe.py
"""astro check refuses a type error: the gate is tested by what it does."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]


def test_astro_check_refuses_a_type_error() -> None:
    probe = SITE / "src" / "type-probe.ts"
    probe.write_text('export const probe: number = "not a number";\n', encoding="utf-8")
    try:
        run = subprocess.run(
            ["bun", "run", "check"], cwd=SITE, capture_output=True, text=True, check=False
        )
    finally:
        probe.unlink()
    out = re.sub(r"\x1b\[[0-9;]*m", "", run.stdout + run.stderr)
    assert run.returncode != 0 and "type-probe.ts" in out and "ts(2322)" in out, out[-2000:]
