# tooling/tests/test_a_decision_is_spec_shaped.py
"""A decision carries what the specification says a decision carries (G.85).

DERIVED FROM THE MODEL, NOT FROM THE FIELDS I HAPPENED TO WRITE. in-toto's
Statement v1 fixes what a claim about an artifact must hold, and says why each
part exists:

    subject[].digest   the immutable thing judged -- "subject artifacts are
                       matched purely by digest", so a decision about a branch
                       NAME binds to nothing.
    predicateType      the rule that decided, an absolute URI whose major
                       version changes on any incompatible change.
    predicate          the type-specific content: verdict, observation, the
                       identity that executed it, and when.

THE FIRST PAYLOAD CARRIED {base, behind}. No revision, so nothing could be
re-checked; no rule identity, so nothing could select it; no execution identity
and no time, so nothing could be reconstructed. Pydantic fields with the
requirement invented afterwards.

gitCommit, NOT sha256. The DigestSet specification defines gitCommit as the
lowercase hex SHA-1 or SHA-256 of a git commit object, and v1.1.0 added it to
the pre-defined algorithms precisely so a revision can be a subject. SLSA's own
Source VSA binds its subject that way. A 40-character revision cannot be a
sha256, and E.37's Digest requires one.

AND THE COST IS KNOWN IN ADVANCE: sigstore-python rejects a statement whose
subject uses gitCommit, because its DigestSet is restricted to SHA-2 and SHA-3.
Signing one through that client means giving up the DSSE envelope. The shape
here follows the framework; the signing stage will have to say how it copes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.85")

HEAD = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
BASE = "0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a"


def _decision(**overrides: object) -> dict[str, object]:
    return {
        "verdict": "deny",
        "reason": "this branch is 3 commit(s) behind origin/develop",
        "behind": 3,
        "executed_by": "mise run start:fresh",
        "decided_at": "2026-09-30T19:16:45.091190Z",
        **overrides,
    }


def test_a_revision_is_bound_as_a_git_commit() -> None:
    """THE ALGORITHM NAME IS THE SPECIFICATION'S, not the nearest one to hand.

    DigestSet defines gitCommit for a git commit object; sha256 over 40 hex
    characters is not a thing any verifier computes.
    """
    from otsafety_tooling.contracts.attestation import Digest

    bound = Digest.model_validate({"gitCommit": HEAD})
    assert bound.git_commit == HEAD


def test_a_revision_that_is_not_a_commit_object_is_refused() -> None:
    """THE POSITIVE FIRST, IN THIS TEST, so the vacuity is impossible.

    This passed while Digest had no gitCommit field at all -- it refused every
    input, including the valid one, and reported that as the rule working. A
    check that reports a negative must first demonstrate it can report a
    positive, and relying on a sibling test to supply that leaves this one
    green when the sibling breaks.
    """
    from pydantic import ValidationError

    from otsafety_tooling.contracts.attestation import Digest

    accepted = Digest.model_validate({"gitCommit": HEAD})
    assert accepted.git_commit == HEAD, "the probe cannot accept, so it cannot refuse"

    for wrong in ("HEAD", "origin/develop", "A1B2C3D4" * 5, "a" * 39, ""):
        with pytest.raises(ValidationError):
            Digest.model_validate({"gitCommit": wrong})


def test_the_decision_binds_to_both_revisions() -> None:
    """A BRANCH NAME BINDS TO NOTHING: origin/develop means something else
    tomorrow. The revision judged and the base it was judged against are both
    subjects, each matched by digest.
    """
    from otsafety_tooling.slsa.freshness import decision_statement

    statement = decision_statement(head=HEAD, base=BASE, decision=_decision())
    named = {s.name: s.digest.git_commit for s in statement.subject}
    assert named == {"HEAD": HEAD, "origin/develop": BASE}


def test_the_rule_is_named_by_an_absolute_versioned_uri() -> None:
    """predicateType is what a verifier selects on, and its major version
    changes on any incompatible change -- so it is a URI, never a word."""
    from otsafety_tooling.slsa.freshness import PREDICATE_TYPE, decision_statement

    statement = decision_statement(head=HEAD, base=BASE, decision=_decision())
    assert statement.predicate_type == PREDICATE_TYPE
    assert PREDICATE_TYPE.startswith("https://")
    assert PREDICATE_TYPE.rstrip("/").rsplit("/", 1)[-1].startswith("v")


def test_the_predicate_carries_verdict_observation_identity_and_time() -> None:
    """The things a decision must identify, present in one document."""
    from otsafety_tooling.slsa.freshness import FreshnessDecision

    decided = FreshnessDecision.model_validate(_decision())
    assert decided.verdict == "deny"
    assert decided.behind == 3
    assert decided.executed_by == "mise run start:fresh"
    assert decided.decided_at.tzinfo is not None, "a time with no zone is not a time"
    assert "behind" in decided.reason


def test_a_verdict_outside_the_vocabulary_is_refused() -> None:
    """allow or deny. A third value is a decision nobody can act on."""
    from pydantic import ValidationError

    from otsafety_tooling.slsa.freshness import FreshnessDecision

    with pytest.raises(ValidationError):
        FreshnessDecision.model_validate(_decision(verdict="probably"))


def test_a_denial_must_say_how_far_behind_it_was() -> None:
    """A refusal with no observation cannot be re-derived from its record."""
    from pydantic import ValidationError

    from otsafety_tooling.slsa.freshness import FreshnessDecision

    with pytest.raises(ValidationError):
        FreshnessDecision.model_validate(_decision(verdict="deny", behind=0))


def test_an_allowance_is_zero_behind() -> None:
    """The other direction: allowing while behind is a contradiction."""
    from pydantic import ValidationError

    from otsafety_tooling.slsa.freshness import FreshnessDecision

    with pytest.raises(ValidationError):
        FreshnessDecision.model_validate(_decision(verdict="allow", behind=2))


def test_the_statement_still_validates_as_in_toto() -> None:
    """The change widens the digest; it does not leave the framework."""
    from otsafety_tooling.contracts.attestation import InTotoStatement
    from otsafety_tooling.slsa.freshness import decision_statement

    statement = decision_statement(head=HEAD, base=BASE, decision=_decision())
    again = InTotoStatement.model_validate_json(statement.model_dump_json(by_alias=True))
    assert again.type_ == "https://in-toto.io/Statement/v1"
    assert len(again.subject) == 2


def test_a_digest_carries_only_algorithms_it_has() -> None:
    """OMIT, NEVER NULL. A DigestSet maps an algorithm name to a string
    encoding of the digest; a null is not a digest, and a verifier iterating
    the map would try to hex-decode it. The same defect reached the wire in
    another project this year and its schema validator rejected the subject.

    STRUCTURAL, NOT PER-CALL-SITE. Relying on every caller to pass
    exclude_none is the fragility that made those nulls ship: the model emits
    the right shape however it is serialised.
    """
    from otsafety_tooling.contracts.attestation import Digest

    written = Digest.model_validate({"gitCommit": HEAD}).model_dump(mode="json", by_alias=True)
    assert written == {"gitCommit": HEAD}, f"a null reached the wire: {written}"

    both = Digest.model_validate({"gitCommit": HEAD, "sha256": "b" * 64})
    assert set(both.model_dump(mode="json", by_alias=True)) == {"gitCommit", "sha256"}


def test_the_statement_carries_no_nulls_in_its_digests() -> None:
    """The whole document, as a verifier would receive it."""
    from otsafety_tooling.slsa.freshness import decision_statement

    statement = decision_statement(head=HEAD, base=BASE, decision=_decision())
    written = statement.model_dump(mode="json", by_alias=True)
    for subject in written["subject"]:
        assert None not in subject["digest"].values(), subject
