# tooling/src/otsafety_tooling/slsa/source.py
"""Which SLSA Source Level this repository meets, computed rather than claimed.

SLSA v1.2 APPROVED THE SOURCE TRACK IN NOVEMBER 2025. Its requirement is
explicit: an attestation MUST state the level of any revision at L1 or above.
A level asserted in prose is a badge; a level computed from evidence, written
as a record and judged by policy, is a claim somebody can check.

LEVELS ARE CUMULATIVE, which is the whole point of a track. A repository whose
branch protection is enforced but whose history can be rewritten is not L3 with
one gap -- it is L1, because every guarantee above rests on the ones below.
Reporting the highest requirement that happens to hold describes a repository
that does not exist.

AND AN UNREACHABLE LEVEL IS NAMED. One maintainer cannot have two reviewers, so
L4 is out of reach here and the attestation says so. A limit quietly omitted
reads as an oversight; stated, it is a declared boundary -- the rule E.39
already applies to the model card's first layer.

WHAT THIS IS NOT. It is not a Source VSA issued by a source control system: the
specification puts that duty on the SCS, and GitHub issues none today. This is
the organisation's own measurement of its own controls, written in the same
in-toto shape so that an SCS-issued attestation could later replace it without
changing a consumer.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from otsafety_tooling.contracts.repository_settings import BranchProtection, Verdict

# THE PREDICATE NAMES WHAT THE DOCUMENT ASSERTS, and SLSA's verification
# summary is the shape for "a thing was checked and here is the conclusion".
PREDICATE_TYPE = "https://slsa.dev/verification_summary/v1"

# L4 IS TWO TRUSTED PEOPLE, which is what the level means rather than a
# threshold anyone chose: the author, and someone who is not the author.
TWO_PARTY = 2

# WHAT EACH LEVEL REQUIRES, in order. The index IS the level, so a rung
# satisfied means that level reached -- counting requirements instead once
# produced a level 5, which the track does not define.
#
# L2 CARRIES TWO REQUIREMENTS, as the specification does: continuous immutable
# history AND provenance issued for each revision. They are one rung, not two.
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
    """The level this revision meets, and what stopped it going higher."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    predicate_type: str = PREDICATE_TYPE
    # A REVISION IS A COMMIT, not a name that resolves to one today and another
    # tomorrow: an attestation about HEAD says nothing a month later.
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    level: int = Field(ge=0, le=4)
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
    """Why the level is not higher, in the specification's own terms."""
    return tuple(reason for rung in LADDER for name, reason in rung if not getattr(controls, name))


def summarise(controls: Controls, *, revision: str) -> Summary:
    """The measurement as a document, ready to be signed and recorded."""
    return Summary(revision=revision, level=level_of(controls), unmet=unmet(controls))


def controls_from(
    protected: Sequence[BranchProtection], *, verdict: Verdict, reviewers: int
) -> Controls:
    """The Source Track's controls, derived from what this repository already records.

    DERIVED, NOT RETYPED. repository-settings/v1 already declares, per branch,
    whether the remote refuses a force push, a deletion and a direct push --
    the three ways lineage is rewritten. A second copy of those booleans beside
    it would drift, which is what a literal typed twice cost at G.80.

    NO PROTECTED BRANCH IS NOT AN IMMUTABLE HISTORY. all() over an empty
    sequence is true, so a repository declaring nothing would report the
    strongest guarantee; the population is required non-empty first.

    UNKNOWN IS NOT PASS. The settings check already refuses that conflation: a
    verdict of unknown means GitHub would not show the settings, and reading it
    as enforcement claims a control nobody observed.

    PROVENANCE PER REVISION IS NOT PRODUCED HERE, and saying otherwise would be
    the badge this exists to replace. The specification puts that duty on the
    source control system; GitHub issues none today, and the candidate tooling
    is proof-of-concept. It is reported false until something issues one.
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
