# scripts/build_arch_onepager.py
"""
Generate the one-page Project Architecture sheet (A3 landscape) as HTML + PDF.

Every term used on the sheet is defined on the sheet. Q1/Q2/Q3 are spelled out
in full rather than referenced, because a reader who has to look elsewhere to
decode a label cannot check the argument.

Single source of truth: the data tables below. Edit data, re-run, both artifacts
regenerate. Docs-as-Code and Diagram-as-Code.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# FONTS ARE VENDORED AND PINNED, FOR THE SAME REASON EXECUTABLES ARE. The same
# HTML produced a 334KB pdf here and a 101KB one on a Linux runner: every face
# embedded was a macOS system font -- HelveticaNeue, Menlo, Arial, LucidaGrande --
# which a runner does not have, so Chromium substituted and embedded different
# glyphs. Every assertion still passed, because the text was there and it was one
# page: the artifact people download was not the artifact CI published. Both
# faces below are SIL Open Font Licence, so a public repository may carry them.
FONT_DIR = REPO_ROOT / "assets" / "fonts"
# STATIC FACES, NOT A VARIABLE FONT. The first attempt vendored InterVariable and
# Chromium embedded a system fallback instead, silently: the pdf was byte-identical
# whether the source was declared plain or with tech(variations), so the variable
# axis was the cause rather than the CSS. Chromium embeds a variable font into a
# pdf only if it can instantiate a static instance, and JetBrainsMono, static,
# embedded first time through the same code path. Each weight is its own file.
# (family, weight, style) -> (filename, sha256)
FONTS = {
    ("Inter", "400", "normal"): (
        "Inter-Regular.woff2",
        "e06f6b1bc553aaea4e4668023ed0ab0a147129c3107f511bc7d03d361b0ae085"),
    ("Inter", "700", "normal"): (
        "Inter-Bold.woff2",
        "fa888127b6da015b65569f0351f3b5c391ad928904951f1c20e9f8462a8d95ea"),
    ("Inter", "400", "italic"): (
        "Inter-Italic.woff2",
        "2d078cb3bc8f934740d53b39dd23b0678f2f97477e49ec785dd9d8acd8b96bfc"),
    ("JetBrainsMono", "400", "normal"): (
        "JetBrainsMono-Regular.woff2",
        "a9cb1cd82332b23a47e3a1239d25d13c86d16c4220695e34b243effa999f45f2"),
}
OUT = REPO_ROOT / "build" / "onepager"
OUT.mkdir(parents=True, exist_ok=True)

RESEARCH_QUESTION = (
    "Do the typed <b>relationships</b> in a public, open-source biomedical knowledge "
    "graph carry information that predicts drug-safety endpoints for protein targets "
    "&mdash; over and above what is predictable from the graph's bare connectivity "
    "statistics, and from target-level features that require no graph at all?"
)

DATA_NOTE = (
    "<b>DATA</b> &mdash; <b>Open Targets 26.03</b>, open Parquet: <b>target</b> "
    "(safety nested inside), <b>drug_warning</b> (Tier 1 labels), "
    "<b>evidence_clinical_precedence</b> (earns a negative), drug_mechanism_of_action, "
    "openfda_significant_adverse_drug_reactions (Tier 3). Hetionet / PrimeKG for "
    "replication. Endpoint DAG from <b>EFO</b> / MONDO / HPO; <b>MedDRA</b> is licensed "
    "and not redistributed."
)

STACK_NOTE = (
    "<b>STACK</b> &mdash; <b>uv 0.12.7</b> &middot; <b>bun 1.4.2</b> &middot; gh 2.101.0 "
    "&middot; <b>mise 2026.9.9</b>, each the vendor&#39;s artifact for darwin and linux, "
    "with its published <b>sha256</b> in <b>toolchain.json</b>; nix flake check runs "
    "every tool and asserts the version it reports. Astro 7.3.3 &middot; Python 3.13.15 "
    "&middot; PyG &middot; PyKEEN."
)

CENTRAL_GOAL = (
    "Establish, under a leakage- and confound-controlled protocol, whether relation-aware "
    "graph learning over a public biomedical KG yields a usable target-safety "
    "prioritisation signal &mdash; and quantify how much of any observed performance is "
    "attributable to the <b>relationships</b>, as opposed to node popularity or non-graph "
    "target biology. The deliverable is a defensible answer plus its evidence, "
    "<b>in either direction</b>."
)

ML_OBJECTIVE = (
    "Let the KG be a heterogeneous graph <b>G = (V, E, R)</b> with typed nodes and typed "
    "edges. Let <b>T</b> be the protein targets and <b>S</b> the safety "
    "endpoints (organ classes / adverse-event terms).<br><br>"
    "<b>Task:</b> learn <b>f : T &times; S &rarr; [0,1]</b>, the probability that "
    "modulating target <i>t</i> is associated with endpoint <i>s</i>.<br><br>"
    "This is <b>multi-label prediction over the target &times; endpoint slice</b>, not "
    "binary &quot;is this target risky&quot;. The brief says endpoint<b>s</b> &mdash; "
    "plural &mdash; and organ-class structure is the clinically meaningful unit; a single "
    "collapsed risky/not-risky label answers a different question.<br><br>"
    "<b>Evaluation:</b> held-out target&ndash;endpoint pairs under a temporal split (train "
    "on the graph as of cutoff &tau;, predict associations that became knowable after "
    "&tau;), plus a target-disjoint cold-start split."
)

NESTED = [
    dict(q="Q1", title="Is there any signal beyond node popularity?",
         contrast="GNN <b>vs</b> degree-only null "
                  "(LogisticRegression on log-degree, no biology, no relations)",
         null="The KG encodes <b>study attention</b>, not safety biology. "
              "The project returns a negative result &mdash; and that is a real finding."),
    dict(q="Q2", title="Does the graph help beyond non-graph target features?",
         contrast="GNN <b>vs</b> tabular GBM / MLP on target annotations only "
                  "(GTEx expression breadth, gnomAD pLI &amp; LOEUF, protein family, "
                  "subcellular localisation)",
         null="Graph structure adds nothing. Ship the cheaper tabular model and "
              "close the project."),
    dict(q="Q3", title="Do the relation TYPES carry the signal?",
         contrast="Relation-<b>aware</b> (R-GCN, CompGCN, HGT) <b>vs</b> "
                  "relation-<b>agnostic</b> (GraphSAGE, GAT on a collapsed single adjacency)",
         null="Connectivity matters; <i>relationships</i> per se do not. "
              "<b>Q3 is the literal research question in the brief</b> &mdash; if a "
              "relation-agnostic GNN matches a relation-aware one, the answer to "
              "&quot;can relationships be used to predict&quot; is <b>no, only "
              "connectivity can</b>."),
]

SWEEP = [
    ("No-graph control", "Q2",
     "sklearn HistGradientBoostingClassifier + tabular MLP &mdash; target annotations only"),
    ("Degree-only null", "Q1",
     "sklearn LogisticRegression on log1p(per-relation degree)"),
    ("Graph-topology GBM", "Q1",
     "sklearn HistGradientBoostingClassifier on PPR / betweenness / k-core / clustering"),
    ("Shallow KGE", "Q3",
     "PyKEEN ComplEx, PyKEEN RotatE &mdash; relation-typed, no message passing"),
    ("Relation-agnostic GNN", "Q3",
     "PyG GraphSAGE (SAGEConv), PyG GAT (GATConv) on data.to_homogeneous()"),
    ("Relation-aware GNN", "Q3",
     "PyG R-GCN (RGCNConv), CompGCN, PyG HGT (HGTConv) + degree-offset head"),
]

SWEEP_RULE = (
    "Identical split, identical negatives, identical endpoints, "
    "<b>&ge;5 seeds with bootstrap CIs</b>. One seed cannot resolve a 0.02 AP difference, "
    "and most reported GNN wins on biomedical KGs sit inside that band."
)

SCOPE_IN = [
    "Public, open-source KGs only. <b>Open Targets</b> is primary &mdash; it carries the "
    "target-safety widget (ToxCast, AOPWiki, ClinPGx).",
    "<b>Hetionet</b> / <b>PrimeKG</b> as secondary graphs, for cross-KG replication of "
    "whatever result Open Targets gives.",
    "AstraZeneca <b>BIKG</b> is the <i>architectural</i> reference only &mdash; it is "
    "internal and is not usable as data.",
]

SCOPE_SECONDARY = (
    "The brief says &quot;important biomedical endpoints, <b>with a particular focus on</b> "
    "drug safety&quot;. That phrasing requires the method to be endpoint-agnostic, so the "
    "same pipeline is run once on a non-safety endpoint (target&ndash;disease association) "
    "to test whether any success is method-general or safety-specific."
)

SCOPE_OUT = [
    "Molecular structure prediction",
    "Compound-level toxicity from chemistry",
    "Clinical decision support",
    "Anything requiring non-public data",
]

# origin: "spec" = in the original 5-layer model, "added" = inserted/appended
LAYERS = [
    dict(n="1", name="REALITY", origin="spec",
         q="Does modulating target T actually cause endpoint E?",
         fail="On-target biology conflated with drug pharmacology. The project asks about the first; all evidence is generated by the second.",
         guard="— unresolvable; declared in model card",
         code="—", data="Model-card limitation statement"),
    dict(n="2", name="SELECTION", origin="added",
         q="Which truths ever get the chance to become evidence?",
         fail="Study attention, who got dosed, indication and reporting bias. Degree bias and confounding by indication are BORN here — not in the model.",
         guard="audit/degree.py · data/attribution.py",
         code="Policy as Code — study-bias thresholds", data="Degree distribution snapshot"),
    dict(n="3", name="EVIDENCE", origin="spec",
         q="What have we actually observed?",
         fail="Undated or unprovenanced edges admitted, making temporal claims unverifiable.",
         guard="data/ingest.py — quarantine at ingest",
         code="Schema as Code — Edge contract", data="Provenance as Data — ReleasePin hash"),
    dict(n="4", name="ATTRIBUTION", origin="added",
         q="Drug-level observation to target-level claim. Which target did it?",
         fail="Uniform propagation makes the LABEL a function of target degree — re-importing the exact confound removed at layer 8.",
         guard="data/attribution.py — noisy-OR + Mantel-Haenszel",
         code="Transformation as Code", data="Evidence as Data — q vector, leak, crude/adj"),
    dict(n="5", name="LABELING RULE", origin="spec",
         q="How do we interpret the evidence?",
         fail="Unlabelled silently treated as negative; evidence tiers pooled so the label's meaning cannot be stated.",
         guard="data/labels.py — 3 states, tiers never pooled",
         code="Policy as Code — tier + earned-negative rules", data="Decisions as Data — per-target tier"),
    dict(n="6", name="DATASET LABEL", origin="spec",
         q="positive / earned-negative / unlabelled, per tier",
         fail="Multiaxiality corrupts the label matrix; a PT annotation becomes a false negative at ancestor level.",
         guard="data/ontology.py · models/hierarchy.py",
         code="Contract as Code — SafetyLabel + DAG", data="Contracts as Data — versioned label set"),
    dict(n="7", name="SPLIT", origin="added",
         q="Which labels does the model SEE vs get TESTED on?",
         fail="Interpolation split behind an extrapolation claim. Same labels + different split = a different scientific claim.",
         guard="data/splits.py · audit/leakage.py (DL1/2/3)",
         code="Acceptance Criteria as Code — cutoff", data="Verdict as Data — pass/fail + reason"),
    dict(n="8", name="MODEL", origin="spec",
         q="What can the GNN learn from it?",
         fail="A popularity detector with an excellent AUROC. Degree explains the score; biology does not.",
         guard="models/hetero_gnn.py — degree offset, partial rho",
         code="Model Config as Code — conf/model/*.yaml", data="Metrics as Data — per-seed, decile, level"),
    dict(n="9", name="VERDICT", origin="added",
         q="Promote or reject? At what operating point, on what evidence?",
         fail="A score shipped where a decision was required; no bound on what the model misses.",
         guard="eval/metrics.py · pipeline.py — conformal + card",
         code="SLO as Code — min_ap_lift, min_partial_rho", data="Attestation as Data — signed model card"),
]

# PHASES AND THREADS ARE OBSERVED, NOT TYPED, for the reason the status line is.
# What was here claimed thread A and B and D complete, C at 70 per cent, "41 tasks"
# and "22 tests", and omitted threads F and G entirely -- G being the largest in
# the plan at 42 of 53. Every figure was true when written.


# Execution spine. Each stage names the As-Code artifact that DEFINES it and the
# As-Data artifact it EMITS -- the two halves of every loop in the platform.
# gate names the badge, verified against pipeline.py: "HALT" = raises and the run
# stops (audit gate, line 118); "REJECT" = the run completes but the model is not
# promoted (promotion gate, line 191 -- a flag, not a stop; hard-fail lands in
# Phase 8). Distinguishing them keeps the sheet honest about which controls have
# teeth today.
STAGES = [
    dict(t="CONFIGURATION", s="conf/config.yaml + pinned OT release hash",
         c="Configuration as Code", d="Config as Data", gate=None),
    dict(t="VALIDATED CONTRACT", s="Pydantic v2 \u00b7 Edge, SafetyLabel, Split",
         c="Schema as Code", d="Contracts as Data", gate=None),
    dict(t="AUDIT GATE", s="leakage DL1/2/3 \u00b7 degree null \u00b7 neg-controls",
         c="Policy as Code", d="Verdict as Data", gate="HALT"),
    dict(t="MODEL FACTORY", s="GBM | ComplEx | SAGE/GAT | R-GCN/HGT",
         c="Model Config as Code", d="Lineage as Data", gate=None),
    dict(t="TRAINING \u00b7 5 SEEDS", s="identical split, negatives, endpoints",
         c="Pipeline as Code", d="Metrics as Data", gate=None),
    dict(t="PROMOTION GATE", s="OPA/Rego \u00b7 \u0394(rung 5 \u2212 rung 4)",
         c="SLO as Code", d="Decision as Data", gate="REJECT"),
    dict(t="SIGNED MODEL CARD", s="promote / reject + evidence chain",
         c="Governance as Code", d="Attestation as Data", gate=None),
]

BACKEDGE = (
    "A model inside this loop <b>amplifies the bias that produced it</b>. Hence the "
    "degree gate is a loop-breaker, not a metric &mdash; and every verdict is persisted, "
    "because a feedback loop you did not log cannot be audited."
)


def _facts() -> Mapping[str, object]:
    """The figures the sheet states, collected before it renders.

    THE RENDERER DOES NOT COLLECT. This runs inside a pinned image carrying
    Playwright and pypdf: no git, no PyYAML, not this repository's package. Every
    attempt to read the plan, count merges or inspect the tree failed there for a
    different missing tool, and each fix was a tool-shaped patch on a design
    mistake. 2026 practice for a generated document separates collection from
    rendering -- the collector runs where the tooling is, and this transforms the
    document it is handed. mise run sheet:facts writes it.
    """
    export = REPO_ROOT / "apps" / "site" / "src" / "content" / "sheet-facts.json"
    if not export.is_file():
        raise SystemExit(f"REFUSED: no facts at {export}; run mise run sheet:facts")
    loaded = json.loads(export.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit(f"REFUSED: {export} is not an object")
    return loaded


def status_line() -> str:
    """The status, in words, from the collected facts."""
    seen = _facts()
    return (
        f"{seen['steps_done']} of {seen['steps']} plan steps &middot; "
        f"{seen['ids']} requirement ids &middot; {seen['test_functions']} test functions, "
        f"{seen['merged_prs']} pull requests"
    )


def observed_status() -> Mapping[str, object]:
    """The collected facts, for anything that needs a figure rather than a line."""
    return _facts()


def phase_chips_data() -> list[tuple[str, str, str]]:
    """Each phase, as collected."""
    phases = _facts().get("phases")
    rows = phases if isinstance(phases, list) else []
    return [
        (str(r["id"]), str(r["title"]), str(r["state"])) for r in rows if isinstance(r, dict)
    ]


def thread_rows_data() -> list[tuple[str, str, int, str, str]]:
    """Each workstream, as collected."""
    threads = _facts().get("threads")
    rows = threads if isinstance(threads, list) else []
    return [
        (
            str(r["id"]),
            str(r["title"]),
            int(str(r["percent"])),
            str(r["state"]),
            f"{r['done']} of {r['total']} steps",
        )
        for r in rows
        if isinstance(r, dict)
    ]


def e(s: str) -> str:
    return html.escape(str(s))


def layer_rows() -> str:
    out = []
    for L in LAYERS:
        cls = "added" if L["origin"] == "added" else "spec"
        badge = '<span class="tag">NEW</span>' if L["origin"] == "added" else ""
        out.append(f"""
        <tr class="{cls}">
          <td class="num"><span class="n">{e(L['n'])}</span>{badge}</td>
          <td class="lname">{e(L['name'])}<div class="q">{e(L['q'])}</div></td>
          <td class="fail">{e(L['fail'])}</td>
          <td class="guard mono">{e(L['guard'])}</td>
          <td class="ac">{e(L['code'])}</td>
          <td class="ad">{e(L['data'])}</td>
        </tr>""")
    return "".join(out)


def nested_blocks() -> str:
    return "".join(f"""
      <div class="nq">
        <div class="nqh"><span class="qbadge">{e(N['q'])}</span>{e(N['title'])}</div>
        <div class="nqc"><b>Contrast:</b> {N['contrast']}</div>
        <div class="nqn"><b>If the contrast ties:</b> {N['null']}</div>
      </div>""" for N in NESTED)


def sweep_rows() -> str:
    return "".join(
        f'<tr><td class="sw1">{e(a)}</td><td class="sw2">{e(b)}</td>'
        f'<td class="sw3 mono">{c}</td></tr>' for a, b, c in SWEEP
    )


def phase_chips() -> str:
    return "".join(
        f'<div class="chip {st}"><span class="pn">{e(n)}</span>'
        f'<span class="pl">{e(nm)}</span></div>' for n, nm, st in phase_chips_data()
    )


def thread_rows() -> str:
    return "".join(f"""
      <div class="thread">
        <div class="th-head"><b>{e(k)}</b> {e(nm)}
          <span class="st {st}">{e(st)}</span></div>
        <div class="bar"><div class="fill {st}" style="width:{p}%"></div></div>
        <div class="th-note">{e(note)}</div>
      </div>""" for k, nm, p, st, note in thread_rows_data())


def flow_svg() -> str:
    """
    Render the execution spine as SVG. Geometry is computed, not hand-placed, so
    adding a stage to STAGES re-lays-out the whole diagram -- Diagram as Code.
    """
    BX, BW, BH, GAP, TOP = 30, 356, 29, 5, 16
    W = 400
    n = len(STAGES)
    last_bottom = TOP + n * BH + (n - 1) * GAP
    H = last_bottom + 38

    INK, MUT = "#14171a", "#5b6672"
    IND, GRN, RED, LINE = "#2f3f8f", "#1d6b45", "#a5312b", "#c9d2da"

    o = [f'<svg viewBox="0 0 {W} {H}" width="100%" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="Inter,sans-serif">',
         '<defs>'
         '<marker id="ar" markerWidth="7" markerHeight="7" refX="5.4" refY="2.6" '
         f'orient="auto"><path d="M0,0 L5.4,2.6 L0,5.2 z" fill="{INK}"/></marker>'
         '<marker id="arb" markerWidth="7" markerHeight="7" refX="5.4" refY="2.6" '
         f'orient="auto"><path d="M0,0 L5.4,2.6 L0,5.2 z" fill="{RED}"/></marker>'
         '</defs>']

    # column legend
    o.append(f'<rect x="{BX}" y="6" width="7" height="7" rx="1.5" fill="{IND}"/>'
             f'<text x="{BX+11}" y="12.5" font-size="6.6" fill="{MUT}">'
             f'AS CODE \u2014 what the system SHOULD do</text>')
    o.append(f'<rect x="{BX+190}" y="6" width="7" height="7" rx="1.5" fill="{GRN}"/>'
             f'<text x="{BX+201}" y="12.5" font-size="6.6" fill="{MUT}">'
             f'AS DATA \u2014 what it DID / DECIDED</text>')

    for i, S in enumerate(STAGES):
        y = TOP + i * (BH + GAP)
        gate = S["gate"]
        stroke, sw = (RED, 1.7) if gate else (LINE, 1.0)
        fill = "#fdf4f3" if gate else "#ffffff"
        o.append(f'<rect x="{BX}" y="{y}" width="{BW}" height="{BH}" rx="3.5" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        o.append(f'<text x="{BX+10}" y="{y+11.5}" font-size="8.4" font-weight="700" '
                 f'fill="{RED if gate else INK}">{S["t"]}</text>')
        if gate:
            bw_ = 31 if gate == "HALT" else 40
            o.append(f'<rect x="{BX+BW-9-bw_}" y="{y+3.5}" width="{bw_}" height="10" '
                     f'rx="2" fill="{RED}"/>'
                     f'<text x="{BX+BW-9-bw_/2}" y="{y+10.8}" font-size="5.9" '
                     f'font-weight="700" fill="#fff" text-anchor="middle">{gate}</text>')
        o.append(f'<text x="{BX+10}" y="{y+20.5}" font-size="6.4" fill="{MUT}" '
                 f'font-family="JetBrainsMono,monospace">{S["s"]}</text>')
        o.append(f'<text x="{BX+10}" y="{y+26.5}" font-size="6.1" fill="{IND}" '
                 f'font-weight="700">\u2023 {S["c"]}</text>')
        o.append(f'<text x="{BX+190}" y="{y+26.5}" font-size="6.1" fill="{GRN}" '
                 f'font-weight="700">\u2023 {S["d"]}</text>')

        if i < len(STAGES) - 1:
            cx = BX + BW / 2
            o.append(f'<line x1="{cx}" y1="{y+BH+0.5}" x2="{cx}" y2="{y+BH+GAP-0.5}" '
                     f'stroke="{INK}" stroke-width="1" marker-end="url(#ar)"/>')

    # back-edge: the loop that makes this not a pipeline
    my = TOP + BH / 2
    o.append(f'<path d="M {BX+BW/2} {last_bottom} L {BX+BW/2} {last_bottom+16} '
             f'L 11 {last_bottom+16} L 11 {my} L {BX-4} {my}" fill="none" '
             f'stroke="{RED}" stroke-width="1.3" stroke-dasharray="4,2.6" '
             f'marker-end="url(#arb)"/>')
    o.append(f'<text x="22" y="{last_bottom+28}" font-size="6.6" font-weight="700" '
             f'fill="{RED}">BACK-EDGE \u2014 this is a loop, not a pipeline</text>')
    o.append(f'<text x="22" y="{last_bottom+36.5}" font-size="6.2" fill="{MUT}">'
             f'deployment \u2192 layer 2 SELECTION \u2192 degree rises \u2192 '
             f'model re-ranks</text>')
    o.append("</svg>")
    return "".join(o)


def scope_items(items: list[str]) -> str:
    return "".join(f"<li>{i}</li>" for i in items)


def font_faces() -> str:
    """The vendored fonts, inlined, each verified against its recorded digest.

    A font that changed upstream fails here rather than silently altering the
    sheet -- the guarantee toolchain.json gives every executable.
    """
    blocks = []
    for (family, weight, style), (filename, digest) in FONTS.items():
        path = FONT_DIR / filename
        if not path.is_file():
            raise SystemExit(f"REFUSED: missing vendored font {path}")
        payload = path.read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != digest:
            raise SystemExit(f"REFUSED: {filename} is {actual}, not {digest}")
        encoded = base64.b64encode(payload).decode("ascii")
        blocks.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"font-style:{style};font-display:block;"
            f"src:url(data:font/woff2;base64,{encoded}) format('woff2');}}"
        )
    return "\n".join(blocks)


CSS = """
/* SIZE IS SET ONCE, BY pg.pdf(). Declaring it here too let the two
   disagree: the mediabox resolved to US Letter landscape on one machine
   and A3 on another, which is what paginated the sheet differently. */
@page { margin: 8mm 9mm; }
* { box-sizing: border-box; }
:root{
  --ink:#14171a; --muted:#5b6672; --line:#d6dce2; --hair:#eaeef2;
  --teal:#0e5f6b; --indigo:#2f3f8f; --amber:#a86400; --red:#a5312b; --green:#1d6b45;
  --addbg:#fff9ef; --addln:#e8c88a;
}
html,body{margin:0;padding:0;height:100%;}
body{font-family:'Inter',sans-serif;color:var(--ink);
  font-size:8.1pt;line-height:1.24;-webkit-print-color-adjust:exact;print-color-adjust:exact;
  display:flex;flex-direction:column;min-height:100%;}
.mono{font-family:'JetBrainsMono',monospace;font-size:7pt;}

header{border-bottom:2.2px solid var(--ink);padding-bottom:4px;margin-bottom:5px;
  display:flex;align-items:baseline;justify-content:space-between;gap:12px;}
h1{font-size:15pt;margin:0;letter-spacing:-.35px;font-weight:700;}
.hstat{font-size:7pt;color:var(--muted);text-align:right;}
.hstat b{color:var(--ink);}

.qband{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5mm;margin-bottom:2.5mm;}
.qcell{border:1px solid var(--line);border-radius:3px;padding:6px 8px;
  display:flex;flex-direction:column;}
.qcell.hero{background:#f5f8f9;border-color:#a9c3c9;border-left:3px solid var(--teal);}
.qcell h2{font-size:7.2pt;text-transform:uppercase;letter-spacing:.9px;margin:0 0 5px;
  color:var(--muted);font-weight:700;}
.qcell.hero h2{color:var(--teal);}
.qbody{font-size:8.3pt;line-height:1.36;}
.qnote{font-size:7.1pt;color:var(--muted);margin-top:auto;padding-top:5px;
  border-top:1px solid var(--hair);}

.grid{flex:1 1 auto;display:grid;grid-template-columns:1fr 96mm;gap:6mm;align-items:start;}

table{border-collapse:collapse;width:100%;}
thead th{font-size:6.5pt;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);
  text-align:left;padding:0 5px 3px;border-bottom:1.2px solid var(--ink);font-weight:700;}
tbody td{padding:3px 5px;border-bottom:1px solid var(--hair);vertical-align:top;}
tr.added td{background:var(--addbg);}
tr.added td.num{border-left:2.4px solid var(--addln);}
td.num{width:10mm;white-space:nowrap;}
.n{display:inline-block;width:14px;height:14px;line-height:14px;text-align:center;
  background:var(--ink);color:#fff;border-radius:50%;font-size:7pt;font-weight:700;}
.tag{display:block;font-size:5.4pt;color:var(--amber);font-weight:700;
  letter-spacing:.9px;margin-top:2px;}
td.lname{width:30mm;font-weight:700;font-size:8.6pt;letter-spacing:.5px;}
.q{font-weight:400;font-size:7pt;color:var(--muted);margin-top:2px;line-height:1.24;}
td.fail{width:54mm;color:var(--red);}
td.guard{width:42mm;color:var(--teal);}
td.ac{width:36mm;color:var(--indigo);}
td.ad{width:36mm;color:var(--green);}

.panel{border:1px solid var(--line);border-radius:3px;padding:4px 8px;margin-bottom:1.8mm;}
.panel h2{font-size:7pt;text-transform:uppercase;letter-spacing:.9px;margin:0 0 6px;
  color:var(--muted);font-weight:700;}

.nq{border-left:2.5px solid var(--indigo);padding:0 0 0 7px;margin-bottom:5px;}
.nq:last-child{margin-bottom:0;}
.nqh{font-weight:700;font-size:8.4pt;margin-bottom:3px;}
.qbadge{display:inline-block;background:var(--indigo);color:#fff;font-size:6.8pt;
  font-weight:700;padding:1px 5px;border-radius:2px;margin-right:5px;}
.nqc{font-size:7.3pt;color:var(--teal);margin-bottom:2px;}
.nqn{font-size:7.3pt;color:var(--muted);}
.nqn b{color:var(--red);}

.panel.sweep{margin-top:2.2mm;margin-bottom:0;}
.sw1{width:40mm;font-weight:700;font-size:7.4pt;}
.sw2{width:10mm;color:var(--indigo);font-weight:700;font-size:7.2pt;}
.sw3{color:var(--muted);}
.panel table td{padding:2.6px 3px;border-bottom:1px solid var(--hair);font-size:7.3pt;}
.swrule{font-size:7pt;color:var(--muted);margin-top:5px;padding-top:4px;
  border-top:1px solid var(--hair);}

.panel.flow{background:#fcfdfd;}
.panel.flow svg{display:block;width:100%;height:auto;}
.flownote{font-size:6.8pt;color:var(--muted);margin-top:5px;padding-top:5px;
  border-top:1px solid var(--hair);}
.flownote b{color:var(--red);}

footer{margin-top:auto;border-top:1.6px solid var(--ink);padding-top:4px;
  display:grid;grid-template-columns:1fr 82mm 80mm;gap:5mm;}
.ftitle{font-size:6.5pt;text-transform:uppercase;letter-spacing:.9px;color:var(--muted);
  font-weight:700;margin-bottom:4px;}
.scope{display:grid;grid-template-columns:1fr 46mm;gap:5mm;}
.scope ul{margin:0;padding-left:12px;font-size:7.1pt;}
.scope li{margin-bottom:1px;}
.outl li{color:var(--red);}
.sechead{font-size:6.6pt;font-weight:700;color:var(--green);margin-bottom:2px;}
.sechead.out{color:var(--red);}
.secondary{font-size:6.6pt;color:var(--muted);margin-top:3px;padding-top:3px;
  border-top:1px solid var(--hair);}
.phases{display:flex;flex-wrap:wrap;gap:3px;}
.chip{border:1px solid var(--line);border-radius:2.5px;padding:2px 5px;
  display:flex;align-items:center;gap:4px;background:#fafbfc;}
.chip .pn{font-weight:700;font-size:6.8pt;color:var(--muted);}
.chip .pl{font-size:6.6pt;}
.chip.now{background:var(--ink);border-color:var(--ink);}
.chip.now .pn,.chip.now .pl{color:#fff;font-weight:700;}
.threads{display:grid;grid-template-columns:1fr 1fr;gap:1px 4mm;}
.thread{margin-bottom:2px;}
.th-head{font-size:6.6pt;}
.th-head b{color:var(--indigo);}
.st{font-size:5.7pt;text-transform:uppercase;letter-spacing:.5px;padding:1px 4px;
  border-radius:2px;margin-left:4px;font-weight:700;}
.st.done{background:#dff0e6;color:var(--green);}
.st.active{background:#e6e9f7;color:var(--indigo);}
.st.todo{background:#eef1f4;color:var(--muted);}
.bar{height:2.5px;background:#eef1f4;border-radius:2px;margin:1.5px 0 1px;overflow:hidden;}
.fill{height:100%;}
.fill.done{background:var(--green);}
.fill.active{background:var(--indigo);}
.fill.todo{background:var(--line);}
.th-note{font-size:5.6pt;color:var(--muted);line-height:1.15;}
"""


def build_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Project Architecture — Target-Safety GNN</title>
<style>{font_faces()}{CSS}</style></head><body>

<header>
  <h1>Project Architecture &mdash; Target-Safety GNN on a Biomedical Knowledge Graph</h1>
  <div class="hstat"><b>Status</b> {status_line()} &middot; both trackers verified on Linux</div>
</header>

<div class="qband">
  <div class="qcell hero">
    <h2>The research question</h2>
    <div class="qbody">{RESEARCH_QUESTION}</div>
    <div class="qnote">{DATA_NOTE}</div>
  </div>
  <div class="qcell">
    <h2>Central goal</h2>
    <div class="qbody">{CENTRAL_GOAL}</div>
    <div class="qnote">{STACK_NOTE}</div>
  </div>
  <div class="qcell">
    <h2>The machine learning objective</h2>
    <div class="qbody">{ML_OBJECTIVE}</div>
  </div>
</div>

<div class="grid">
  <div>
    <table>
      <thead><tr>
        <th>#</th><th>Layer &amp; what it answers</th><th>Failure if unguarded</th>
        <th>Guard</th><th>As Code &mdash; intent</th><th>As Data &mdash; record</th>
      </tr></thead>
      <tbody>{layer_rows()}</tbody>
    </table>

    <div class="panel sweep">
      <h2>Required model sweep &mdash; every rung on an identical protocol</h2>
      <table><tbody>{sweep_rows()}</tbody></table>
      <div class="swrule">{SWEEP_RULE}</div>
    </div>
  </div>

  <div>
    <div class="panel">
      <h2>The three nested questions</h2>
      {nested_blocks()}
    </div>

    <div class="panel flow">
      <h2>How it runs &mdash; as code &rarr; execution &rarr; as data</h2>
      {flow_svg()}
      <div class="flownote">{BACKEDGE}</div>
    </div>
  </div>
</div>

<footer>
  <div>
    <div class="ftitle">Scope boundaries</div>
    <div class="scope">
      <div>
        <div class="sechead">IN SCOPE</div>
        <ul>{scope_items(SCOPE_IN)}</ul>
        <div class="secondary"><b>Secondary check required by the spec:</b>
          {SCOPE_SECONDARY}</div>
      </div>
      <div>
        <div class="sechead out">OUT OF SCOPE</div>
        <ul class="outl">{scope_items(SCOPE_OUT)}</ul>
      </div>
    </div>
  </div>
  <div>
    <div class="ftitle">Delivery phases &mdash; current position highlighted</div>
    <div class="phases">{phase_chips()}</div>
  </div>
  <div>
    <div class="ftitle">Workstreams</div>
    <div class="threads">{thread_rows()}</div>
  </div>
</footer>

</body></html>"""


CONTRACT = "command-outcome/v1"


def note(text: str) -> None:
    """Human-facing progress: stderr, never the payload channel."""
    sys.stderr.write(f"{text}\n")


# THE PAYLOAD IS JSON, AND THIS SCRIPT IS STANDARD LIBRARY ONLY: the contract
# model may not be installed where it runs, so the payload cannot be a Pydantic
# model. Mapping[str, object] is the honest stdlib type -- object rather than Any,
# so nothing is exempted from checking, and Mapping rather than dict because dict
# is INVARIANT in its value type: dict[str, str] is not a dict[str, object], which
# is what made an earlier alias need widening at every call site.
def emit(command: str, outcome: str, code: str, message: str, data: Mapping[str, object]) -> int:
    """The envelope on stdout, and the exit code the outcome carries.

    BUILT AS PLAIN DATA: this renders inside a pinned image carrying the renderer
    and the standard library, not this repository's contracts. A test validates
    the shape through the contract model, so a drift fails there, not in a caller.
    """
    envelope = {
        "contract": CONTRACT,
        "command": command,
        "outcome": outcome,
        "code": code,
        "message": message,
        "data": data,
    }
    sys.stdout.write(json.dumps(envelope) + "\n")
    return {"success": 0, "failed": 1, "refused": 2}[outcome]


def main() -> int:
    html_path = OUT / "project-architecture.html"
    pdf_path = OUT / "project-architecture.pdf"
    html_path.write_text(build_html(), encoding="utf-8")
    note(f"WROTE_HTML {html_path} bytes={html_path.stat().st_size}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(html_path.as_uri())
        # document.fonts.ready, NOT networkidle. The fonts are data: URIs and
        # issue no network request, so networkidle cannot mean they are applied.
        # This is correct on its own terms. It was NOT the cause of the one-page
        # versus two-page divergence, though it was committed claiming to be:
        # that was a phase chip wrapping after its column was narrowed.
        pg.wait_for_load_state("load")
        pg.evaluate("() => document.fonts.ready")
        applied = pg.evaluate("() => document.fonts.status")
        if applied != "loaded":
            raise SystemExit(f"REFUSED: fonts are {applied}, not loaded")
        note(f"FONTS {applied} ({pg.evaluate('() => document.fonts.size')} faces)")
        pg.pdf(path=str(pdf_path), width="420mm", height="297mm",
               print_background=True, prefer_css_page_size=False,
               margin={"top": "8mm", "bottom": "8mm", "left": "9mm", "right": "9mm"})
        b.close()
    note(f"WROTE_PDF {pdf_path} bytes={pdf_path.stat().st_size}")

    from pypdf import PdfReader

    # PAGE_COUNT IS THE MEASURE, AND THE ONLY ONE THAT PROVED HONEST. Two
    # attempts at a fill fraction were abandoned: dividing by clientHeight
    # measured the browser window, and dividing by the print box returned the
    # same 1.057 before and after real height was removed, because body is a
    # flex container pinned by min-height and scrollHeight reports the viewport.
    # A number that does not move when the layout does is worse than none.
    n = len(PdfReader(str(pdf_path)).pages)
    note(f"PAGE_COUNT {n}")
    sheet = {
        "html": str(html_path),
        "pdf": str(pdf_path),
        "bytes": pdf_path.stat().st_size,
        "pages": n,
    }
    if n != 1:
        # THE SHEET IS ONE PAGE OR IT IS NOT THE SHEET: a second page means the
        # content outgrew the design, which is a refusal, not a rendering error.
        return emit(
            "pdf:render", "refused", "sheet_not_one_page",
            f"the sheet rendered {n} pages; it is a one-page sheet", sheet,
        )
    return emit(
        "pdf:render", "success", "sheet_rendered",
        f"one page, {pdf_path.stat().st_size} bytes", sheet,
    )


if __name__ == "__main__":
    sys.exit(main())
