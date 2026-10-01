# tooling/tests/test_a_claim_matches_its_evidence.py
"""A step's title may not promise what its evidence cannot observe (G.85).

THE DEFECT THIS EXISTS FOR. G.85 was titled "computed from evidence and
attested" and its acceptance criteria named a task, a Rego rule and a test --
none of which can see a signature. It closed on a claim nothing tested, and
only reading it caught that.

MECHANICAL, NOT SEMANTIC. Judging whether a test really asserts a requirement
needs a reader; this is narrower and decidable: certain words in a title name a
KIND of evidence, and a step using one must carry evidence of that kind.
Finding an id in a test name proves traceability formatting, not that the test
asserts anything -- so this checks the vocabulary rather than the meaning, and
says so.

THE RULE IS NOT A STYLE PREFERENCE. "Attested" and "signed" have a definition
in this repository: E.37 says a DSSE envelope over an in-toto statement, logged
for transparency. A step claiming one and proving it with a file path claims
something a reader will believe and nothing will check.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.85")


def test_a_title_promising_a_signature_needs_evidence_that_sees_one() -> None:
    """THE RULE: the promise and the proof must be of the same kind."""
    from otsafety_tooling.planning.claims import overclaimed

    promised = {
        "id": "X.1",
        "title": "The verdict is signed and logged for transparency",
        "done_when": [{"kind": "path", "path": "tooling/src/x.py"}],
    }
    assert "signed" in overclaimed(promised), overclaimed(promised)


def test_a_title_promising_nothing_special_is_left_alone() -> None:
    """THE CONTROL: a rule flagging every step would pass the test above."""
    from otsafety_tooling.planning.claims import overclaimed

    ordinary = {
        "id": "X.2",
        "title": "The site's TypeScript is type-checked by a gate",
        "done_when": [{"kind": "path", "path": "apps/site/tsconfig.json"}],
    }
    assert overclaimed(ordinary) == ()


def test_the_promise_is_satisfied_by_the_right_kind() -> None:
    """THE CONTRACT DECIDES WHAT A CLAIM CAN BE PROVED BY, and today none of
    the five kinds -- pr, release, path, task, proof -- can see a signature.

    My first version invented an "attestation" kind to satisfy the rule, which
    would have made it unsatisfiable rather than strict: a step could clear it
    only by declaring evidence the plan cannot express. So a promise of a
    signature is refused until the contract can prove one, which is G.86.
    """
    from typing import get_args

    from otsafety_tooling.contracts.plan import Evidence
    from otsafety_tooling.planning.claims import SEES_A_SIGNATURE

    members = get_args(get_args(Evidence)[0])
    declared = {get_args(m.model_fields["kind"].annotation)[0] for m in members}
    assert declared, "no kinds read; the check would pass having examined nothing"
    assert SEES_A_SIGNATURE.isdisjoint(declared), (
        f"{SEES_A_SIGNATURE & declared} can prove a signature now; the rule should allow it"
    )


def test_every_step_in_the_plan_claims_only_what_it_proves() -> None:
    """THE LIVE CHECK, over this repository's own plan.

    ONLY FINISHED STEPS ARE JUDGED. An open step naming evidence that does not
    exist yet is the plan describing the future, which G.67 already settled for
    tasks: judging those would make the gate refuse the plan for planning. A
    step whose evidence HOLDS has made its claim, and that claim must be one
    its evidence could support.
    """
    from otsafety_tooling.contracts.files import read_yaml
    from otsafety_tooling.contracts.plan import ProjectPlan
    from otsafety_tooling.paths import REPO_ROOT
    from otsafety_tooling.planning.claims import overclaimed
    from otsafety_tooling.planning.status import gather_facts, unmet

    plan = read_yaml(REPO_ROOT / "context" / "plan.yaml", ProjectPlan)
    assert plan.steps, "no steps read; the check would pass having examined nothing"

    facts = gather_facts(REPO_ROOT, "HEAD", merged_prs=frozenset)
    finished = [step for step in plan.steps if not unmet(plan, facts, step.id)]
    assert finished, "no finished steps; the check would pass vacuously"

    offenders = {
        step.id: words for step in finished if (words := overclaimed(step.model_dump(mode="json")))
    }
    assert offenders == {}, f"finished steps promising what they did not prove: {offenders}"


def test_the_scanner_catches_a_planted_overclaim() -> None:
    """THE LIVENESS CONTROL. A scanner that matched nothing would report the
    plan clean for the wrong reason, which is how this defect shipped once.
    """
    from otsafety_tooling.planning.claims import overclaimed

    planted = {
        "id": "X.4",
        "title": "A release is attested and verified before deploy",
        "done_when": [{"kind": "task", "name": "deploy:site"}],
    }
    assert overclaimed(planted), "the scanner cannot see a planted overclaim"


def test_a_title_defining_a_word_is_not_claiming_it() -> None:
    """THE ONE FALSE POSITIVE, EXCLUDED MECHANICALLY.

    E.37 is titled "Signed means a DSSE envelope over an in-toto statement,
    logged for transparency". It DEFINES the word rather than claiming anything
    was signed -- the step's whole product is the definition, and its evidence
    is the contract that states it.

    "MEANS" IS THE MARKER, not a judgement about meaning. A scanner carrying a
    known false positive gets suppressed wholesale within a week, so the
    exclusion is as narrow and as mechanical as the rule itself: a title whose
    signature word is followed by "means" is a definition.
    """
    from otsafety_tooling.planning.claims import overclaimed

    defining = {
        "id": "X.5",
        "title": "Signed means a DSSE envelope over an in-toto statement, logged",
        "done_when": [{"kind": "path", "path": "tooling/src/x/attestation.py"}],
    }
    assert overclaimed(defining) == ()

    claiming = {
        "id": "X.6",
        "title": "The model card is signed before it ships",
        "done_when": [{"kind": "path", "path": "tooling/src/x/card.py"}],
    }
    assert overclaimed(claiming) == ("signed",), "the exclusion swallowed a real claim"
