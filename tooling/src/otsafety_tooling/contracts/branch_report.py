# tooling/src/otsafety_tooling/contracts/branch_report.py
"""branch-report/v1: the recorded state of every branch, and the verdict on it.

EVIDENCE, THEN VERDICT. A report holds FACTS (what git said about each branch)
and FINDINGS (which GitFlow rules those facts break), and its VERDICT must agree
with its findings. The invariants below make a self-contradictory report
impossible to construct, so nothing that reads one has to re-check it.

THE RULES A FINDING MAY NAME
    B001  a protected branch is behind its upstream (only)
    B002  a protected branch is ahead of its upstream (only)
    B003  a merged feature branch still exists on the remote
    B004  a protected branch has diverged from its upstream
    B005  origin/main is not contained in origin/develop

PRIVACY. Facts record whether a branch is checked out, never where: a worktree
path contains the local username, and reports are shared evidence.

WHY frozen AND extra ARE CLASS KEYWORDS. Pydantic accepts either form, but
mypy recognises only the class-keyword form as read-only, so an attempted
mutation is a type error as well as a runtime one.

WHY STRICT TYPES PER FIELD RATHER THAN strict=True. Model-wide strict mode
refuses a list for a tuple field, and both JSON and ordinary callers supply
lists. StrictInt and StrictBool keep the scalars exact without that cost.

WHY CONTRACT IS Final. An unannotated constant is inferred as plain `str`,
which mypy will not assign to a Literal field. A Final name initialised with a
literal keeps that literal type.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    NonNegativeInt,
    StrictBool,
    model_validator,
)

CONTRACT: Final = "branch-report/v1"

RuleId = Literal["B001", "B002", "B003", "B004", "B005"]
Verdict = Literal["pass", "fail", "unknown"]
BranchKind = Literal["local", "remote"]

COMMIT_PATTERN = r"^[0-9a-f]{40}$"
REASON_CODE_PATTERN = r"^[A-Z][A-Z0-9_]*$"
GIT_VERSION_PATTERN = r"^\d+\.\d+(\.\d+)?"


class Divergence(BaseModel, frozen=True, extra="forbid"):
    """Commits on each side of a comparison, as git counts them."""

    ahead: NonNegativeInt = Field(strict=True)
    behind: NonNegativeInt = Field(strict=True)

    @property
    def is_diverged(self) -> bool:
        return self.ahead > 0 and self.behind > 0


class BranchFact(BaseModel, frozen=True, extra="forbid"):
    """What git reports about one branch. A fact, not a judgement."""

    name: str = Field(min_length=1)
    kind: BranchKind
    commit: str = Field(pattern=COMMIT_PATTERN)
    upstream: str | None = None
    vs_upstream: Divergence | None = None
    vs_develop: Divergence | None = None
    merged_into_develop: StrictBool
    checked_out: StrictBool

    @model_validator(mode="after")
    def _upstream_is_complete(self) -> Self:
        if self.kind == "remote" and self.upstream is not None:
            raise ValueError(f"a remote branch has no upstream: {self.name}")
        if self.upstream is not None and self.vs_upstream is None:
            raise ValueError(f"upstream {self.upstream} is recorded without its counts")
        if self.upstream is None and self.vs_upstream is not None:
            raise ValueError("counts are recorded without an upstream")
        return self


class Finding(BaseModel, frozen=True, extra="forbid"):
    """A GitFlow rule the facts break, in machine-readable form."""

    rule_id: RuleId
    reason_code: str = Field(pattern=REASON_CODE_PATTERN)
    message: str = Field(min_length=1)
    branch: str = Field(min_length=1)


class BranchReport(BaseModel, frozen=True, extra="forbid"):
    """The recorded state of every branch, and the verdict on it."""

    contract: Literal["branch-report/v1"] = CONTRACT
    generated_at: AwareDatetime
    repository: str = Field(min_length=1)
    head: str = Field(pattern=COMMIT_PATTERN)
    git_version: str = Field(pattern=GIT_VERSION_PATTERN)
    facts: tuple[BranchFact, ...]
    findings: tuple[Finding, ...] = ()
    verdict: Verdict

    @model_validator(mode="after")
    def _verdict_agrees_with_the_evidence(self) -> Self:
        if self.findings and self.verdict != "fail":
            raise ValueError(f"verdict is {self.verdict!r} but there are findings")
        if self.verdict == "fail" and not self.findings:
            raise ValueError("verdict is 'fail' but there are no findings")
        if self.verdict == "pass" and not self.facts:
            raise ValueError("a 'pass' requires at least one recorded fact")
        return self
