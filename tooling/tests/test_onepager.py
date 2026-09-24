# tooling/tests/test_onepager.py
"""The one-page architecture sheet, built from the same data the site renders.

WHY THE SITE'S DATA AND NOT ITS OWN. The sheet and apps/site/src/data both state
the nine layers and the three nested questions. Two copies drift, and the drift
is invisible until someone reads them side by side. The generator reads the
TypeScript exports so there is one source and no second place to update.

WHY A TEST AND NOT A LOOK. The first version of this sheet named Q2 and Q3 in a
panel and defined them nowhere, and the delivery band still listed a phase for
architecture decision records after that practice was dropped. Both were caught
by reading, late. These assertions catch them at build time.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("8.2")

GENERATOR = REPO_ROOT / "scripts" / "build_arch_onepager.py"

# Phases as the revised plan states them. Phase 5 is deliberately absent: the
# rule against architecture decision records removed it, and a sheet that still
# advertises it is stale documentation of exactly the kind the rule forbids.
EXPECTED_PHASES = [
    "Ground truth",
    "Branch divergence",
    "GitFlow baseline",
    "Worktree",
    "Stack inventory",
    "Toolchain and tasks",
    "The site",
    "The PDF",
    "The GNN package",
    "Lightning AI",
    "Research execution",
]

FORBIDDEN = ["ADR", "architecture decision", "FAS OnDemand"]


def _generator_source() -> str:
    if not GENERATOR.is_file():
        pytest.fail(f"no generator at {GENERATOR}")
    return GENERATOR.read_text(encoding="utf-8")


def test_the_generator_exists_and_declares_every_phase() -> None:
    src = _generator_source()
    for phase in EXPECTED_PHASES:
        assert phase in src, f"the delivery band does not name the phase {phase!r}"


def test_the_generator_names_no_cancelled_practice() -> None:
    """A band advertising a phase that was cancelled is worse than no band.

    SCOPED TO THE PHASE DECLARATION, NOT THE WHOLE FILE. Grepping the source
    failed on the banner explaining why phase 5 is absent, which is the note a
    later reader most needs. What must not contain a cancelled practice is the
    band that is rendered, so that is what this reads.
    """
    src = _generator_source()
    block = src.split("PHASES = [", 1)[1].split("]", 1)[0]
    for term in FORBIDDEN:
        assert term not in block, f"the rendered phase band still names {term!r}"


def test_the_generator_declares_every_section_the_sheet_renders() -> None:
    """The sheet carries nine sections, and a generator missing one renders a
    page that looks complete and is not.

    An earlier version read these tables from apps/site/src/data for a single
    source of truth. The round trip through a plain-string parser silently
    dropped the inline emphasis, the As Code and As Data columns, the SVG
    execution spine and the workstream band, and the sheet rendered four of
    nine sections. Declaring them here and asserting the RENDERED pdf below is
    the trade that keeps the sheet whole.
    """
    src = _generator_source()
    for table in ("LAYERS", "NESTED", "SWEEP", "STAGES", "SCOPE_IN", "THREADS"):
        assert f"{table} = [" in src, f"the generator does not declare {table}"
    for fn in ("flow_svg", "thread_rows", "layer_rows"):
        assert f"def {fn}" in src, f"the generator does not render {fn}"


def test_the_generator_asserts_its_own_page_count() -> None:
    """A one-page sheet that silently becomes two pages is not a one-pager."""
    src = _generator_source()
    assert "PAGE_COUNT" in src, "the generator does not report its page count"


# --- the rendered sheet, when one has been built -----------------------------
# READING THE SOURCE IS NOT READING THE OUTPUT. The tests above check what the
# generator declares; these check what Chromium actually laid out. A section
# that is declared and then dropped by a layout error passes the first set and
# fails this one.

PDF = REPO_ROOT / "build" / "onepager" / "project-architecture.pdf"

REQUIRED_SECTIONS = [
    "THE RESEARCH QUESTION",
    "CENTRAL GOAL",
    "MACHINE LEARNING OBJECTIVE",
    "REQUIRED MODEL SWEEP",
    "THREE NESTED QUESTIONS",
    "HOW IT RUNS",
    "SCOPE BOUNDARIES",
    "DELIVERY PHASES",
]

REQUIRED_CONTENT = [
    "HALT",  # the audit gate stops the run
    "REJECT",  # the promotion gate does not
    "RotatE",  # the shallow-KGE rung
    "GraphSAGE",  # the relation-agnostic control that isolates Q3
    "Open Targets",
    "BIKG",
]


def _pdf_text() -> str:
    """The sheet's text, with whitespace removed.

    WHY WHITESPACE IS DISCARDED. The pdf stores each string as a single Tj with
    no kerning offsets at all, in an Identity-H subset that carries its ToUnicode
    map -- the characters and their order are exact. pypdf reconstructs word
    boundaries from glyph advance widths, and against a subsetted font it guesses
    wrong: "St at us", "T HE RESEARCH QUEST ION", "relat ionships". Asserting on
    its spacing tests the extractor's heuristic rather than the document, and it
    diverges between renderers, which is how it first appeared.

    Two probes were run and both came back negative before this was understood:
    disabling kerning changed nothing, and neutralising every letter-spacing rule
    changed nothing, because the offsets they would have produced were never
    there. The content stream said so.
    """
    if not PDF.is_file():
        pytest.skip(f"no sheet at {PDF}; run `mise run pdf:render`")
    pypdf = pytest.importorskip("pypdf", reason="the e2e extra is not installed")
    extracted: str = pypdf.PdfReader(str(PDF)).pages[0].extract_text()
    return "".join(extracted.split())


def _squeeze(value: str) -> str:
    """A probe, compared the same way the extracted text is."""
    return "".join(value.split())


def test_the_rendered_sheet_carries_every_section() -> None:
    text = _pdf_text().upper()
    for section in REQUIRED_SECTIONS:
        assert _squeeze(section) in text, f"the sheet does not render {section!r}"


def test_the_rendered_sheet_carries_the_content_a_reader_needs() -> None:
    text = _pdf_text()
    for item in REQUIRED_CONTENT:
        assert _squeeze(item) in text, f"the sheet does not render {item!r}"


def test_the_rendered_sheet_is_one_page() -> None:
    if not PDF.is_file():
        pytest.skip("no sheet built")
    pypdf = pytest.importorskip("pypdf")
    assert len(pypdf.PdfReader(str(PDF)).pages) == 1


def test_the_rendered_sheet_names_no_cancelled_practice() -> None:
    assert "ADR" not in _pdf_text()


# --- DATA and STACK in the question band --------------------------------------
# The research-question card carried a note on the words "whether" and
# "relationships". It was replaced by what a reader needs to judge feasibility:
# which data, under what licence, and which pinned tools reproduce the result.
# Every dataset name below was read off the 26.03 release listing.

DATA_TERMS = [
    "DATA",
    "Open Targets 26.03",
    "drug_warning",
    "evidence_clinical_precedence",
    "MedDRA",
    "EFO",
]

STACK_TERMS = [
    "STACK",
    "uv 0.12.7",
    "bun 1.4.2",
    "mise 2026.9.9",
    "toolchain.json",
    "sha256",
]

REMOVED_NOTE = "The operative word in the brief is"


def test_the_rendered_sheet_carries_the_data_block() -> None:
    text = _pdf_text()
    for term in DATA_TERMS:
        assert _squeeze(term) in text, f"the DATA block does not render {term!r}"


def test_the_rendered_sheet_carries_the_stack_block() -> None:
    text = _pdf_text()
    for term in STACK_TERMS:
        assert _squeeze(term) in text, f"the STACK block does not render {term!r}"


def test_the_research_question_note_is_gone() -> None:
    """Replaced, not appended: the space it held is where DATA now sits."""
    assert _squeeze(REMOVED_NOTE) not in _pdf_text()


# --- the sheet must be the same document on every machine ---------------------
# The same HTML produced a 334KB pdf on macOS and a 101KB one on a Linux runner.
# Every embedded face was a macOS system font -- HelveticaNeue, Menlo, Arial,
# LucidaGrande -- which Linux does not have, so Chromium substituted and embedded
# different glyphs. Every assertion still passed: the text was present and it was
# one page. A deliverable people download was not the deliverable CI published,
# and no gate could see it.
#
# THE FIX IS toolchain.json's: stop depending on what a machine happens to
# provide. The fonts are vendored, pinned by digest and embedded in the page.

VENDORED_FONTS = ("Inter", "JetBrainsMono")

# Faces that mean a machine's own fonts were used instead of the vendored ones.
SYSTEM_FONTS = (
    "HelveticaNeue",
    "Helvetica",
    "Menlo",
    "LucidaGrande",
    "Arial",
    "DejaVu",
    "Liberation",
    "Nimbus",
)


def _embedded_fonts() -> list[str]:
    if not PDF.is_file():
        pytest.skip(f"no sheet at {PDF}; run `mise run pdf:build`")
    pypdf = pytest.importorskip("pypdf", reason="the e2e extra is not installed")
    page = pypdf.PdfReader(str(PDF)).pages[0]
    names = []
    for ref in page["/Resources"].get("/Font", {}).values():
        base = ref.get_object().get("/BaseFont")
        if base:
            # Subset fonts are prefixed ABCDEF+; the face is what follows.
            names.append(str(base).lstrip("/").split("+")[-1])
    return names


def test_the_sheet_embeds_only_vendored_fonts() -> None:
    """A system font here means this pdf differs from the one CI publishes."""
    for face in _embedded_fonts():
        assert not face.startswith(SYSTEM_FONTS), (
            f"{face} is a system font: this sheet depends on the machine that built it"
        )


def test_the_sheet_embeds_the_fonts_it_declares() -> None:
    faces = _embedded_fonts()
    assert faces, "no fonts embedded at all"
    for vendored in VENDORED_FONTS:
        assert any(vendored in face for face in faces), (
            f"{vendored} is declared but not embedded; found {sorted(set(faces))}"
        )
