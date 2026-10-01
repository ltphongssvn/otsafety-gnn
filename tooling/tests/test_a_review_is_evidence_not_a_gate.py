# tooling/tests/test_a_review_is_evidence_not_a_gate.py
"""A semantic review produces evidence a person reads, never a verdict (G.87).

THREE QUESTIONS OF INCREASING STRENGTH about a step's claim:

    does the id appear anywhere            -- formatting
    does a title's vocabulary have         -- G.85, mechanical and offline
      evidence of a compatible KIND
    does that evidence establish           -- this, and it needs a reader
      everything the sentence claims

AND THE THIRD CANNOT BE A GATE. Non-determinism in a language model persists at
temperature zero and under forced greedy decoding, because it originates before
the sampling step, in the forward pass. A judge that flips once blocks the same
change twice, and a gate's whole value is that its answer can be reproduced.

SO THE REVIEW IS RECORDED, NOT ENFORCED. It carries the contract that produced
it -- model id, rubric version, prompt hash -- and the variance across repeats
rather than one smoothed answer, so no single run becomes the authority. That
is what turns a judgement into evidence rather than an opinion.

PINNED, NEVER AN ALIAS. A model alias resolves to a different model every few
weeks, which makes a recorded review unreproducible for a reason nobody can see
afterwards.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.87")


def _judged(**overrides: object) -> dict[str, object]:
    return {
        "model": "claude-fable-5-1",
        "rubric": "does-the-evidence-establish-the-claim/v1",
        "prompt_sha256": "a" * 64,
        "repeats": 3,
        "agreed": 3,
        **overrides,
    }


def _review(**overrides: object) -> dict[str, object]:
    return {
        "contract": "semantic-review/v1",
        "reviewed_at": "2026-10-01T02:00:00Z",
        "step": "G.85",
        "claim": "The SLSA Source Level is computed from evidence and enforced by policy",
        "finding": "covered",
        "rationale": "the policy denies a missing record, a level below the floor, and a "
        "level disagreeing with its observation, which is what the title claims",
        "judge": _judged(),
        **overrides,
    }


def test_a_review_names_the_contract_that_produced_it() -> None:
    """MODEL, RUBRIC AND PROMPT ARE ONE TUPLE. Any of the three changing makes
    a different measurement, and a review that records only its answer cannot
    say which measurement it was.
    """
    from otsafety_tooling.contracts.semantic_review import SemanticReview

    review = SemanticReview.model_validate(_review())
    assert review.judge.model == "claude-fable-5-1"
    assert review.judge.rubric.endswith("/v1")
    assert len(review.judge.prompt_sha256) == 64


def test_a_model_alias_is_refused() -> None:
    """An alias resolves to a different model every few weeks, so a review
    naming one cannot be reproduced and cannot say why not."""
    from pydantic import ValidationError

    from otsafety_tooling.contracts.semantic_review import SemanticReview

    for alias in ("claude-sonnet-latest", "gpt-5", "sonnet"):
        with pytest.raises(ValidationError):
            SemanticReview.model_validate(_review(judge=_judged(model=alias)))


def test_disagreement_across_repeats_is_recorded_not_smoothed() -> None:
    """NO SINGLE RUN IS THE AUTHORITY. Repeats that disagree are the finding,
    and a review reporting one answer hides exactly what a reader needs."""
    from otsafety_tooling.contracts.semantic_review import SemanticReview

    split = SemanticReview.model_validate(_review(judge=_judged(repeats=5, agreed=3)))
    assert split.judge.unanimous is False
    assert split.judge.agreed == 3


def test_agreement_cannot_exceed_the_repeats() -> None:
    """A record whose arithmetic is impossible describes no run at all."""
    from pydantic import ValidationError

    from otsafety_tooling.contracts.semantic_review import SemanticReview

    with pytest.raises(ValidationError):
        SemanticReview.model_validate(_review(judge=_judged(repeats=2, agreed=3)))


def test_a_finding_outside_the_vocabulary_is_refused() -> None:
    """covered, partial, uncovered or unreadable -- and nothing else, because a
    free-text verdict is prose a harness would have to parse back into a
    decision, which is where a judge-driven gate flips."""
    from pydantic import ValidationError

    from otsafety_tooling.contracts.semantic_review import SemanticReview

    for word in ("probably", "LGTM", "pass"):
        with pytest.raises(ValidationError):
            SemanticReview.model_validate(_review(finding=word))


def test_an_uncovered_finding_must_say_what_is_missing() -> None:
    """A finding with no rationale cannot be acted on or disputed."""
    from pydantic import ValidationError

    from otsafety_tooling.contracts.semantic_review import SemanticReview

    with pytest.raises(ValidationError):
        SemanticReview.model_validate(_review(finding="uncovered", rationale=""))


def test_the_review_is_not_a_gate() -> None:
    """THE RULE THIS STEP EXISTS FOR. A judge that flips once blocks the same
    change twice; check must not run it, and no hook may either.
    """
    import ast as syntax

    from otsafety_tooling.contracts.files import read_yaml
    from otsafety_tooling.contracts.lefthook_config import LefthookConfig
    from otsafety_tooling.paths import REPO_ROOT

    gates = (REPO_ROOT / "scripts" / "check_all.py").read_text(encoding="utf-8")
    tree = syntax.parse(gates)
    named = {
        entry.elts[0].value
        for node in tree.body
        if isinstance(node, syntax.AnnAssign)
        and isinstance(node.target, syntax.Name)
        and node.target.id == "GATES"
        and isinstance(node.value, syntax.List)
        for entry in node.value.elts
        if isinstance(entry, syntax.Tuple) and isinstance(entry.elts[0], syntax.Constant)
    }
    assert named, "no gates read; the check would pass having examined nothing"
    assert "plan:review" not in named, "a judge is in the gate, and a gate must be reproducible"

    hooks = read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig)
    for hook in (hooks.pre_commit, hooks.pre_push, hooks.commit_msg):
        for job in hook.jobs if hook else ():
            assert "plan:review" not in job.run, f"a hook runs the judge: {job.name}"


def test_a_dateless_modern_model_is_pinned() -> None:
    """THE RULE IS A GENERATION BOUNDARY, NOT A SHAPE.

    From the 4.6 generation onward a model id is dateless AND a pinned
    snapshot: the weights behind an existing id are never updated, and a new
    version ships under a new id. Requiring a date suffix would refuse every
    current model while accepting only the older dated forms -- which is what
    my first pattern did.
    """
    from otsafety_tooling.contracts.semantic_review import SemanticReview

    for pinned in ("claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-4-6", "claude-opus-4-8"):
        SemanticReview.model_validate(_review(judge=_judged(model=pinned)))


def test_a_dated_older_model_is_pinned_too() -> None:
    """Before 4.6 the dateless form is the alias and the dated one is pinned."""
    from otsafety_tooling.contracts.semantic_review import SemanticReview

    SemanticReview.model_validate(_review(judge=_judged(model="claude-haiku-4-5-20251001")))


def test_a_dateless_older_model_is_an_alias_and_refused() -> None:
    """claude-sonnet-4-5 points at whatever snapshot is newest, so a review
    naming it cannot say which model answered."""
    from pydantic import ValidationError

    from otsafety_tooling.contracts.semantic_review import SemanticReview

    for alias in ("claude-sonnet-4-5", "claude-opus-4-1", "claude-3-5-haiku"):
        with pytest.raises(ValidationError):
            SemanticReview.model_validate(_review(judge=_judged(model=alias)))
