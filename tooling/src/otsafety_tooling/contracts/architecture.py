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

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    name: str = Field(min_length=3)
    question: Literal["Q1", "Q2", "Q3"]
    detail: str = Field(min_length=10)


class Architecture(BaseModel):
    """The architecture, stated once and read by the sheet, the site and the README."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CONTRACT_ID: ClassVar[str] = "architecture/v1"

    contract: Literal["architecture/v1"] = "architecture/v1"
    layers: tuple[Layer, ...] = Field(min_length=9, max_length=9)
    stages: tuple[Stage, ...] = Field(min_length=1)
    questions: tuple[Question, ...] = Field(min_length=3, max_length=3)
    rungs: tuple[Rung, ...] = Field(min_length=1)
    scope_in: tuple[str, ...] = Field(min_length=1)
    scope_out: tuple[str, ...] = Field(min_length=1)
