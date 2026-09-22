# tooling/src/otsafety_tooling/contracts/site_package.py
"""The site's package.json, as far as the checks here read it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SitePackage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    scripts: dict[str, str] = {}
    dependencies: dict[str, str] = {}
    devDependencies: dict[str, str] = {}  # noqa: N815 -- package.json's own key
