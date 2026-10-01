# tooling/src/otsafety_tooling/contracts/semantic_review.py
"""semantic-review/v1: whether a step's evidence establishes what its title claims.

THREE QUESTIONS OF INCREASING STRENGTH. Whether a requirement's id appears
anywhere is formatting. Whether a title's vocabulary has evidence of a
compatible KIND is G.85: mechanical, offline, and a gate. Whether that evidence
establishes everything the sentence claims needs a reader, and this records
what the reader found.

AND IT IS NOT A GATE. Non-determinism in a language model persists at
temperature zero and under forced greedy decoding, because it originates before
the sampling step, in the forward pass itself. A judge that flips once blocks
the same change twice, and a gate's whole value is that its answer can be
reproduced. So this produces evidence a person reads, and check never runs it.

THE CONTRACT THAT PRODUCED A REVIEW IS PART OF IT. Model, rubric and prompt are
one tuple: any of the three changing makes a different measurement, and a
record carrying only its answer cannot say which measurement it was.

PINNED IS A GENERATION BOUNDARY, NOT A SHAPE. From the 4.6 generation onward a
Claude model id is dateless AND a fixed snapshot: the weights behind an id are
never updated, and a new version ships under a new id. Before 4.6 the dateless
form is a convenience pointer that moves, and the dated form is the snapshot.
My first pattern demanded a date suffix, which would have refused every
current model while accepting only the older dated ones.

THE JUDGE IS claude-fable-5-1, chosen by the requirement rather than first. It
is the strongest widely released model, it pins by a dateless id from a
generation where dateless means fixed, and it returns structured outputs. Two
constraints are stated rather than left to surprise: it carries extra safety
measures around biology, and this repository's subject is drug safety --
though the reviewer reads plan titles and evidence paths, not protocols; and in
a CMEK organisation structured outputs are unavailable on Fable models.
claude-opus-5-5 is the fallback for either.

STRUCTURED OUTPUTS, NEVER A FORCED TOOL. On a model whose thinking is always
on, forcing a tool call makes it skip the thinking and squeeze its working-out
into the arguments -- which is why Fable 5.1 and Opus 5.5 refuse it outright.
For a reviewer that would be the worst failure available: the reasoning it
exists for, silently dropped. A response format constrains the answer and
keeps the thinking. That format cannot express string lengths or numeric
bounds, so this contract enforces them after the response arrives.

DISAGREEMENT IS THE FINDING, NOT NOISE TO SMOOTH. Repeats that split are
exactly what a reader needs, so the count that agreed travels with the count
that ran, and no single run becomes the authority. A prompted model is not an
accountability authority, which is why the finding is recorded beside the
deterministic evidence rather than in place of it.
"""

from __future__ import annotations

import re
from typing import ClassVar, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

# DATED BEFORE 4.6, DATELESS FROM IT. A pattern demanding a date refuses every
# current model; one accepting any dateless id admits the older aliases.
DATED = re.compile(r"^claude-[a-z]+-\d+-\d+-\d{8}$")
DATELESS = re.compile(r"^claude-[a-z]+-(?P<major>\d+)(?:-(?P<minor>\d+))?$")
FIRST_DATELESS_PINNED = (4, 6)

JUDGE_MODEL = "claude-fable-5-1"
FALLBACK_MODEL = "claude-opus-5-5"


def is_pinned(model: str) -> bool:
    """Whether this id names one fixed snapshot rather than a moving pointer."""
    if DATED.fullmatch(model):
        return True
    found = DATELESS.fullmatch(model)
    if found is None:
        return False
    generation = (int(found["major"]), int(found["minor"] or 0))
    return generation >= FIRST_DATELESS_PINNED


class Judge(BaseModel):
    """What produced a finding, in enough detail to ask for it again."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    rubric: str = Field(pattern=r"^[a-z0-9-]+/v\d+$")
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # HOW OFTEN IT WAS ASKED, and how often the answers matched.
    repeats: PositiveInt
    agreed: PositiveInt

    @field_validator("model")
    @classmethod
    def _names_one_snapshot(cls, value: str) -> str:
        if not is_pinned(value):
            raise ValueError(
                f"{value} is an alias or not a model id: a review naming one cannot say "
                "which model answered, because the pointer moves"
            )
        return value

    @model_validator(mode="after")
    def _agreement_fits_the_repeats(self) -> Self:
        if self.agreed > self.repeats:
            raise ValueError(
                f"{self.agreed} agreed out of {self.repeats} runs, which describes no run at all"
            )
        return self

    @property
    def unanimous(self) -> bool:
        """Whether every repeat gave the same answer."""
        return self.agreed == self.repeats


class SemanticReview(BaseModel):
    """One reading of whether a step's evidence establishes its claim."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CONTRACT_ID: ClassVar[str] = "semantic-review/v1"

    contract: Literal["semantic-review/v1"] = "semantic-review/v1"
    reviewed_at: AwareDatetime
    step: str = Field(min_length=1)
    # THE CLAIM AS IT WAS READ, carried with the finding: a title edited later
    # would otherwise leave a review that appears to be about something else.
    claim: str = Field(min_length=1)
    # A CLOSED VOCABULARY, because a free-text verdict is prose a harness would
    # have to parse back into a decision -- which is precisely where a
    # judge-driven gate flips on wording rather than on substance.
    finding: Literal["covered", "partial", "uncovered", "unreadable"]
    rationale: str = Field(min_length=1)
    judge: Judge
