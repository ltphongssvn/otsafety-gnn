# tooling/src/otsafety_tooling/git/pr.py
"""Open a pull request, verify its checks, and merge it synchronously.

WHY THIS BLOCKS RATHER THAN RETURNING
Enabling auto-merge and returning moves the cost to the person, who watches
the Actions tab and confirms the merge by hand on every pull request.

WHY AUTO-MERGE IS NOT USED AT ALL
Since March 2026 auto-merge cannot be ENABLED until every requirement is
already met (HTTP 422), which leaves it useful only where it is unnecessary.
The merge endpoint is called directly instead.

AN INTENT IS NOT AN OUTCOME
That endpoint verifies nothing -- GitHub documents that it ignores failing
checks -- and a 200 can carry `merged: false`. So this observes, verifies,
acts, and then observes the RESULT:

    OBSERVE   wait for checks to register, watch them to completion, then wait
              for the rollup's conclusions to settle
    VERIFY    every conclusion acceptable, none still running, and not zero
    ACT       merge synchronously, as a merge commit (GitFlow)
    OBSERVE   parse the response and confirm merged is true

A FAILURE REPORTS BOTH STREAMS. A pre-push hook writes its whole report to
stdout while git's stderr says only "failed to push some refs".

SAFE TO RUN AGAIN. Before anything is pushed, the commits the branch has that
origin/develop lacks are counted. With none, the run pushes nothing and exits 0,
reporting the merged pull request if there is one. Re-running used to push the
merged branch -- re-creating it after GitHub deleted it on merge -- and then
fail to create a pull request with no commits.

Ported from cscie103-olap-oltp (src/cscie103_olap_oltp/git/pr.py).
"""

from __future__ import annotations

import subprocess
import sys
import time
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

PROTECTED = frozenset({"develop", "main"})
INTEGRATION_BRANCH = "develop"
RELEASE_BRANCH = "main"

# FleetManagement's empty-release loop: a content-free back-merge re-ran CI,
# which promoted again and cut an empty release. [skip ci] ends it.
BACK_MERGE_MESSAGE = "chore: back-merge main into develop [skip ci]"

# HOW LONG EACH PHASE MAY TAKE.
# Registration is fast: a workflow appears within seconds of a push.
CHECKS_APPEAR_TIMEOUT = 120
# The checks themselves. This repository's slowest job today is a Playwright
# shard (~4 minutes after queueing); twenty minutes leaves room for a cold
# runner while a hung workflow still fails here rather than being waited on.
CHECKS_COMPLETE_TIMEOUT = 1200
POLL_INTERVAL = 5


def report(result: subprocess.CompletedProcess[str]) -> None:
    """Print BOTH streams of a failed command."""
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def gh(*args: str, check: bool = True) -> str:
    """Run gh in the repository, or fail loudly."""
    result = subprocess.run(  # noqa: S603
        ["gh", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if check and result.returncode != 0:
        report(result)
        raise SystemExit(f"gh {' '.join(args)} failed")
    return result.stdout


class CheckConclusion(StrEnum):
    """Every conclusion GitHub reports.

    DEFINED BEFORE Check, WHICH ANNOTATES A FIELD WITH IT: pydantic resolves
    annotations at class creation, and no static gate catches the ordering.

    AN UNRECOGNISED VALUE FAILS VALIDATION. A value outside the documented set
    is a contract change, and reading it as "fine" is how a merge happens that
    nobody authorised.
    """

    SUCCESS = "SUCCESS"
    NEUTRAL = "NEUTRAL"
    SKIPPED = "SKIPPED"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    STARTUP_FAILURE = "STARTUP_FAILURE"
    STALE = "STALE"


# A SKIPPED CHECK HAS NOT FAILED: a path filter excluding a job (Playwright on a
# workflow-only change) must not block the merge.
PASSING_CONCLUSIONS = frozenset(
    {CheckConclusion.SUCCESS, CheckConclusion.NEUTRAL, CheckConclusion.SKIPPED}
)


class Check(BaseModel):
    """One status check on the pull request.

    extra="ignore": gh returns many fields this does not read. MergeResult
    forbids extras, because its three fields ARE the contract.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = ""
    conclusion: CheckConclusion | None = None

    @field_validator("conclusion", mode="before")
    @classmethod
    def empty_means_pending(cls, value: object) -> object:
        """gh reports a pending check as "", not null; normalise to one form."""
        return None if value == "" else value


class PullRequest(BaseModel):
    """The pull request as gh reports it, validated at the boundary."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    number: int
    state: str
    base: str = Field(default="", alias="baseRefName")
    merge_state: str = Field(default="", alias="mergeStateStatus")
    url: str = ""
    checks: tuple[Check, ...] = Field(default=(), alias="statusCheckRollup")

    @property
    def is_merged(self) -> bool:
        return self.state == "MERGED"

    @property
    def is_terminal(self) -> bool:
        return self.state in {"MERGED", "CLOSED"}

    @property
    def checks_settled(self) -> bool:
        """Every registered check has a conclusion.

        `bool(self.checks)` IS LOAD-BEARING: all() over an empty sequence is
        True, which would report a pull request with no checks as concluded.
        """
        return bool(self.checks) and all(c.conclusion is not None for c in self.checks)


class MergeResult(BaseModel):
    """What the merge endpoint returned: strict, and nothing else allowed."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    merged: bool
    sha: str
    message: str


class RerunPlan(BaseModel, frozen=True, extra="forbid"):
    """What a run of `pr` will do, decided before anything is pushed."""

    action: Literal["propose", "already_merged", "nothing"]
    ahead: NonNegativeInt = Field(strict=True)
    merged_pr: PositiveInt | None = Field(default=None, strict=True)
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def _merged_names_its_pull_request(self) -> Self:
        if self.action == "already_merged" and self.merged_pr is None:
            raise ValueError("already_merged must name the merged pull request")
        return self


def plan_rerun(ahead: int, merged_pr: int | None) -> RerunPlan:
    """Propose only when the branch has commits origin/develop lacks."""
    if ahead:
        return RerunPlan(
            action="propose",
            ahead=ahead,
            merged_pr=merged_pr,
            message=f"{ahead} commit(s) to propose into {INTEGRATION_BRANCH}",
        )
    if merged_pr is not None:
        return RerunPlan(
            action="already_merged",
            ahead=0,
            merged_pr=merged_pr,
            message=f"already merged in PR #{merged_pr}; nothing new to push. next: mise run sync",
        )
    return RerunPlan(
        action="nothing",
        ahead=0,
        message=f"nothing to propose: every commit is already in {INTEGRATION_BRANCH}",
    )


def commits_ahead(root: Path) -> int:
    """Commits on HEAD that origin/develop lacks, after refreshing origin."""
    fetched = git("fetch", "origin", "--prune", "--quiet", cwd=root)
    if fetched.returncode != 0:
        report(fetched)
        raise SystemExit("fetch failed; cannot tell what this branch would propose")
    counted = git("rev-list", "--count", f"origin/{INTEGRATION_BRANCH}..HEAD", cwd=root)
    if counted.returncode != 0:
        report(counted)
        raise SystemExit(f"could not compare HEAD with origin/{INTEGRATION_BRANCH}")
    return int(counted.stdout.strip())


def merged_pr_number(branch: str) -> int | None:
    """The most recent merged pull request from this branch, if any."""
    found = gh(
        "pr",
        "list",
        "--head",
        branch,
        "--state",
        "merged",
        "--json",
        "number",
        "--jq",
        ".[0].number // empty",
    ).strip()
    return int(found) if found else None


VIEW_FIELDS = "number,state,baseRefName,mergeStateStatus,statusCheckRollup,url"


def view_args(pr_number: int | None) -> list[str]:
    """The `gh pr view` arguments for one pull request.

    THE NUMBER IS THREADED THROUGH EVERY OBSERVATION. cscie103-olap-oltp's
    merge_when_green accepted a number but polled `gh pr view` with none,
    which reads the CURRENT BRANCH's pull request -- so merging a pull request
    that is not checked out (a Dependabot update) watched the wrong one.
    """
    reference = [str(pr_number)] if pr_number is not None else []
    return ["pr", "view", *reference, "--json", VIEW_FIELDS]


def pr_state(pr_number: int | None = None) -> PullRequest:
    return PullRequest.model_validate_json(gh(*view_args(pr_number)))


def describe_transitions(before: tuple[Check, ...], after: tuple[Check, ...]) -> tuple[str, ...]:
    """One line per check that appeared or concluded, in name order.

    WHY NOT `gh pr checks --watch`. It re-emits the COMPLETE status every few
    seconds by design: a screen for a human, not a log. Inside a recorded run
    that became eighteen near-identical blocks and most of the run's captured
    bytes. Reporting transitions leaves a handful of meaningful lines that read
    the same in a terminal, a log and a record.

    A CHECK THAT VANISHES IS NOT NEWS: the rollup can drop a skipped job between
    polls, and announcing that would be noise of a different kind.
    """
    seen = {check.name: check.conclusion for check in before}
    lines = []
    for check in sorted(after, key=lambda item: item.name):
        if check.name not in seen:
            state = check.conclusion.value if check.conclusion else "queued"
            lines.append(f"{check.name} {state}")
        elif check.conclusion is not None and seen[check.name] is None:
            lines.append(f"{check.name} {check.conclusion.value}")
    return tuple(lines)


def wait_for_checks_to_register(deadline: float, pr_number: int | None) -> bool:
    """A pull request has no checks for a few seconds after the push."""
    while time.monotonic() < deadline:
        checks = pr_state(pr_number).checks
        if checks:
            print("checks registered: " + ", ".join(check.name for check in checks))
            return True
        time.sleep(POLL_INTERVAL)
    return False


def wait_for_checks(deadline: float, pr_number: int | None) -> PullRequest:
    """Poll until every check has concluded, reporting only what changed.

    REPLACES A WATCH PLUS A SETTLE PHASE. The old code shelled out to
    `gh pr checks --watch` and then waited again for the rollup to catch up,
    because the watcher's own output could not be trusted as the record of what
    happened. Polling the rollup is the single source, so there is one wait and
    one budget.
    """
    observed = pr_state(pr_number)
    while True:
        if observed.is_terminal or observed.checks_settled:
            return observed
        if time.monotonic() >= deadline:
            pending = ", ".join(c.name for c in observed.checks if c.conclusion is None)
            raise SystemExit(
                f"checks did not conclude within {CHECKS_COMPLETE_TIMEOUT}s: {pending}"
            )
        time.sleep(POLL_INTERVAL)
        latest = pr_state(pr_number)
        for line in describe_transitions(observed.checks, latest.checks):
            print(line)
        observed = latest


def verify_checks(checks: tuple[Check, ...]) -> None:
    """Refuse unless every check concluded acceptably. FAIL CLOSED on none."""
    if not checks:
        raise SystemExit("merge refused: no checks reported at all")

    unfinished = [c.name for c in checks if c.conclusion is None]
    if unfinished:
        raise SystemExit(f"merge refused: checks still running: {', '.join(unfinished)}")

    failing = [c.name for c in checks if c.conclusion not in PASSING_CONCLUSIONS]
    if failing:
        raise SystemExit(f"merge refused: unacceptable checks: {', '.join(failing)}")


def verify_target(pr: PullRequest, base: str = INTEGRATION_BRANCH) -> None:
    """Refuse a pull request that does not target the expected branch.

    GITFLOW: feature and dependency updates enter through develop, which is the
    default, so `mise run pr` still cannot merge into main. Only `promote` asks
    for main, explicitly.
    """
    if pr.base != base:
        raise SystemExit(
            f"merge refused: PR #{pr.number} targets {pr.base or '(unknown)'!r}, not {base!r}"
        )


def execute_merge(pr_number: int) -> MergeResult:
    """Merge synchronously as a merge commit and return the PARSED result.

    405 means not mergeable; 409 means the head moved since the checks ran.
    """
    response = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "gh",
            "api",
            f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/merge",
            "-X",
            "PUT",
            "-f",
            "merge_method=merge",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if response.returncode != 0:
        report(response)
        raise SystemExit("merge request failed")

    return MergeResult.model_validate_json(response.stdout)


def merge_when_green(
    pr_number: int | None = None, base: str = INTEGRATION_BRANCH
) -> MergeResult | None:
    """Observe, verify, act, observe the result."""
    if not wait_for_checks_to_register(time.monotonic() + CHECKS_APPEAR_TIMEOUT, pr_number):
        raise SystemExit(f"no checks registered within {CHECKS_APPEAR_TIMEOUT}s")

    observed = wait_for_checks(time.monotonic() + CHECKS_COMPLETE_TIMEOUT, pr_number)
    if observed.is_terminal:
        print(f"PR #{observed.number} is already {observed.state}")
        return None

    verify_target(observed, base)
    verify_checks(observed.checks)

    result = execute_merge(observed.number)
    if not result.merged:
        raise SystemExit(f"PR #{observed.number} was not merged: {result.message}")

    print(f"merged {result.sha[:12]}: {result.message}")
    return result


def merge_existing(pr_number: int) -> int:
    """Verify and merge a pull request that is not checked out here.

    For Dependabot updates and for a branch opened from another machine: the
    same observe-verify-act-observe sequence, without a push.
    """
    merge_when_green(pr_number)
    final = pr_state(pr_number)
    if not final.is_merged:
        raise SystemExit(f"PR #{final.number} is {final.state}, not MERGED.")
    print(f"\nPR #{final.number} merged. next: mise run sync")
    return 0


class PromotionPlan(BaseModel, frozen=True, extra="forbid"):
    """Whether develop has anything main lacks."""

    action: Literal["promote", "nothing"]
    ahead: NonNegativeInt = Field(strict=True)


def plan_promotion(ahead: int) -> PromotionPlan:
    return PromotionPlan(action="promote" if ahead else "nothing", ahead=ahead)


def _git_or_exit(*args: str, why: str) -> str:
    result = git(*args, cwd=REPO_ROOT)
    if result.returncode != 0:
        report(result)
        raise SystemExit(why)
    return result.stdout.strip()


def back_merge() -> None:
    """Bring main's merge commit into develop, so develop never drifts behind.

    FleetManagement's third bug: without this, develop falls one commit behind
    main at every release.
    """
    _git_or_exit(
        "fetch",
        "origin",
        RELEASE_BRANCH,
        INTEGRATION_BRANCH,
        "--quiet",
        why="fetch failed before the back-merge",
    )
    contained = git(
        "merge-base", "--is-ancestor", f"origin/{RELEASE_BRANCH}", "HEAD", cwd=REPO_ROOT
    )
    if contained.returncode == 0:
        print(f"{INTEGRATION_BRANCH} already contains {RELEASE_BRANCH}; no back-merge needed")
        return
    _git_or_exit(
        "merge",
        "--no-ff",
        f"origin/{RELEASE_BRANCH}",
        "-m",
        BACK_MERGE_MESSAGE,
        why="back-merge failed; develop is unchanged on origin",
    )
    _git_or_exit("push", "origin", INTEGRATION_BRANCH, why="push of the back-merge refused")
    print(f"back-merged {RELEASE_BRANCH} into {INTEGRATION_BRANCH} with [skip ci]")


def promote() -> int:
    """Merge develop into main through a verified pull request, then back-merge.

    Ported from FleetManagement's promote.yml. Run under the person's own gh
    login, so the merge emits a push event and release.yml cuts the version;
    a GITHUB_TOKEN merge would not, which is why FleetManagement needed an App.
    """
    branch = _git_or_exit("rev-parse", "--abbrev-ref", "HEAD", why="cannot read the branch")
    if branch != INTEGRATION_BRANCH:
        raise SystemExit(f"refusing: promote runs from {INTEGRATION_BRANCH}, not {branch!r}")
    if _git_or_exit("status", "--porcelain", why="cannot read the working tree"):
        raise SystemExit("refusing: the working tree is not clean")
    _git_or_exit("fetch", "origin", "--prune", "--tags", "--quiet", why="fetch failed")
    local = _git_or_exit("rev-parse", "HEAD", why="cannot resolve HEAD")
    remote = _git_or_exit("rev-parse", f"origin/{INTEGRATION_BRANCH}", why="no origin/develop")
    if local != remote:
        raise SystemExit(
            f"refusing: local {INTEGRATION_BRANCH} differs from origin; run mise run sync"
        )

    ahead = int(
        _git_or_exit(
            "rev-list",
            "--count",
            f"origin/{RELEASE_BRANCH}..origin/{INTEGRATION_BRANCH}",
            why="cannot compare main with develop",
        )
    )
    if plan_promotion(ahead).action == "nothing":
        print(f"nothing to promote: {RELEASE_BRANCH} already has every commit")
        return 0

    query = (
        "pr",
        "list",
        "--base",
        RELEASE_BRANCH,
        "--head",
        INTEGRATION_BRANCH,
        "--state",
        "open",
        "--json",
        "number",
        "--jq",
        ".[0].number // empty",
    )
    existing = gh(*query).strip()
    if existing:
        print(f"reusing open promotion PR #{existing}")
    else:
        gh(
            "pr",
            "create",
            "--base",
            RELEASE_BRANCH,
            "--head",
            INTEGRATION_BRANCH,
            "--title",
            "release: promote develop to main",
            "--body",
            f"{ahead} commit(s) from {INTEGRATION_BRANCH}. Merging runs "
            "release.yml, which cuts the version tag and GitHub Release.",
        )
        existing = gh(*query).strip()
    number = int(existing)
    print(f"promoting {ahead} commit(s) through PR #{number}\n")

    merge_when_green(number, base=RELEASE_BRANCH)
    final = pr_state(number)
    if not final.is_merged:
        raise SystemExit(f"PR #{number} is {final.state}, not MERGED")

    back_merge()
    print(
        "\npromoted. next: the Release workflow cuts the tag; then check out the "
        "tag and run mise run deploy:site"
    )
    return 0


def parse_number(argv: list[str]) -> int:
    """The single positive integer argument of `merge`, or a usage error."""
    if len(argv) != 1 or not argv[0].isdigit() or int(argv[0]) < 1:
        raise SystemExit("usage: python -m otsafety_tooling.git.pr merge <number>")
    return int(argv[0])


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["merge"]:
        return merge_existing(parse_number(args[1:]))
    if args == ["promote"]:
        return promote()
    if args:
        raise SystemExit("usage: python -m otsafety_tooling.git.pr [merge <number> | promote]")

    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=REPO_ROOT).stdout.strip()
    if branch in PROTECTED:
        raise SystemExit(f"refusing: on protected branch {branch!r}; work on a feature branch")

    # DECIDE BEFORE PUSHING: a merged branch must not be pushed again.
    ahead = commits_ahead(REPO_ROOT)
    plan = plan_rerun(ahead, merged_pr_number(branch) if ahead == 0 else None)
    if plan.action != "propose":
        print(plan.message)
        return 0

    push = git("push", "-u", "origin", branch, cwd=REPO_ROOT)
    if push.returncode != 0:
        report(push)
        raise SystemExit("push refused; see the hook output above")

    # AN EXISTING PULL REQUEST IS THE NORMAL CASE after every correction.
    existing = gh(
        "pr",
        "list",
        "--head",
        branch,
        "--state",
        "open",
        "--json",
        "number",
        "--jq",
        ".[0].number // empty",
    ).strip()

    if existing:
        print(f"reusing open PR #{existing}")
    else:
        gh("pr", "create", "--base", INTEGRATION_BRANCH, "--head", branch, "--fill")

    print(f"opened {pr_state().url}\n")
    merge_when_green()

    final = pr_state()
    if not final.is_merged:
        raise SystemExit(f"PR #{final.number} is {final.state}, not MERGED.")

    print(f"\nPR #{final.number} merged. next: mise run sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
