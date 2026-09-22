# tooling/src/otsafety_tooling/contracts/exemptions.py
"""exemption-register/v1: every exemption from a rule, with its reason.

Scoped entries mirror Ruff's per-file ignores, which Ruff cannot read from here;
inline entries count each rule's suppressions per file, keyed by file rather
than by line, since lines move with every edit. A reason is required, because a
suppression anyone can add without saying why is a rule that holds only while
people remember it.
"""

from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScopedExemption(_Strict):
    glob: str = Field(min_length=1)
    rules: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)


class InlineExemption(_Strict):
    path: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    count: int = Field(ge=1)
    reason: str = Field(min_length=1)


class ExemptionRegister(_Strict):
    AUTHORED: ClassVar[bool] = True
    contract: Literal["exemption-register/v1"]
    scoped: tuple[ScopedExemption, ...]
    inline: tuple[InlineExemption, ...]

    @model_validator(mode="after")
    def _each_key_once(self) -> Self:
        globs = [s.glob for s in self.scoped]
        keys = [(i.path, i.rule) for i in self.inline]
        duplicated = {g for g in globs if globs.count(g) > 1} | {
            k for k in keys if keys.count(k) > 1
        }
        if duplicated:
            raise ValueError(f"declared more than once: {sorted(map(str, duplicated))}")
        return self
