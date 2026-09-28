# tooling/src/otsafety_tooling/contracts/sources.py
"""context/sources.yaml: every data source, its terms, and what may not ship.

THE CONSTRAINT WAS A COMMENT. conf/config.yaml said in prose that MedDRA is
proprietary and its hierarchy cannot be redistributed -- true, and no gate could
read it. 2026 audits name that shape precisely: declarations rich, enforcement
theatre, and a project measured by the share of its requirements carrying a real
mechanical check.

FACTS, NOT LEGAL READINGS. A source records its terms as written, whether it is
open, and which artefacts must never be redistributed. Interpreting a licence is
not something to encode without the maintainer; observing that a named artefact
is absent from the tree is.

AN UNDECLARED LICENCE IS NOT PERMISSION, which is why the field is required and
non-empty rather than optional: a source whose terms nobody recorded cannot be
used, the same way an unknown SPDX identifier blocks ingestion elsewhere.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Source(_Strict):
    """One data source and the terms under which this project may use it."""

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=2)
    role: str = Field(min_length=40)
    licence: str = Field(min_length=20)
    open: bool
    # WHAT MUST NEVER BE REDISTRIBUTED, named as file patterns so the absence of
    # each is observable. An open source names none; a closed one must name at
    # least one, because knowing a source is closed is not enough to act on.
    withheld: tuple[str, ...] = ()
    release: str | None = None

    @model_validator(mode="after")
    def _a_closed_source_names_what_it_withholds(self) -> Self:
        if not self.open and not self.withheld:
            raise ValueError(
                f"{self.id} is not open and names nothing withheld, so no gate can check it"
            )
        return self


class DataSources(_Strict):
    """Every source this project reads, with its terms."""

    CONTRACT_ID: ClassVar[str] = "data-sources/v1"

    contract: str = Field(default="data-sources/v1", pattern=r"^data-sources/v1$")
    sources: tuple[Source, ...] = Field(min_length=1)
