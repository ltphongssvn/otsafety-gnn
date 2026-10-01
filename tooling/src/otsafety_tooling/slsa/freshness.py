# tooling/src/otsafety_tooling/slsa/freshness.py
"""A freshness decision, shaped by the specification rather than by convenience.

THE REQUIREMENT CAME FIRST. in-toto's Statement v1 fixes what a claim about an
artifact must carry, and each part answers a question: the subject says what
was judged and binds it by digest, because a name means something different
tomorrow; the predicateType says which rule decided, as a versioned URI a
verifier can select on; the predicate carries the rest.

WHAT A FRESHNESS DECISION MUST IDENTIFY: the immutable revision judged, the
immutable base it was judged against, the rule that decided, what was observed,
the identity that executed it, the time, and the verdict. The first payload
here carried {base: "origin/develop", behind: 0} -- a branch name and a number,
from which nothing can be re-derived and against which nothing can be matched.

TWO SUBJECTS, NOT ONE. A decision about freshness is a claim about a PAIR: this
revision, against that base. Recording only the head leaves the question
unanswerable later, because origin/develop will have moved.

gitCommit BINDS A REVISION. The DigestSet specification defines it as the
lowercase hex SHA-1 or SHA-256 of a commit object, and SLSA's Source VSA binds
its subject the same way; hashing a revision string as file content would
produce a number nobody computes.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from otsafety_tooling.contracts.attestation import Digest, InTotoStatement, Subject

# THE RULE'S IDENTITY, as a URI carrying its major version: a verifier selects
# on this, and an incompatible change must change it rather than quietly
# altering what an old record meant.
PREDICATE_TYPE = "https://otsafety.thanhphongle.net/attestation/freshness/v1"

# THE BASE THIS RULE JUDGES AGAINST, named once. The remote-tracking ref, never
# a local branch: a local develop nobody updates is stale by construction.
BASE_REF = "origin/develop"


class FreshnessDecision(BaseModel):
    """The predicate: what was decided, on what observation, by whom, and when.

    THE VERDICT AND THE OBSERVATION MUST AGREE. A denial that records nothing
    behind cannot be re-derived from its own record, and an allowance recorded
    while behind is a contradiction a reader would have to resolve by guessing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: Literal["allow", "deny"]
    reason: str = Field(min_length=1)
    behind: NonNegativeInt
    # WHO RAN IT. A decision with no execution identity cannot be attributed,
    # and the same rule run by a person and by a hook are different events.
    executed_by: str = Field(min_length=1)
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def _the_verdict_follows_the_observation(self) -> Self:
        if self.verdict == "deny" and self.behind == 0:
            raise ValueError(
                "a denial must record how far behind it was, or it cannot be re-derived"
            )
        if self.verdict == "allow" and self.behind:
            raise ValueError(f"allowed while {self.behind} behind, which is a contradiction")
        return self


def decision_statement(
    *, head: str, base: str, decision: FreshnessDecision | dict[str, object]
) -> InTotoStatement:
    """The decision as an in-toto statement: two subjects, one rule, one predicate."""
    predicate = (
        decision
        if isinstance(decision, FreshnessDecision)
        else FreshnessDecision.model_validate(decision)
    )
    return InTotoStatement(
        subject=(
            Subject(name="HEAD", digest=Digest(git_commit=head)),
            Subject(name=BASE_REF, digest=Digest(git_commit=base)),
        ),
        predicate_type=PREDICATE_TYPE,
        predicate=predicate.model_dump(mode="json"),
    )
