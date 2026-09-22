# tooling/tests/test_commit_trailers.py
"""Every commit names the plan steps it serves, in a Plan-Step trailer.

WHY THIS EXISTS. Git is the record of this repository's documentation, and the
plan is the record of its intent; a trailer binds each change to the steps it
serves, so history and plan cannot disagree. A merged commit message once cited
a document never written -- a claim nothing checked.

2026 PRACTICE. One rule read from two places: the commit-msg hook checks a
message as it is written, the floor; a check over every commit since the cutoff,
run in the pre-push hook and CI, is the ceiling. The message is read as git will
store it -- comments and everything below a scissors line cut -- and parsed by
git interpret-trailers, the parser behind %(trailers). Merges git writes itself
are exempt. Ids resolve against the plan in the commit's own tree.
"""

from __future__ import annotations

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.lefthook_config import LefthookConfig
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.trailers import CUTOFF, commits_since_cutoff, plan_steps, problems

IDS = frozenset({"G.28", "G.29", "X.README"})


def test_a_valid_trailer_passes() -> None:
    assert problems("feat: a thing\n\nWhy it matters.\n\nPlan-Step: G.29\n", IDS) == []


def test_several_trailers_pass() -> None:
    assert problems("feat: a\n\nbody\n\nPlan-Step: G.28\nPlan-Step: X.README\n", IDS) == []


def test_a_missing_trailer_is_refused() -> None:
    assert any("no Plan-Step" in p for p in problems("feat: a thing\n\nJust a body.\n", IDS))


def test_an_unknown_id_is_refused_by_name() -> None:
    assert any("G.99" in p for p in problems("feat: a\n\nbody\n\nPlan-Step: G.99\n", IDS))


def test_a_trailer_buried_in_the_body_is_not_a_trailer() -> None:
    assert problems("feat: a\n\nPlan-Step: G.29\n\nMore prose after it.\n", IDS) != []


def test_comments_and_scissors_are_cut_as_git_cuts_them() -> None:
    message = (
        "feat: a\n\nbody\n\nPlan-Step: G.29\n# a comment\n"
        "# ------------------------ >8 ------------------------\n"
        "Plan-Step: G.99\n"
    )
    assert problems(message, IDS) == []


def test_a_merge_is_exempt() -> None:
    assert problems("Merge pull request #1 from x/y\n", IDS, is_merge=True) == []


def test_every_commit_since_the_cutoff_names_its_plan_steps() -> None:
    """The ceiling: each commit checked against the plan in its own tree."""
    checked = commits_since_cutoff(REPO_ROOT)
    assert checked, f"no commits found since {CUTOFF}; the gate would pass vacuously"
    failures = {
        sha[:9]: p
        for sha, message, is_merge in checked
        if (p := problems(message, plan_steps(REPO_ROOT, sha), is_merge=is_merge))
    }
    assert failures == {}


def test_the_floor_runs_the_same_rule() -> None:
    hook = read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig).commit_msg
    assert hook is not None
    assert any(job.run.startswith("mise run policy:trailers") for job in hook.jobs)
