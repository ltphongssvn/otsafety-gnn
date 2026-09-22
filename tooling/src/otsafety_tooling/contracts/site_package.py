# tooling/src/otsafety_tooling/contracts/site_package.py
"""The site's package.json, as far as the checks here read it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SitePackage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    scripts: dict[str, str] = {}
    dependencies: dict[str, str] = {}
    # package.json's own key, mapped onto a Python name rather than suppressed.
    dev_dependencies: dict[str, str] = Field(default_factory=dict, alias="devDependencies")
