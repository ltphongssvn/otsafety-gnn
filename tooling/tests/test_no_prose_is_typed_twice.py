# tooling/tests/test_no_prose_is_typed_twice.py
"""No prose is typed twice, and the detector is proved able to see it (G.76).

THREE COPIES WERE FOUND BY SOMEONE ASKING. The nine layers at 8.5, the ladder at
G.66, then the research question itself at G.75 -- each typed in the sheet and
again on the site, each already diverged by the time anyone looked. A fourth
would have lasted just as long.

ITS OWN FILE, BECAUSE A MODULE CLAIMS ONE REQUIREMENT. A second pytestmark
assignment silently replaces the first, so the codemod refuses to stack them:
evidence pointing at a file another step already claims reads as complete and
unconfirmed, which is exactly what the matrix refused when G.76 named G.75's.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.76")

SHEET = REPO_ROOT / "scripts" / "build_arch_onepager.py"


def _shared_sentences(sources: dict[str, str]) -> list[str]:
    """Sentences appearing in more than one source, comments excluded.

    CONTENT, NOT COMMENTARY: an explanation written into two files is real
    duplication of the wrong kind, because a comment never reaches a reader and
    so cannot be the diverged claim this looks for.
    """
    import re

    def sentences(text: str) -> set[str]:
        without_comments = re.sub(r"^\s*(#|//).*$", " ", text, flags=re.M)
        plain = re.sub(r"<[^>]+>|&[a-z]+;|\s+", " ", without_comments)
        return {
            run.strip()
            for run in re.split(r"[.?!]\s", plain)
            if len(run.strip()) >= 60 and " " in run.strip()
        }

    seen: dict[str, str] = {}
    shared: list[str] = []
    for name, text in sources.items():
        for sentence in sentences(text):
            if sentence in seen and seen[sentence] != name:
                shared.append(f"{seen[sentence]} and {name}: {sentence[:60]}")
            seen.setdefault(sentence, name)
    return shared


def test_the_detector_fires_on_a_known_duplicate() -> None:
    """THE LIVENESS CONTROL, beside the assertion that depends on it.

    2026 practice audits a gate with two questions: can it pass without
    executing, and has it been PROVEN able to fire in this run? A pattern that
    matches nothing is evidence only once you have separately established that
    it can match -- a gate never observed failing has not been observed working.

    AN EXTERNAL PLANT WAS THE WRONG INSTRUMENT. My first attempt put the
    sentence somewhere the gate never scanned, so it passed when it should have
    failed. The control belongs in the same run as the claim it supports.
    """
    duplicate = (
        "Do the typed relationships in a public, open-source biomedical knowledge graph "
        "carry information that predicts drug-safety endpoints for protein targets"
    )
    assert _shared_sentences({"one": duplicate, "two": duplicate}), (
        "the detector cannot see a sentence written into two sources"
    )
    assert _shared_sentences({"one": duplicate, "two": "something else entirely"}) == []


def test_no_long_sentence_appears_in_two_renderers() -> None:
    """G.76: the gate that catches the fourth copy before someone asks.

    ACROSS EVERY RENDERER, not one named file. An earlier version compared the
    sheet against apps/site/src/data/architecture.ts and would have passed the
    moment that file was deleted -- which is exactly what happened to it.
    """
    renderers = {
        path.name: path.read_text(encoding="utf-8")
        for path in [SHEET, *sorted((REPO_ROOT / "apps" / "site" / "src").rglob("*.astro"))]
    }
    assert len(renderers) > 3, "too few renderers to compare; the gate would pass vacuously"
    shared = _shared_sentences(renderers)
    assert shared == [], f"{len(shared)} sentences typed in two renderers: {shared[:2]}"
