# tooling/tests/test_bot_commits_need_no_trailer.py
"""A dependency bot's commit is exempt from the trailer rule (G.55).

ONE MODULE, ONE CLAIM. These lived in test_commit_trailers, which claims G.29 --
every commit names its plan steps -- and pytestmark carries a single id, so the
two collided. The exemption is a different property anyway: G.29 says a human
commit must name what it serves, and this says a bot has nothing to name.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.requirement("G.55")


# --- a dependency bot cannot name a plan step (G.55) --------------------------
# Dependabot bumped actions/upload-artifact with no Plan-Step trailer, and every
# branch merging develop afterwards failed CI on a commit it did not create. A
# version bump serves no plan step and has no human to name one, so the gate
# could never pass -- the deterministic consequence of two correct components
# meeting, not a flake and not something a rerun fixes.
#
# EXEMPT FROM THE TRAILER RULE AND FROM NOTHING ELSE. 2026 practice matches the
# bot by its full address, anchored at both ends, so a crafted local part such as
# evil+dependabot[bot]@... is still judged. It is a hygiene guard rather than a
# security boundary: an author field is free text, and what actually stops a
# forged one is review before merge.

DEPENDABOT = "49699333+dependabot[bot]@users.noreply.github.com"


def test_a_dependency_bots_commit_needs_no_trailer() -> None:
    from otsafety_tooling.policy.trailers import problems

    assert (
        problems("⬆ Bump actions/upload-artifact\n", frozenset({"G.29"}), author=DEPENDABOT) == []
    )


def test_a_human_commit_still_needs_one() -> None:
    from otsafety_tooling.policy.trailers import problems

    assert problems("fix: something\n", frozenset({"G.29"}), author="someone@example.com") != []


def test_an_address_merely_containing_the_bots_name_is_still_judged() -> None:
    """Anchored at both ends: a crafted local part does not grant the exemption."""
    from otsafety_tooling.policy.trailers import problems

    forged = "evil+49699333+dependabot[bot]@users.noreply.github.com"
    assert problems("⬆ Bump something\n", frozenset({"G.29"}), author=forged) != []
