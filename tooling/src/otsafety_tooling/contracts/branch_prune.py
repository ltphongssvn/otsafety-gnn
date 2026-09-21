# tooling/src/otsafety_tooling/contracts/branch_prune.py
"""branch-prune/v1: every pruning decision, and what came of it, as data.

DECISION AS DATA. Deleting a branch on the shared remote cannot be undone for
anyone else, so each decision is recorded with the branch report that
justified it, the reason, and the outcome.

    decision  delete  reason DELETE_MERGED                      outcome planned | deleted | failed
    decision  keep    reason KEEP_PROTECTED | KEEP_ALREADY_GONE
                             | KEEP_NOT_MERGED                  outcome not_applicable

THE RECORD IS CONSISTENT BY CONSTRUCTION
    a plan (applied=false) records only planned outcomes, never deleted or failed
    an applied run leaves nothing merely planned
    decisions exist only with the branch report they came from
    verdict: no report -> unknown; any failed deletion -> fail; otherwise pass

TRACEABLE. source_report is the branch report's file name, in the format the
report writer uses, so every deletion points at the evidence behind it.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator

CONTRACT: Final = "branch-prune/v1"

Decision = Literal["delete", "keep"]
ReasonCode = Literal["DELETE_MERGED", "KEEP_PROTECTED", "KEEP_ALREADY_GONE", "KEEP_NOT_MERGED"]
Outcome = Literal["planned", "deleted", "failed", "not_applicable"]
Verdict = Literal["pass", "fail", "unknown"]

REPORT_NAME_PATTERN = r"^\d{8}T\d{12}Z\.json$"
REMOTE_BRANCH_PATTERN = r"^origin/.+"

DELETE_OUTCOMES: Final = frozenset({"planned", "deleted", "failed"})


class PruneDecision(BaseModel, frozen=True, extra="forbid"):
    """What was decided about one remote branch, why, and what happened."""

    branch: str = Field(pattern=REMOTE_BRANCH_PATTERN)
    decision: Decision
    reason_code: ReasonCode
    message: str = Field(min_length=1)
    outcome: Outcome

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.decision == "keep":
            if not self.reason_code.startswith("KEEP_"):
                raise ValueError(f"a keep decision needs a KEEP_ reason, not {self.reason_code}")
            if self.outcome != "not_applicable":
                raise ValueError(f"a keep decision has outcome not_applicable, not {self.outcome}")
            return self
        if self.reason_code != "DELETE_MERGED":
            raise ValueError(f"a delete decision must carry DELETE_MERGED, not {self.reason_code}")
        if self.outcome not in DELETE_OUTCOMES:
            raise ValueError(f"a delete decision cannot have outcome {self.outcome}")
        return self


class PruneRecord(BaseModel, frozen=True, extra="forbid"):
    """One pruning run: the plan or its execution, recorded as data."""

    contract: Literal["branch-prune/v1"] = CONTRACT
    generated_at: AwareDatetime
    repository: str = Field(min_length=1)
    source_report: str | None = Field(default=None, pattern=REPORT_NAME_PATTERN)
    applied: bool = Field(strict=True)
    decisions: tuple[PruneDecision, ...] = ()
    verdict: Verdict

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        outcomes = {decision.outcome for decision in self.decisions}
        if self.source_report is None and self.decisions:
            raise ValueError("decisions require the branch report they came from")
        if not self.applied and outcomes & {"deleted", "failed"}:
            raise ValueError("a plan (applied=false) cannot record deleted or failed outcomes")
        if self.applied and "planned" in outcomes:
            raise ValueError("an applied run cannot leave planned outcomes")

        implied: Verdict
        if self.source_report is None:
            implied = "unknown"
        elif "failed" in outcomes:
            implied = "fail"
        else:
            implied = "pass"
        if self.verdict != implied:
            raise ValueError(f"verdict is {self.verdict!r} but the record implies {implied!r}")
        return self
