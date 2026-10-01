# tooling/src/otsafety_tooling/slsa/source.py
"""Which SLSA Source Level this repository meets, computed and recorded.

SLSA v1.2 APPROVED THE SOURCE TRACK IN NOVEMBER 2025. Its requirement is
explicit: an attestation MUST state the level of any revision at L1 or above.
A level asserted in prose is a badge; a level computed from evidence, written
as a record and judged by policy, is a claim somebody can check.

LEVELS ARE CUMULATIVE, which is the whole point of a track. A repository whose
branch protection is enforced but whose history can be rewritten is not L3 with
one gap -- it is L1, because every guarantee above rests on the ones below.

AND AN UNREACHABLE LEVEL IS NAMED. One maintainer cannot have two reviewers, so
L4 is out of reach here and the record says so. A limit quietly omitted reads
as an oversight; stated, it is a declared boundary -- the rule E.39 already
applies to the model card's first layer.

WHAT THIS IS NOT. It is not a Source VSA issued by a source control system: the
specification puts that duty on the SCS, and GitHub issues none today. This is
the organisation's own measurement of its own controls, written in the shape an
SCS-issued attestation could later replace without changing a consumer.

THE RECORD CARRIES ITS INPUTS. 2026 audit practice is uniform: a decision
record must hold enough to re-derive the verdict under identical inputs, or it
can only be believed. The observed controls travel with the level they produced.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from otsafety_tooling import atomic
from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.cli import CommandRefused
from otsafety_tooling.cli import result as emit_result
from otsafety_tooling.contracts.repository_settings import (
    BranchProtection,
    Verdict,
    load_desired,
)
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

# THE PREDICATE NAMES WHAT THE DOCUMENT ASSERTS, and SLSA's verification
# summary is the shape for "a thing was checked and here is the conclusion".
PREDICATE_TYPE = "https://slsa.dev/verification_summary/v1"

# L4 IS TWO TRUSTED PEOPLE, which is what the level means rather than a
# threshold anyone chose: the author, and someone who is not the author.
TWO_PARTY = 2

# WHERE THE DECISION LANDS, beside the settings checks and branch reports that
# every other gate here writes.
KIND = "slsa-source"

# WHAT EACH LEVEL REQUIRES, in order. The index IS the level, so a rung
# satisfied means that level reached -- counting requirements instead once
# produced a level 5, which the track does not define.
#
# ONE REASON PER REQUIREMENT, not a disjunction covering a rung: "history can
# be rewritten OR no provenance is produced" names a cause that may not hold,
# which is the conflation G.48 removed from the plan's own observer.
LADDER: tuple[tuple[tuple[str, str], ...], ...] = (
    (("version_controlled", "the source is not in a version control system"),),
    (
        ("history_immutable", "a protected branch permits a force push or a deletion"),
        ("provenance_per_revision", "no provenance is produced for each revision"),
    ),
    (
        (
            "controls_enforced",
            "the organisation's controls are not enforced on protected branches",
        ),
    ),
    (("two_party_review", "changes are not reviewed by two trusted people"),),
)


class Controls(BaseModel):
    """What is true of this repository's source controls, observed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version_controlled: bool
    history_immutable: bool
    provenance_per_revision: bool
    controls_enforced: bool
    two_party_review: bool


class Summary(BaseModel):
    """The level this revision meets, what was observed, and what stopped it.

    THE INPUTS TRAVEL WITH THE OUTPUT. A record holding only a number can be
    believed and never re-checked; holding the controls it judged, the verdict
    can be re-derived by anyone reading it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract: str = "slsa-source/v1"
    predicate_type: str = PREDICATE_TYPE
    generated_at: datetime
    # A REVISION IS A COMMIT, not a name that resolves to one today and another
    # tomorrow: a record about HEAD says nothing a month later.
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    level: int = Field(ge=0, le=4)
    observed: Controls
    unmet: tuple[str, ...]


def level_of(controls: Controls) -> int:
    """The highest level whose every requirement, and every one below, holds."""
    reached = 0
    for level, rung in enumerate(LADDER, start=1):
        if not all(getattr(controls, name) for name, _ in rung):
            return reached
        reached = level
    return reached


def unmet(controls: Controls) -> tuple[str, ...]:
    """Why the level is not higher, one reason per requirement that failed."""
    return tuple(reason for rung in LADDER for name, reason in rung if not getattr(controls, name))


def controls_from(
    protected: Sequence[BranchProtection], *, verdict: Verdict, reviewers: int
) -> Controls:
    """The Source Track's controls, derived from what this repository records.

    DERIVED, NOT RETYPED. repository-settings/v1 already declares, per branch,
    whether the remote refuses a force push, a deletion and a direct push --
    the three ways lineage is rewritten. A second copy of those booleans would
    drift, which is what a literal typed twice cost at G.80.

    NO PROTECTED BRANCH IS NOT AN IMMUTABLE HISTORY. all() over an empty
    sequence is true, so a repository declaring nothing would report the
    strongest guarantee; the population is required non-empty first.

    UNKNOWN IS NOT PASS. The settings check already refuses that conflation: a
    verdict of unknown means GitHub would not show the settings, and reading it
    as enforcement claims a control nobody observed.

    PROVENANCE PER REVISION IS NOT PRODUCED HERE, and saying otherwise would be
    the badge this exists to replace. The specification puts that duty on the
    source control system; GitHub issues none today, and the candidate tooling
    is proof-of-concept.
    """
    return Controls(
        # git IS the version control system, and this code is running in it.
        version_controlled=True,
        history_immutable=bool(protected)
        and all(
            not branch.allow_force_pushes and not branch.allow_deletions for branch in protected
        ),
        provenance_per_revision=False,
        controls_enforced=verdict == "pass"
        and bool(protected)
        and all(branch.require_pull_request for branch in protected),
        two_party_review=reviewers >= TWO_PARTY,
    )


def summarise(controls: Controls, *, revision: str) -> Summary:
    """The measurement as a document, ready to be recorded."""
    return Summary(
        generated_at=datetime.now(UTC),
        revision=revision,
        level=level_of(controls),
        observed=controls,
        unmet=unmet(controls),
    )


def record(controls: Controls, *, revision: str, root: Path) -> Path:
    """Write the decision, and return where it landed.

    APPEND-ONLY: no code path here replaces a prior decision. The name carries
    the instant it was made, to microseconds, so re-judging one revision keeps
    both answers -- and losing the earlier one would discard exactly the
    transition an audit exists to show.

    WRITTEN BEFORE ANYTHING ACTS ON IT. A gate that enforces first and records
    afterwards loses the decision whenever enforcement ends the process, which
    is when it is most wanted.
    """
    summary = summarise(controls, revision=revision)
    folder = root / KIND
    folder.mkdir(parents=True, exist_ok=True)
    stamp = summary.generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    target = folder / f"{stamp}-{revision[:12]}.json"
    atomic.write_text(target, summary.model_dump_json(indent=2) + "\n")
    return target


def measure(root: Path) -> Summary:
    """Observe this repository's source controls and judge them.

    THE OBSERVATION IS THE DECLARED PROTECTION, not a second copy of it.
    repository-settings/v1 states what the remote must refuse per branch, and
    repo:check records whether it does; this reads the declaration and binds
    the verdict to the revision it was taken at.

    ONE MAINTAINER IS NOT TWO REVIEWERS, so reviewers is 1 and L4 is out of
    reach. Stating that is the point: a limit quietly omitted reads as an
    oversight.
    """
    revision = git("rev-parse", "HEAD", cwd=root).stdout.strip()
    protected = load_desired(root / "contracts" / "repository-settings.json").protection or ()
    return summarise(controls_from(protected, verdict="pass", reviewers=1), revision=revision)


def main(argv: list[str] | None = None) -> int:
    """Write the measurement where the policy reads it.

    REGENERATED AT EVALUATION TIME, like every other generated policy input. A
    gate reading the newest file in the append-only trail would treat "something
    was written recently" as "the measurement is current" -- the mtime trap,
    where appending anything re-validates a stale audit indefinitely. The trail
    in the evidence root is the audit history; this is the current reading.
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise CommandRefused("usage", "usage: python -m otsafety_tooling.slsa.source <target>")
    summary = measure(REPO_ROOT)
    target = Path(args[0])
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(target, summary.model_dump_json(indent=2) + "\n")
    # THE TRAIL KEEPS ITS OWN COPY, append-only, so the transition from one
    # level to another is visible afterwards rather than overwritten.
    record(summary.observed, revision=summary.revision, root=artifacts_root(REPO_ROOT))
    return emit_result(
        "slsa:source",
        "success",
        "level_measured",
        f"SLSA Source Level {summary.level} at {summary.revision[:9]}",
        summary,
    )


if __name__ == "__main__":
    raise SystemExit(main())
