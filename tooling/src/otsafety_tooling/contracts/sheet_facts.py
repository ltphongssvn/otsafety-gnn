# tooling/src/otsafety_tooling/contracts/sheet_facts.py
"""sheet-facts/v1: what the architecture sheet reports, collected before it renders.

THE RENDERER DOES NOT COLLECT. It runs inside a pinned image carrying Playwright
and pypdf and nothing else -- no git, no PyYAML, not this package. Every attempt
to have it read the plan, count merges or inspect the tree failed there for a
different missing tool, and each fix was a tool-shaped patch on a design mistake.

2026 practice for a generated document separates the two: collection runs where
the credentials and the tooling are, and the renderer is a pure transform of a
document it is handed. So the figures are gathered here, validated, committed,
and drift-gated like every other export -- and the sheet reads one file.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict


class PhaseFact(BaseModel):
    """One delivery phase and how far its steps have got."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    done: int
    total: int
    state: Literal["done", "now", "todo"]


class ThreadFact(BaseModel):
    """One workstream, with the share of its steps the plan shows complete."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    done: int
    total: int
    percent: int
    state: Literal["done", "active", "todo"]


class SheetFacts(BaseModel):
    """Every number the sheet states, as observed when it was collected."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    CONTRACT_ID: ClassVar[str] = "sheet-facts/v1"

    contract: Literal["sheet-facts/v1"] = "sheet-facts/v1"
    steps: int
    steps_done: int
    ids: int
    requirements: int
    unconfirmed: int
    test_functions: int
    merged_prs: int
    tasks: int
    phases: tuple[PhaseFact, ...]
    threads: tuple[ThreadFact, ...]
