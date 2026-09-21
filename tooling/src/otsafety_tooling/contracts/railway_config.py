# tooling/src/otsafety_tooling/contracts/railway_config.py
"""deploy/site/railway.json, the service's configuration as code."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class RailwayBuild(_Strict):
    builder: Literal["DOCKERFILE"]
    dockerfile_path: str = Field(alias="dockerfilePath")


class RailwayDeploy(_Strict):
    healthcheck_path: str = Field(alias="healthcheckPath")
    restart_policy_type: Literal["ON_FAILURE", "ALWAYS", "NEVER"] = Field(alias="restartPolicyType")


class RailwayConfig(_Strict):
    schema_url: str = Field(alias="$schema")
    build: RailwayBuild
    deploy: RailwayDeploy
