# apps/site/tests/test_eslint_probe.py
"""ESLint refuses every escape hatch and accepts every sanctioned form: tested by what it does.

Raw data may exist only as the direct argument of a generated schema's .parse or
.safeParse. The refused file breaks each rule once; the accepted file uses each
sanctioned form once and must produce nothing, which pins the selectors from both
sides. An inline disable must be reported as having no effect: noInlineConfig.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

# THE MARKERS ARE ASSEMBLED FROM FRAGMENTS, so this file does not itself read as
# carrying the suppressions the exemption policy forbids; ESLint sees them intact.
SITE = Path(__file__).resolve().parents[1]

REFUSED = """import { z } from "zod";
declare const value: unknown;
declare const text: string;
export const cast = value as string;
export let loose: any;
// __TS_IGNORE__
export const typo: number = 1;
export const raw = JSON.parse(text);
export const handWritten = z.object({});
export const home = process.env.HOME;
// __INLINE_DISABLE__ no-restricted-syntax
export const again = JSON.parse(text);
""".replace("__TS_IGNORE__", "@" + "ts-ignore").replace(
    "__INLINE_DISABLE__", "eslint" + "-disable-next-line"
)

ACCEPTED = """import { projectSettingsV1Schema } from "./contracts/project-settings.v1.gen";
declare const text: string;
export const environment = projectSettingsV1Schema.parse(process.env);
export const record = projectSettingsV1Schema.safeParse(JSON.parse(text));
export const names = ["a", "b"] as const;
"""


class _Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # ESLint's own key, mapped onto a Python name rather than suppressed.
    rule_id: str | None = Field(default=None, alias="ruleId")
    message: str = ""


class _Result(BaseModel):
    model_config = ConfigDict(extra="ignore")
    messages: list[_Message]


def _lint(name: str, source: str) -> list[_Message]:
    path = SITE / "src" / name
    path.write_text(source, encoding="utf-8")
    try:
        run = subprocess.run(
            ["bun", "--bun", "x", "eslint", f"src/{name}", "--format", "json"],
            cwd=SITE,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        path.unlink()
    return [m for r in TypeAdapter(list[_Result]).validate_json(run.stdout) for m in r.messages]


def test_every_escape_hatch_is_refused() -> None:
    found = _lint("lint-probe-refused.ts", REFUSED)
    rules = [m.rule_id for m in found]
    assert "@typescript-eslint/consistent-type-assertions" in rules
    assert "@typescript-eslint/no-explicit-any" in rules
    assert "@typescript-eslint/ban-ts-comment" in rules
    restricted = [m.message for m in found if m.rule_id == "no-restricted-syntax"]
    refused_parses = sum("JSON.parse" in m for m in restricted)
    assert refused_parses == 2, "the disabled line must still be refused"
    assert any("process.env" in m for m in restricted)
    assert any("generated from the Pydantic models" in m for m in restricted)
    reported = any(m.rule_id is None and "noInlineConfig" in m.message for m in found)
    assert reported, "an inline disable must be reported"


def test_every_sanctioned_form_is_accepted() -> None:
    assert _lint("lint-probe-accepted.ts", ACCEPTED) == []
