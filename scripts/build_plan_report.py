# scripts/build_plan_report.py
"""The step-level plan report as a one-page A3 sheet."""

from __future__ import annotations

import datetime
import html
import json
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "build" / "onepager"
OUT.mkdir(parents=True, exist_ok=True)
DATA = OUT / "plan-report.json"  # written by mise run plan:report

STATE = {"DONE": "#1d6b45", "READY": "#a86400", "BLOCK": "#a5312b"}


def e(value: object) -> str:
    return html.escape(str(value))


def emit(command: str, outcome: str, code: str, message: str, data: Mapping[str, object]) -> int:
    """The envelope on stdout, and the exit code the outcome carries."""
    envelope = {
        "contract": "command-outcome/v1",
        "command": command,
        "outcome": outcome,
        "code": code,
        "message": message,
        "data": data,
    }
    sys.stdout.write(json.dumps(envelope) + "\n")
    return {"success": 0, "failed": 1, "refused": 2}[outcome]


def build() -> str:
    if not DATA.is_file():
        raise SystemExit(f"REFUSED: no report at {DATA}; run mise run plan:report")
    report = json.loads(DATA.read_text(encoding="utf-8"))  # noqa: TID251
    cards = []
    for phase in report["phases"]:
        cards.append(
            f'<div class="ph"><b>PHASE {e(phase["id"])}</b> {e(phase["title"])} '
            f'<span class="n">{phase["done"]}/{phase["total"]}</span></div>'
        )
        for step in phase["steps"]:
            colour = STATE[step["state"]]
            after = (
                f'<span class="d">after {e(", ".join(step["after"]))}</span>'
                if step["after"]
                else ""
            )
            unmet = (
                f'<span class="u">{e("; ".join(step["unmet"])[:150])}</span>'
                if step["unmet"]
                else ""
            )
            cards.append(
                f'<div class="s"><span class="t" style="background:{colour}">{step["state"]}</span>'
                f"<b>{e(step['id'])}</b> {e(step['title'])}"
                f'<div class="m">{e(step["thread"])} &middot; '
                f"{e(', '.join(step['evidence'])[:110])}"
                f"{after}{unmet}</div></div>"
            )
    when = datetime.datetime.now(datetime.UTC)
    head = report
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Plan report</title><style>
@page{{size:420mm 297mm;margin:6mm}}*{{box-sizing:border-box}}
body{{font-family:'Liberation Sans',Arial,sans-serif;font-size:5.2pt;
line-height:1.17;margin:0;color:#14171a}}
h1{{font-size:11pt;margin:0 0 1mm}}
.hd{{border-bottom:1.6px solid #14171a;padding-bottom:1mm;margin-bottom:1.5mm;display:flex;
justify-content:space-between;align-items:baseline}}
.sub{{font-size:6.4pt;color:#5b6672}}
.cols{{column-count:7;column-gap:2.6mm;column-fill:auto;height:272mm}}
.ph{{break-inside:avoid;background:#14171a;color:#fff;padding:1px 3px;margin:1.4mm 0 0.7mm;
font-size:6.4pt;border-radius:2px}}
.ph .n{{float:right}}
.s{{break-inside:avoid;overflow-wrap:anywhere;margin-bottom:1mm;
padding-left:2px;border-left:1.6px solid #eaeef2}}
.t{{display:inline-block;color:#fff;font-size:4.4pt;font-weight:700;padding:0 2px;
border-radius:1.5px;margin-right:2px;vertical-align:1px}}
.m{{color:#5b6672;font-size:4.7pt;overflow-wrap:anywhere;word-break:break-word}}
.d{{display:block;color:#2f3f8f}}
.u{{display:block;color:#a5312b}}
</style></head><body>
<div class="hd"><h1>otsafety-gnn &mdash; every step in every phase</h1>
<div class="sub">{head["steps_done"]} of {head["steps"]} done &middot;
{head["ready"]} ready &middot; {head["blocked"]} blocked &middot; {head["ids"]} ids &middot;
{head["requirements"]} matrix rows &middot;
{head["orphans"]} orphans &middot; {when:%Y-%m-%d %H:%M} UTC</div></div>
<div class="cols">{"".join(cards)}</div></body></html>"""


def main() -> int:
    """Print the collected report, and report the printing as data."""
    page = OUT / "plan-report.html"
    pdf = OUT / "plan-report.pdf"
    page.write_text(build(), encoding="utf-8")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(page.as_uri())
        pg.wait_for_load_state("load")
        pg.evaluate("() => document.fonts.ready")
        pg.pdf(
            path=str(pdf),
            width="420mm",
            height="297mm",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "6mm", "bottom": "6mm", "left": "6mm", "right": "6mm"},
        )
        b.close()

    from pypdf import PdfReader

    # EVERY COMMAND REPORTS AS DATA. This wrote PAGES to stderr and nothing to
    # stdout, so the command inventory counted it silent -- the one command in
    # twenty-eight that could not be read by a program.
    pages = len(PdfReader(str(pdf)).pages)
    sheet: Mapping[str, object] = {
        "html": str(page),
        "pdf": str(pdf),
        "bytes": pdf.stat().st_size,
        "pages": pages,
    }
    if pages != 1:
        return emit(
            "plan:report",
            "refused",
            "report_not_one_page",
            f"the report rendered {pages} pages; it is a one-page sheet",
            sheet,
        )
    return emit(
        "plan:report", "success", "report_printed", f"one page, {pdf.stat().st_size} bytes", sheet
    )


if __name__ == "__main__":
    raise SystemExit(main())
