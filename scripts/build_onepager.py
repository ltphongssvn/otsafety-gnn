#!/usr/bin/env python3
# scripts/build_onepager.py
# THE ONE-PAGE ARCHITECTURE SHEET, A3 LANDSCAPE, AS HTML AND PDF.
#
# THE LAYERS AND THE QUESTIONS ARE NOT DECLARED HERE. They live in
# apps/site/src/data/architecture.ts, which the site renders, and this script
# parses those exports. An earlier version of this sheet held its own copies:
# two statements of what the project is, drifting apart invisibly until someone
# read them side by side. One source, or they disagree.
#
# THE DELIVERY BAND IS DECLARED HERE, because it describes how the work is
# sequenced rather than what the project claims. Phase 5 is deliberately absent:
# it was "2026 research to ADR", and the rule against architecture decision
# records removed it. A band advertising a cancelled practice is precisely the
# stale documentation that rule exists to prevent.
#
# PAGE COUNT IS ASSERTED, NOT HOPED FOR. The script exits non-zero when the PDF
# is not exactly one page, so a one-pager cannot silently become two.
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = REPO_ROOT / "apps" / "site" / "src" / "data" / "architecture.ts"
OUT_DIR = REPO_ROOT / "build" / "onepager"

PHASES = [
    ("0", "Ground truth"),
    ("1", "Branch divergence"),
    ("2", "GitFlow baseline"),
    ("3", "Worktree"),
    ("4", "Stack inventory"),
    ("6", "Toolchain and tasks"),
    ("7", "The site"),
    ("8", "The PDF"),
    ("9", "The GNN package"),
    ("10", "Lightning AI"),
    ("11", "Research execution"),
]

CURRENT_PHASE = "8"


def parse_layers(text: str) -> list[dict[str, str]]:
    """Read the LAYERS export without evaluating TypeScript.

    A regex over a data file is brittle by nature, so the caller asserts the
    count: nine layers, or the parse is wrong and the sheet must not be built.
    """
    block = text.split("export const LAYERS", 1)[1]
    block = block.split("];", 1)[0]
    out: list[dict[str, str]] = []
    for entry in re.findall(r"\{(.*?)\}", block, re.S):
        fields = dict(re.findall(r'(\w+):\s*"((?:[^"\\]|\\.)*)"', entry))
        added = "added: true" in entry
        if "name" in fields:
            fields["added"] = "true" if added else "false"
            out.append(fields)
    return out


def parse_questions(text: str) -> list[dict[str, str]]:
    block = text.split("export const QUESTIONS", 1)[1].split("];", 1)[0]
    out: list[dict[str, str]] = []
    for entry in re.findall(r"\{(.*?)\}", block, re.S):
        fields = dict(re.findall(r'(\w+):\s*"((?:[^"\\]|\\.)*)"', entry))
        if "question" in fields:
            out.append(fields)
    return out


def unescape(value: str) -> str:
    """Turn a TypeScript string literal's escapes into the characters they mean."""
    # json.loads returns Any, and strict mypy will not let that be returned as
    # str. The cast is the assertion that this input is always a JSON string.
    decoded: str = json.loads(f'"{value}"')
    return decoded


def build_html(layers: list[dict[str, str]], questions: list[dict[str, str]]) -> str:
    tag = '<div class="tag">NEW</div>'
    rows = "".join(
        f'''<tr class="{"added" if layer["added"] == "true" else ""}">
        <td class="n"><span>{layer["n"]}</span>
        {tag if layer["added"] == "true" else ""}</td>
        <td class="name">{unescape(layer["name"])}
        <div class="q">{unescape(layer["question"])}</div></td>
        <td class="fail">{unescape(layer["failure"])}</td>
        <td class="guard">{unescape(layer["guard"])}</td></tr>'''
        for layer in layers
    )
    nested = "".join(
        f"""<div class="nq"><div class="nqh"><span class="badge">{q["id"]}</span>
        {unescape(q["question"])}</div>
        <div class="nqc"><b>Contrast:</b> {unescape(q["contrast"])}</div>
        <div class="nqn"><b>If the contrast ties:</b> {unescape(q["whenTied"])}</div></div>"""
        for q in questions
    )
    chips = "".join(
        f"""<div class="chip {"now" if n == CURRENT_PHASE else ""}">
        <span class="phase-n">{n}</span><span class="phase-l">{label}</span></div>"""
        for n, label in PHASES
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Project Architecture — otsafety-gnn</title><style>
@page {{ size: A3 landscape; margin: 9mm 10mm; }}
* {{ box-sizing: border-box; }}
:root {{ --ink:#14171a; --muted:#5b6672; --line:#d6dce2; --hair:#eef1f4;
  --teal:#0e5f6b; --indigo:#2f3f8f; --red:#a5312b; --amber:#a86400; --added:#fff9ef; }}
html,body {{ margin:0; padding:0; height:100%; }}
body {{ font:8.6pt/1.32 "Helvetica Neue",Helvetica,Arial,sans-serif; color:var(--ink);
  display:flex; flex-direction:column; min-height:100%;
  -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
header {{ border-bottom:2.2px solid var(--ink); padding-bottom:5px; margin-bottom:6px;
  display:flex; align-items:baseline; justify-content:space-between; }}
h1 {{ font-size:15pt; margin:0; letter-spacing:-.02em; }}
.hstat {{ font-size:7pt; color:var(--muted); }}
.grid {{ flex:1 1 auto; display:grid; grid-template-columns:1fr 92mm; gap:6mm; }}
table {{ border-collapse:collapse; width:100%; }}
th {{ text-align:left; font-size:6.6pt; text-transform:uppercase; letter-spacing:.07em;
  color:var(--muted); border-bottom:1.3px solid var(--ink); padding:0 5px 4px; }}
td {{ padding:8px 5px; border-bottom:1px solid var(--hair); vertical-align:top; }}
tr.added td {{ background:var(--added); }}
td.n {{ width:9mm; }}
td.n span {{ display:inline-block; width:15px; height:15px; line-height:15px; text-align:center;
  background:var(--ink); color:#fff; border-radius:50%; font-size:7pt; font-weight:700; }}
.tag {{ font-size:5.5pt; color:var(--amber); font-weight:700;
  letter-spacing:.06em; margin-top:2px; }}
td.name {{ width:32mm; font-weight:700; font-size:9pt; }}
.q {{ font-weight:400; font-size:7.2pt; color:var(--muted); margin-top:2px; }}
td.fail {{ width:62mm; color:var(--red); }}
td.guard {{ width:52mm; color:var(--teal);
  font-family:ui-monospace,Menlo,monospace; font-size:7pt; }}
.panel {{ border:1px solid var(--line); border-radius:3px; padding:7px 9px; }}
.panel h2 {{ font-size:7pt; text-transform:uppercase; letter-spacing:.09em; margin:0 0 7px;
  color:var(--muted); }}
.nq {{ border-left:2.5px solid var(--indigo); padding-left:8px; margin-bottom:8px; }}
.nqh {{ font-weight:700; font-size:8.6pt; margin-bottom:3px; }}
.badge {{ background:var(--indigo); color:#fff; font-size:6.8pt; padding:1px 5px;
  border-radius:2px; margin-right:4px; }}
.nqc {{ font-size:7.4pt; color:var(--teal); }}
.nqn {{ font-size:7.4pt; color:var(--muted); }}
.nqn b {{ color:var(--red); }}
footer {{ margin-top:auto; border-top:1.6px solid var(--ink); padding-top:7px; }}
.ftitle {{ font-size:6.6pt; text-transform:uppercase; letter-spacing:.09em;
  color:var(--muted); font-weight:700; margin-bottom:5px; }}
.phases {{ display:flex; flex-wrap:wrap; gap:4px; }}
.chip {{ border:1px solid var(--line); border-radius:3px; padding:3px 6px; background:#fafbfc;
  display:flex; gap:5px; align-items:center; }}
.chip .phase-n {{ font-weight:700; font-size:7pt; color:var(--muted); }}
.chip .phase-l {{ font-size:7pt; }}
.chip.now {{ background:var(--ink); border-color:var(--ink); }}
.chip.now .phase-n,.chip.now .phase-l {{ color:#fff; font-weight:700; }}
</style></head><body>
<header><h1>Project Architecture &mdash; Target-Safety GNN on a Biomedical Knowledge Graph</h1>
<div class="hstat">Generated from apps/site/src/data/architecture.ts</div></header>
<div class="grid">
<div><table><thead><tr><th>#</th><th>Layer &amp; what it answers</th>
<th>Failure if unguarded</th><th>Guard</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="panel"><h2>The three nested questions</h2>{nested}</div>
</div>
<footer><div class="ftitle">Delivery phases &mdash; current position highlighted</div>
<div class="phases">{chips}</div></footer>
</body></html>"""


def main() -> int:
    text = SITE_DATA.read_text(encoding="utf-8")
    layers = parse_layers(text)
    questions = parse_questions(text)
    print(f"LAYERS_PARSED {len(layers)}")
    print(f"QUESTIONS_PARSED {len(questions)}")
    if len(layers) != 9:
        print("REFUSED: expected 9 layers", file=sys.stderr)
        return 2
    if len(questions) != 3:
        print("REFUSED: expected 3 nested questions", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUT_DIR / "project-architecture.html"
    pdf_path = OUT_DIR / "project-architecture.pdf"
    html_path.write_text(build_html(layers, questions), encoding="utf-8")
    print(f"WROTE_HTML {html_path} bytes={html_path.stat().st_size}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A3",
            landscape=True,
            print_background=True,
            margin={"top": "9mm", "bottom": "9mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()
    print(f"WROTE_PDF {pdf_path} bytes={pdf_path.stat().st_size}")

    # IMPORTED, NOT SHELLED OUT. pypdf is declared in the e2e extra, so reading
    # the page count directly removes a subprocess with a partial executable path
    # and reports a real error instead of an empty stdout when it fails.
    from pypdf import PdfReader

    count = len(PdfReader(str(pdf_path)).pages)
    print(f"PAGE_COUNT {count}")
    return 0 if count == 1 else 3


if __name__ == "__main__":
    sys.exit(main())
