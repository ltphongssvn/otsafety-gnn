# tooling/src/otsafety_tooling/contracts/opentargets_config.py
"""conf/config.yaml: the ingestion contract -- which release, which datasets.

The model is the file's shape, field for field, so a misspelled key or a
dataset triple of the wrong length fails when the file is read, not when the
first download resolves to nothing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# (dataset, source_column, date_column)
Relation = tuple[str, str | None, str | None]


class DataConfig(_Strict):
    platform_version: str = Field(pattern=r"^\d{2}\.\d{2}$")
    base_url: str = Field(pattern=r"^https://")
    root: str = Field(min_length=1)
    relations: dict[str, Relation] = Field(min_length=1)


class LabelsConfig(_Strict):
    curated: tuple[str, ...] = Field(min_length=1)
    clinical_precedence: str = Field(min_length=1)
    min_phase_for_negative: int = Field(ge=1, le=4)


class EndpointsConfig(_Strict):
    ontologies: tuple[str, ...] = Field(min_length=1)
    ontology_api: str = Field(pattern=r"^https://")
    meddra_hierarchy: str | None


class OpenTargetsConfig(_Strict):
    data: DataConfig
    labels: LabelsConfig
    target_features: tuple[str, ...] = Field(min_length=1)
    endpoints: EndpointsConfig
