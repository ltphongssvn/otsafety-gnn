# tooling/src/otsafety_tooling/slsa/review.py
"""Ask the judge whether a step's evidence establishes its claim, and record it.

NEVER A GATE. A language model's answer cannot be reproduced -- its
non-determinism originates in the forward pass, and the SDK no longer even
accepts a temperature -- so this produces a record a person reads. No gate and
no hook calls it, which a test holds.

STRUCTURED OUTPUT, NOT A FORCED TOOL. The verdict comes back through a response
format. On a model whose thinking is always on, forcing a tool makes it skip
the thinking, which is the reasoning a reviewer exists for.

THE JUDGE RETURNS ONLY WHAT IT KNOWS. Its finding and its reason. The model
id, the prompt hash and the count of repeats are facts held here; a model asked
to report them would invent them.

A TIE IS EMITTED AS "split", NEVER HIDDEN. The mode is the finding; when two
answers share the top count there is no mode, and choosing one would invent a
verdict. A split goes to a person, which is the standing advice for a judge
that cannot decide -- and the reason this record exists.

AN ANSWER THAT IS NOT A VERDICT IS "unreadable". If the response cannot be read
as the schema the judge was given, that is the honest meaning of the word, and
it is counted like any other answer rather than retried until one parses.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from otsafety_tooling.cli import CommandRefused
from otsafety_tooling.contracts.semantic_review import JUDGE_MODEL, Judge, SemanticReview
from otsafety_tooling.contracts.settings import settings

if TYPE_CHECKING:
    import anthropic

# THE RUBRIC'S IDENTITY, versioned: a change to what the judge is asked is a
# different measurement, and the record must say which one it was.
RUBRIC = "does-the-evidence-establish-the-claim/v1"

# ENOUGH FOR A JUSTIFICATION, not for an essay.
MAX_TOKENS = 4096

SYSTEM = (
    "You review one requirement from a software project's plan. You are given "
    "the requirement's title -- its claim -- and the evidence its plan names to "
    "prove it: file paths, task names and test names. Decide whether that "
    "evidence, as named, could establish everything the claim asserts.\n\n"
    "covered: the evidence establishes every part of the claim.\n"
    "partial: it establishes some parts and not others; say which are missing.\n"
    "uncovered: it establishes none of what the claim asserts.\n"
    "unreadable: the claim or the evidence is too unclear to judge.\n\n"
    "Judge only what is named. Do not assume evidence exists that is not listed."
)


class Verdict(BaseModel):
    """What the judge returns, and all it returns.

    NO "split" HERE. A split is what the repeats did, not something one answer
    can be; the aggregation decides it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding: Literal["covered", "partial", "uncovered", "unreadable"]
    rationale: str = Field(min_length=1)


def question(*, step: str, claim: str, evidence: Sequence[str]) -> str:
    """The user turn: exactly what the judge is asked about, and nothing else."""
    listed = "\n".join(f"- {item}" for item in evidence) or "- (none named)"
    return f"Requirement {step}.\n\nClaim:\n{claim}\n\nEvidence named:\n{listed}"


def prompt_sha256(*, step: str, claim: str, evidence: Sequence[str]) -> str:
    """THE HASH NAMES THE QUESTION. System and user turn together, so a change
    to either is a different measurement and two reviews of the same thing say
    they asked the same thing."""
    rendered = SYSTEM + "\x00" + question(step=step, claim=claim, evidence=evidence)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _one(client: anthropic.Anthropic, *, step: str, claim: str, evidence: Sequence[str]) -> Verdict:
    response = client.messages.parse(
        model=JUDGE_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": question(step=step, claim=claim, evidence=evidence)}],
        output_format=Verdict,
    )
    parsed = response.parsed_output
    if isinstance(parsed, Verdict):
        return parsed
    return Verdict(finding="unreadable", rationale="the response was not a verdict")


def ask(
    client: anthropic.Anthropic, *, step: str, claim: str, evidence: Sequence[str], repeats: int
) -> SemanticReview:
    """Ask `repeats` times; the mode is the finding, and a tie is a split."""
    answers = [_one(client, step=step, claim=claim, evidence=evidence) for _ in range(repeats)]
    counted = Counter(answer.finding for answer in answers).most_common()
    top, agreed = counted[0]
    tied = len(counted) > 1 and counted[1][1] == agreed

    if tied:
        finding: Literal["covered", "partial", "uncovered", "unreadable", "split"] = "split"
        rationale = "the repeats disagreed: " + "; ".join(
            f"{count} said {label}" for label, count in counted
        )
    else:
        finding = top
        rationale = next(answer.rationale for answer in answers if answer.finding == top)

    return SemanticReview(
        reviewed_at=datetime.now(UTC),
        step=step,
        claim=claim,
        finding=finding,
        rationale=rationale,
        judge=Judge(
            model=JUDGE_MODEL,
            rubric=RUBRIC,
            prompt_sha256=prompt_sha256(step=step, claim=claim, evidence=evidence),
            repeats=repeats,
            agreed=agreed,
        ),
    )


def client_from_settings() -> anthropic.Anthropic:
    """The real client, keyed through the settings model and nowhere else.

    THE SDK IS IMPORTED HERE, NOT AT THE TOP. It is an optional extra that CI
    does not install, so a module-scope import would fail every test that
    imports this file on a runner without it.

    THE KEY IS PASSED, NOT FETCHED. The SDK would read ANTHROPIC_API_KEY from
    the environment itself, which is a second reader of the environment beside
    the one this repository allows.
    """
    key = settings().anthropic_api_key
    if key is None or not key.get_secret_value():
        raise CommandRefused(
            "no_key",
            "ANTHROPIC_API_KEY is not set; the review is optional, and nothing else needs it",
        )
    import anthropic

    return anthropic.Anthropic(api_key=key.get_secret_value())
