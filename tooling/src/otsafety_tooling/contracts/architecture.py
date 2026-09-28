# tooling/src/otsafety_tooling/contracts/architecture.py
"""architecture/v1: the nine layers and what guards each, stated once.

THEY WERE TYPED TWICE AND HAD ALREADY DIVERGED. The sheet's generator held nine
layers; apps/site/src/data/architecture.ts held nine more. REALITY's failure
read two sentences in one and one sentence in the other, and the site carried
neither the as-code nor the as-data column. The names matched, which is the
weakest agreement two copies can have, and nothing compared the rest.

BOTH SIDES ARE REQUIRED FIELDS, because they are exactly what the round trip
lost. A layer that names no as-code artifact and no as-data record is half a
row, and half a row renders as a complete one.
"""

from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Layer(BaseModel):
    """One layer of the model: what it answers, what fails, what guards it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # THE SITE KEYS ITS COLLECTION BY THIS. Astro's file() loader requires a
    # unique id on every entry, and its schema validates the entry WITH it, so a
    # contract that omits it cannot be the collection's schema.
    id: str = Field(min_length=1)
    n: str = Field(pattern=r"^[1-9]$")
    name: str = Field(min_length=3)
    # spec: in the original five-layer model. added: inserted by this project.
    origin: Literal["spec", "added"]
    question: str = Field(min_length=20)
    failure: str = Field(min_length=40)
    guard: str = Field(min_length=3)
    as_code: str = Field(min_length=1)
    as_data: str = Field(min_length=3)
    produced_by: tuple[str, ...] = Field(min_length=1)
    # What the layer is about, and what actually produces its observations. Where
    # these differ, the layer carries a gap; layer 1's is the project's largest.
    asks: str = Field(min_length=3)
    evidence_from: str = Field(min_length=3)
    # RESOLVABLE SEPARATES WORK FROM LIMITATION. A gap that engineering can close
    # is a step not yet done; one it cannot is a limitation that must travel with
    # every claim the model makes, which is why the card refuses without it.
    resolvable: bool

    @model_validator(mode="after")
    def _a_gap_between_a_thing_and_itself_is_no_gap(self) -> Self:
        """If the subject and its evidence agree, there is nothing to resolve."""
        if self.asks == self.evidence_from and not self.resolvable:
            raise ValueError(
                f"layer {self.n} calls its gap unresolvable while asking about "
                f"{self.asks} and drawing evidence from the same thing"
            )
        return self


class Stage(BaseModel):
    """One stage of the execution spine, and the gate it carries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=3)
    source: str = Field(min_length=3)
    as_code: str = Field(min_length=3)
    as_data: str = Field(min_length=3)
    gate: Literal["HALT", "REJECT"] | None = None


class Question(BaseModel):
    """One of the three nested questions, its contrast, and its null result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Literal["Q1", "Q2", "Q3"]
    title: str = Field(min_length=10)
    contrast: str = Field(min_length=20)
    if_it_ties: str = Field(min_length=30)


class Rung(BaseModel):
    """One rung of the ladder, and which question it answers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    # The rung's position on the ladder: "0" through "5", with "2b" for the
    # topology variant that sits beside the tabular control.
    n: str = Field(pattern=r"^[0-9][a-z]?$")
    name: str = Field(min_length=3)
    experiment: str = Field(min_length=3)
    asks: str = Field(min_length=10)
    models: str = Field(min_length=20)
    answers: Literal["Q1", "Q2", "Q3", "none"]
    # WHAT FOLLOWS IF NOTHING ABOVE BEATS IT. The rung's whole purpose: a
    # contrast that ties is a finding, and this is the finding it would be.
    if_not_beaten: str = Field(min_length=20)


class LadderRule(BaseModel):
    """What makes the ladder a comparison rather than a list of runs.

    A MODEL, NOT A STRING, because the site reads it as a collection entry and
    the loader requires an id on every entry -- the same reason a layer carries
    one. The contract describes what both sides consume.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    rule: str = Field(min_length=40)


class Claim(BaseModel):
    """What this project asks, why it asks it, and what answering means."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str = Field(min_length=80)
    goal: str = Field(min_length=80)
    objective: str = Field(min_length=80)
    # The data this rests on, and the check the brief's wording requires.
    data_note: str = Field(min_length=40)
    scope_note: str = Field(min_length=40)
    # THE TERMS THAT CARRY THE MEANING, named rather than marked up: a renderer
    # emphasises these however it emphasises anything.
    emphasise: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _every_emphasis_is_in_the_prose(self) -> Self:
        """An annotation pointing at nothing is worse than no annotation.

        A renderer looks each term up to emphasise it; one that appears nowhere
        is silently skipped, so the term drifts out of the prose and no one
        learns. That is how the markup and the words came apart in the first
        place.
        """
        prose = " ".join((self.question, self.goal, self.objective))
        missing = [term for term in self.emphasise if term not in prose]
        if missing:
            raise ValueError(f"emphasised terms that appear nowhere in the prose: {missing}")
        return self


class Architecture(BaseModel):
    """The architecture, stated once and read by the sheet, the site and the README."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CONTRACT_ID: ClassVar[str] = "architecture/v1"

    contract: Literal["architecture/v1"] = "architecture/v1"
    layers: tuple[Layer, ...] = Field(min_length=9, max_length=9)
    stages: tuple[Stage, ...] = Field(min_length=1)
    questions: tuple[Question, ...] = Field(min_length=3, max_length=3)
    rungs: tuple[Rung, ...] = Field(min_length=1)
    # WHAT MAKES THE LADDER A COMPARISON rather than a list of runs: identical
    # protocol on every rung, and enough seeds to resolve the difference claimed.
    claim: Claim
    ladder_rule: LadderRule
    scope_in: tuple[str, ...] = Field(min_length=1)
    scope_out: tuple[str, ...] = Field(min_length=1)
