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
from dataclasses import dataclass
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

# The ablation ladder as the sheet states it. Every rung names the model that
# occupies it: a rung described in the abstract is not a falsifiable comparison,
# and the first rung NOT beaten is the research answer.
SWEEP = [
    (
        "No-graph control",
        "Q2",
        "sklearn HistGradientBoostingClassifier + tabular MLP \u2014 target annotations only",
    ),
    ("Degree-only null", "Q1", "sklearn LogisticRegression on log1p(per-relation degree)"),
    (
        "Graph-topology GBM",
        "Q1",
        "sklearn HistGradientBoostingClassifier on PPR / betweenness / k-core / clustering",
    ),
    (
        "Shallow KGE",
        "Q3",
        "PyKEEN ComplEx, PyKEEN RotatE \u2014 relation-typed, no message passing",
    ),
    (
        "Relation-agnostic GNN",
        "Q3",
        "PyG GraphSAGE (SAGEConv), PyG GAT (GATConv) on a collapsed adjacency",
    ),
    (
        "Relation-aware GNN",
        "Q3",
        "PyG R-GCN (RGCNConv), CompGCN, PyG HGT (HGTConv) + degree-offset head",
    ),
]

SWEEP_RULE = (
    "Identical split, identical negatives, identical endpoints, at least five seeds "
    "with bootstrap confidence intervals. One seed cannot resolve a 0.02 difference "
    "in average precision, and most reported wins on biomedical knowledge graphs sit "
    "inside that band."
)

# gate names the badge: HALT raises and the run stops; REJECT completes the run
# but does not promote the model.
STAGES = [
    (
        "CONFIGURATION",
        "conf/config.yaml + pinned release hash",
        "Configuration as Code",
        "Config as Data",
        "",
    ),
    (
        "VALIDATED CONTRACT",
        "Pydantic v2 \u00b7 Edge, SafetyLabel, Split",
        "Schema as Code",
        "Contracts as Data",
        "",
    ),
    (
        "AUDIT GATE",
        "leakage DL1/2/3 \u00b7 degree null \u00b7 neg-controls",
        "Policy as Code",
        "Verdict as Data",
        "HALT",
    ),
    (
        "MODEL FACTORY",
        "GBM | ComplEx | SAGE/GAT | R-GCN/HGT",
        "Model Config as Code",
        "Lineage as Data",
        "",
    ),
    (
        "TRAINING \u00b7 5 SEEDS",
        "identical split, negatives, endpoints",
        "Pipeline as Code",
        "Metrics as Data",
        "",
    ),
    ("PROMOTION GATE", "\u0394(rung 5 \u2212 rung 4)", "SLO as Code", "Decision as Data", "REJECT"),
    (
        "SIGNED MODEL CARD",
        "promote / reject + evidence chain",
        "Governance as Code",
        "Attestation as Data",
        "",
    ),
]

BACK_EDGE = (
    "A model inside this loop amplifies the bias that produced it. Hence the degree "
    "gate is a loop-breaker, not a metric \u2014 and every verdict is persisted, "
    "because a feedback loop you did not log cannot be audited."
)


@dataclass(frozen=True)
class Sheet:
    """Everything the sheet renders, read from the site's data.

    A dict[str, object] made every value opaque: mypy cannot iterate an object,
    and one annotation was hiding six different shapes.
    """

    layers: list[dict[str, str]]
    questions: list[dict[str, str]]
    question: str
    question_note: str
    goal: str
    objective: list[str]
    scope: list[tuple[str, list[str]]]
    scope_note: str


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


def _elements(block: str) -> list[str]:
    """Split a TypeScript array of strings into its elements.

    SPLITTING ON THE COMMA CONSUMES THE CLOSING QUOTE. An earlier version split
    on '",' followed by a newline, which left every element after the first
    opening with a quote it never closed: the quoted-string pattern then matched
    nothing and three of four scope items rendered as empty. Match the quoted
    strings first, and group them by the line they start on, so a string
    concatenated across lines joins and a new element starts.
    """
    parts: list[str] = []
    current: list[str] = []
    ends_with_comma = True
    for line in block.splitlines():
        quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', line)
        if not quoted:
            continue
        if ends_with_comma and current:
            parts.append("".join(current))
            current = []
        current.extend(unescape(q) for q in quoted)
        ends_with_comma = line.rstrip().endswith(",")
    if current:
        parts.append("".join(current))
    return [p for p in parts if p.strip()]


def parse_string(text: str, name: str) -> str:
    """Read a single-string export, joining its concatenated parts."""
    block = text.split(f"export const {name} =", 1)[1].split(";", 1)[0]
    return "".join(unescape(m) for m in re.findall(r'"((?:[^"\\]|\\.)*)"', block))


def parse_string_list(text: str, name: str) -> list[str]:
    """Read an array-of-strings export, joining each element's parts.

    Elements are separated by a comma that follows a closing quote, so the split
    is on the quote boundary rather than on commas inside the strings.
    """
    block = text.split(f"export const {name}", 1)[1].split("];", 1)[0]
    block = block.split("[", 1)[1]
    return _elements(block)


def parse_scope(text: str) -> list[tuple[str, list[str]]]:
    block = text.split("export const SCOPE:", 1)[1].split("\n];", 1)[0]
    out: list[tuple[str, list[str]]] = []
    for section in re.findall(r'heading:\s*"([^"]+)",\s*items:\s*\[(.*?)\]\}', block, re.S):
        heading, body = section
        out.append((heading, _elements(body)))
    return out


def build_html(ctx: Sheet) -> str:
    layers = ctx.layers
    questions = ctx.questions
    tag = '<div class="tag">NEW</div>'

    rows = "".join(
        f'''<tr class="{"added" if l["added"] == "true" else ""}">
        <td class="n"><span>{l["n"]}</span>{tag if l["added"] == "true" else ""}</td>
        <td class="name">{unescape(l["name"])}
        <div class="q">{unescape(l["question"])}</div></td>
        <td class="fail">{unescape(l["failure"])}</td>
        <td class="guard">{unescape(l["guard"])}</td></tr>'''
        for l in layers  # noqa: E741
    )
    nested = "".join(
        f"""<div class="nq"><div class="nqh"><span class="badge">{q["id"]}</span>
        {unescape(q["question"])}</div>
        <div class="nqc"><b>Contrast:</b> {unescape(q["contrast"])}</div>
        <div class="nqn"><b>If the contrast ties:</b> {unescape(q["whenTied"])}</div></div>"""
        for q in questions
    )
    sweep = "".join(
        f'<tr><td class="sw1">{n}</td><td class="sw2">{q}</td><td class="sw3">{m}</td></tr>'
        for n, q, m in SWEEP
    )
    stages = "".join(
        f"""<div class="stage {"gate" if g else ""}">
        <div class="sh">{t}{f'<span class="badge-g">{g}</span>' if g else ""}</div>
        <div class="ss">{sub}</div>
        <div class="st"><span class="c">&#9656; {c}</span>
        <span class="d">&#9656; {d}</span></div></div>"""
        for t, sub, c, d, g in STAGES
    )
    scope = "".join(
        f"""<div class="sc"><div class="sch">{h}</div>
        <ul>{"".join(f"<li>{i}</li>" for i in items)}</ul></div>"""
        for h, items in ctx.scope
    )
    objective = "".join(f"<p>{para}</p>" for para in ctx.objective)
    chips = "".join(
        f"""<div class="chip {"now" if n == CURRENT_PHASE else ""}">
        <span class="phase-n">{n}</span><span class="phase-l">{label}</span></div>"""
        for n, label in PHASES
    )

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Project Architecture &mdash; otsafety-gnn</title><style>
@page {{ size: A3 landscape; margin: 8mm 9mm; }}
* {{ box-sizing: border-box; }}
:root {{ --ink:#14171a; --muted:#5b6672; --line:#d6dce2; --hair:#eef1f4;
  --teal:#0e5f6b; --indigo:#2f3f8f; --red:#a5312b; --amber:#a86400;
  --green:#1d6b45; --added:#fff9ef; }}
html,body {{ margin:0; padding:0; height:100%; }}
body {{ font:7.6pt/1.28 "Helvetica Neue",Helvetica,Arial,sans-serif; color:var(--ink);
  display:flex; flex-direction:column; min-height:100%;
  -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
header {{ border-bottom:2.2px solid var(--ink); padding-bottom:4px; margin-bottom:4px;
  display:flex; align-items:baseline; justify-content:space-between; }}
h1 {{ font-size:14pt; margin:0; letter-spacing:-.02em; }}
.hstat {{ font-size:6.6pt; color:var(--muted); }}
.band {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:4mm; margin-bottom:3.5mm; }}
.cell {{ border:1px solid var(--line); border-radius:3px; padding:6px 8px;
  display:flex; flex-direction:column; }}
.cell.hero {{ background:#f5f8f9; border-left:3px solid var(--teal); }}
.cell h2 {{ font-size:6.6pt; text-transform:uppercase; letter-spacing:.09em;
  margin:0 0 4px; color:var(--muted); }}
.cell .body {{ font-size:7.6pt; line-height:1.34; }}
.cell .body p {{ margin:0 0 4px; }}
.note {{ font-size:6.6pt; color:var(--muted); margin-top:auto; padding-top:4px;
  border-top:1px solid var(--hair); }}
.grid {{ flex:1 1 auto; display:grid; grid-template-columns:1fr 88mm; gap:5mm; }}
table {{ border-collapse:collapse; width:100%; }}
th {{ text-align:left; font-size:6.2pt; text-transform:uppercase; letter-spacing:.07em;
  color:var(--muted); border-bottom:1.3px solid var(--ink); padding:0 4px 3px; }}
td {{ padding:4.5px 4px; border-bottom:1px solid var(--hair); vertical-align:top; }}
tr.added td {{ background:var(--added); }}
td.n {{ width:8mm; }}
td.n span {{ display:inline-block; width:13px; height:13px; line-height:13px;
  text-align:center; background:var(--ink); color:#fff; border-radius:50%;
  font-size:6.4pt; font-weight:700; }}
.tag {{ font-size:5pt; color:var(--amber); font-weight:700; margin-top:1px; }}
td.name {{ width:28mm; font-weight:700; font-size:8pt; }}
.q {{ font-weight:400; font-size:6.6pt; color:var(--muted); margin-top:1px; }}
td.fail {{ width:56mm; color:var(--red); }}
td.guard {{ width:46mm; color:var(--teal); font-family:ui-monospace,Menlo,monospace;
  font-size:6.4pt; }}
.panel {{ border:1px solid var(--line); border-radius:3px; padding:6px 8px; margin-bottom:3mm; }}
.panel h2 {{ font-size:6.6pt; text-transform:uppercase; letter-spacing:.09em;
  margin:0 0 5px; color:var(--muted); }}
.nq {{ border-left:2.5px solid var(--indigo); padding-left:7px; margin-bottom:6px; }}
.nqh {{ font-weight:700; font-size:7.8pt; margin-bottom:2px; }}
.badge {{ background:var(--indigo); color:#fff; font-size:6.2pt; padding:1px 4px;
  border-radius:2px; margin-right:3px; }}
.nqc {{ font-size:6.8pt; color:var(--teal); }}
.nqn {{ font-size:6.8pt; color:var(--muted); }}
.nqn b {{ color:var(--red); }}
.sw1 {{ width:34mm; font-weight:700; font-size:6.8pt; }}
.sw2 {{ width:8mm; color:var(--indigo); font-weight:700; font-size:6.6pt; }}
.sw3 {{ color:var(--muted); font-family:ui-monospace,Menlo,monospace; font-size:6.2pt; }}
.swrule {{ font-size:6.4pt; color:var(--muted); margin-top:4px; padding-top:3px;
  border-top:1px solid var(--hair); }}
.stage {{ border:1px solid var(--line); border-radius:3px; padding:3px 6px; margin-bottom:2px; }}
.stage.gate {{ border-color:var(--red); background:#fdf4f3; }}
.sh {{ font-weight:700; font-size:7.2pt; }}
.stage.gate .sh {{ color:var(--red); }}
.badge-g {{ background:var(--red); color:#fff; font-size:5.4pt; font-weight:700;
  padding:1px 4px; border-radius:2px; margin-left:4px; }}
.ss {{ font-size:6pt; color:var(--muted); font-family:ui-monospace,Menlo,monospace; }}
.st {{ font-size:5.8pt; font-weight:700; display:flex; gap:8px; }}
.st .c {{ color:var(--indigo); }}
.st .d {{ color:var(--green); }}
.loop {{ font-size:6.4pt; color:var(--red); margin-top:4px; }}
footer {{ margin-top:auto; border-top:1.6px solid var(--ink); padding-top:5px;
  display:grid; grid-template-columns:1fr 96mm; gap:5mm; }}
.ftitle {{ font-size:6.2pt; text-transform:uppercase; letter-spacing:.09em;
  color:var(--muted); font-weight:700; margin-bottom:4px; }}
.scopes {{ display:grid; grid-template-columns:1fr 46mm; gap:4mm; }}
.sch {{ font-size:6.2pt; font-weight:700; color:var(--green); margin-bottom:2px; }}
.sc ul {{ margin:0; padding-left:11px; font-size:6.6pt; }}
.scnote {{ font-size:6.2pt; color:var(--muted); margin-top:3px; padding-top:3px;
  border-top:1px solid var(--hair); }}
.phases {{ display:flex; flex-wrap:wrap; gap:3px; }}
.chip {{ border:1px solid var(--line); border-radius:3px; padding:2px 5px;
  background:#fafbfc; display:flex; gap:4px; align-items:center; }}
.chip .phase-n {{ font-weight:700; font-size:6.2pt; color:var(--muted); }}
.chip .phase-l {{ font-size:6.2pt; }}
.chip.now {{ background:var(--ink); border-color:var(--ink); }}
.chip.now .phase-n,.chip.now .phase-l {{ color:#fff; font-weight:700; }}
</style></head><body>
<header><h1>Project Architecture &mdash; Target-Safety GNN on a Biomedical Knowledge Graph</h1>
<div class="hstat">Generated from apps/site/src/data/architecture.ts</div></header>
<div class="band">
  <div class="cell hero"><h2>The research question</h2>
    <div class="body">{ctx.question}</div>
    <div class="note">{ctx.question_note}</div></div>
  <div class="cell"><h2>Central goal</h2>
    <div class="body">{ctx.goal}</div></div>
  <div class="cell"><h2>The machine learning objective</h2>
    <div class="body">{objective}</div></div>
</div>
<div class="grid">
  <div>
    <table><thead><tr><th>#</th><th>Layer &amp; what it answers</th>
    <th>Failure if unguarded</th><th>Guard</th></tr></thead><tbody>{rows}</tbody></table>
    <div class="panel" style="margin-top:3mm">
      <h2>Required model sweep &mdash; every rung on an identical protocol</h2>
      <table><tbody>{sweep}</tbody></table>
      <div class="swrule">{SWEEP_RULE}</div></div>
  </div>
  <div>
    <div class="panel"><h2>The three nested questions</h2>{nested}</div>
    <div class="panel"><h2>How it runs &mdash; as code &rarr; execution &rarr; as data</h2>
      {stages}<div class="loop">{BACK_EDGE}</div></div>
  </div>
</div>
<footer>
  <div><div class="ftitle">Scope boundaries</div>
    <div class="scopes">{scope}</div>
    <div class="scnote">{ctx.scope_note}</div></div>
  <div><div class="ftitle">Delivery phases &mdash; current position highlighted</div>
    <div class="phases">{chips}</div></div>
</footer>
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
    ctx = Sheet(
        layers=layers,
        questions=questions,
        question=parse_string(text, "RESEARCH_QUESTION"),
        question_note=parse_string(text, "RESEARCH_QUESTION_NOTE"),
        goal=parse_string(text, "CENTRAL_GOAL"),
        objective=parse_string_list(text, "ML_OBJECTIVE"),
        scope=parse_scope(text),
        scope_note=parse_string(text, "SCOPE_NOTE"),
    )
    if not ctx.question or len(ctx.scope) != 2:
        print("REFUSED: the framing exports did not parse", file=sys.stderr)
        return 2
    html_path.write_text(build_html(ctx), encoding="utf-8")
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
