# tooling/src/otsafety_tooling/contracts/eslint_config.py
"""ESLint's configuration, as data: what its API returns, and what the policy reads.

ESLint's configuration is JavaScript, so Conftest cannot parse it; its resolved
form is produced instead, per file, through ESLint's own API. That output crosses
two boundaries, so each has a contract. ESLint's API types its result as any,
which the site's own rules refuse: eslint-calculated-config/v1 parses it on the
way in. eslint-effective/v1 is the normalized form the Rego policy reads, and the
script that writes it validates it on the way out.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class _Linter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    no_inline_config: bool = Field(default=False, alias="noInlineConfig")


class CalculatedConfig(BaseModel):
    """ESLint's calculateConfigForFile result: only what the policy needs."""

    model_config = ConfigDict(frozen=True, extra="ignore")
    CONTRACT_ID: ClassVar[str] = "eslint-calculated-config/v1"
    AUTHORED: ClassVar[bool] = True  # a third party's shape, with defaults where it omits

    # REQUIRED: ESLint's API always returns both, so a missing one fails the parse
    # rather than being defaulted. A default_factory never reaches the JSON Schema,
    # so the generated Zod would have made both optional.
    linter_options: _Linter = Field(alias="linterOptions")
    # A rule's setting is a severity (0, 1, 2 or a word) or a list of severity and options.
    rules: dict[str, JsonValue]


Severity = Literal["off", "warn", "error"]


class RuleSetting(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    severity: Severity
    options: tuple[JsonValue, ...]


class FileConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    no_inline_config: bool
    rules: dict[str, RuleSetting]


class EffectiveConfig(BaseModel):
    """What ESLint actually applies to each linted file, written for the policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    contract: Literal["eslint-effective/v1"] = "eslint-effective/v1"
    files: dict[str, FileConfig]
