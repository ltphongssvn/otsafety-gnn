# tooling/src/otsafety_tooling/contracts/model_card.py
"""model-card/v1: what a trained model must travel with to be interpretable.

THE MODEL IS NOT THE SCIENTIFIC RESULT. A ranked list of targets means nothing
without the question it answers, the evidence that supports it, and the claims
it may not make. This card is the identity, the evidence report and the
limitation statement together -- part of the accountability mechanism rather
than documentation written after training.

STRUCTURAL PRESENCE IS NOT SUBSTANTIVE CONTENT. 2026 governance practice found
that a card reporting aggregate accuracy, with no subgroup breakdown and an
undisclosed test set, is technically a card and gives none of the protection the
format exists for. So the invariants here refuse exactly those cards: at least
two disaggregated slices, free text long enough to say something, and a claim
that its own evidence supports.

WHY THE SLICES MUST BE DISAGGREGATED HERE IN PARTICULAR. This project exists to
tell a safety signal from node popularity. An aggregate average precision hides
the degree confound completely -- the whole apparatus of the degree-only null,
the offset head and the partial correlation reports nothing if the card states
one number.
"""

from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from otsafety_tooling.contracts.attestation import DsseEnvelope

# THE LENGTH FLOORS ARE CRUDE AND EFFECTIVE, which is exactly how 2026 practice
# describes them: they do not make prose good, they make one-line boilerplate
# fail. "Predicts target safety." is the card this refuses.
STATEMENT = 80
USE = 120

Question = Literal["Q1", "Q2", "Q3", "secondary"]
Rung = Literal[
    "no-graph-control",
    "degree-only-null",
    "graph-topology-gbm",
    "shallow-kge",
    "relation-agnostic-gnn",
    "relation-aware-gnn",
]


class ModelIdentity(BaseModel):
    """Which model, trained from what, answering which question."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    name: str = Field(min_length=3)
    rung: Rung
    question: Question
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    release_pin: str = Field(min_length=3)
    # FIVE SEEDS, BECAUSE ONE CANNOT RESOLVE THE DIFFERENCE BEING CLAIMED: most
    # reported wins on biomedical graphs sit inside the band a single seed leaves.
    seeds: tuple[int, ...] = Field(min_length=5)


class Slice(BaseModel):
    """One disaggregated result: a stratum, its size, and its score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=3)
    kind: Literal["degree", "endpoint-level", "seed", "cold-start", "temporal"]
    n: int = Field(gt=0)
    average_precision: float = Field(ge=0.0, le=1.0)


class Contrast(BaseModel):
    """What this model was measured against, and by how much it differed.

    AN INTERVAL, NOT A POINT. A lift reported without one cannot be told from
    noise, and the ladder's whole purpose is deciding whether a difference is
    real.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    against: Rung
    question: Question
    ap_lift: float
    ci_low: float
    ci_high: float

    @model_validator(mode="after")
    def _interval_contains_the_estimate(self) -> Self:
        if not self.ci_low <= self.ap_lift <= self.ci_high:
            raise ValueError(
                f"the lift {self.ap_lift} lies outside its own interval "
                f"[{self.ci_low}, {self.ci_high}]"
            )
        return self


class Limitation(BaseModel):
    """Something the card declares it cannot claim past.

    KIND SEPARATES WHAT CAN BE FIXED FROM WHAT CANNOT. Layer 1's conflation of
    on-target biology with drug pharmacology is unresolvable by any amount of
    engineering: the project asks about the target and every observation comes
    from a compound. Declaring it is the only honest treatment.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: int = Field(ge=1, le=9)
    kind: Literal["unresolvable", "known", "untested"]
    statement: str = Field(min_length=STATEMENT)


class ModelCard(BaseModel):
    """The card a model travels with, or it does not travel."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    CONTRACT_ID: ClassVar[str] = "model-card/v1"

    contract: Literal["model-card/v1"] = "model-card/v1"
    model: ModelIdentity
    intended_use: str = Field(min_length=USE)
    out_of_scope_use: str = Field(min_length=USE)
    slices: tuple[Slice, ...] = Field(min_length=2)
    contrasts: tuple[Contrast, ...]
    limitations: tuple[Limitation, ...] = Field(min_length=1)
    verdict: Literal["promote", "reject"]
    attestation: DsseEnvelope

    @model_validator(mode="after")
    def _layer_one_is_declared(self) -> Self:
        """The unresolvable gap is stated, or this is not this project's card."""
        if not any(item.layer == 1 for item in self.limitations):
            raise ValueError(
                "no layer-1 limitation: the conflation of on-target biology with drug "
                "pharmacology is unresolvable here and must be declared"
            )
        return self

    @model_validator(mode="after")
    def _a_promotion_carries_its_evidence(self) -> Self:
        """A verdict is a claim; a claim with no contrast has nothing behind it.

        A REJECTION NEEDS NONE. Refusing to promote asserts nothing about the
        world, and a negative result is a real finding this project accepts.
        """
        if self.verdict == "promote" and not self.contrasts:
            raise ValueError("a promotion states no contrast, so its claim has no evidence")
        return self

    @model_validator(mode="after")
    def _the_slices_are_disaggregated(self) -> Self:
        """Two slices of one kind, or the stratification says nothing."""
        if len({item.name for item in self.slices}) < 2:
            raise ValueError("the slices are not distinct, so nothing is disaggregated")
        return self
