# tooling/tests/test_browser_tests_run_on_linux.py
"""The browser tests run, on Linux, before a merge (7.2).

THE STEP WAS PROVED BY A WORKFLOW FILE EXISTING. A file is inspection: it shows
the artefact and not that anything runs. Required checks have gone green
elsewhere precisely because no check parses the workflow at all.

READ AS STRUCTURE, NEVER AS TEXT. The sibling tests here record why: a
substring check passed on a matching comment. 2026 practice is migrating
workflow tests away from substring searches and homemade indentation parsers
towards triggers, jobs and steps read as parsed structure -- and a file can be
valid YAML while being invalid to Actions, which text scanning never catches.

PLAYWRIGHT IS THE POINT. mise run test is the fast gate and installs no browser;
test:e2e is the one that drives a real browser against the built site. If that
never runs on a runner, the acceptance tests exist and prove nothing.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.workflow import Workflow
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("7.2")

SITE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test-site.yml"


def _site() -> Workflow:
    return read_yaml(SITE_WORKFLOW, Workflow)


def _runs(workflow: Workflow) -> str:
    return "\n".join(step.run or "" for job in workflow.jobs.values() for step in job.steps)


def test_the_site_workflow_has_jobs_to_read() -> None:
    """THE PRECONDITION: a workflow whose jobs parsed as nothing asserts nothing.

    An Actions file can be valid YAML and invalid to Actions -- a job key at
    column zero makes `jobs` parse as null, the workflow is refused, and no
    check run is ever created. Every assertion below is vacuous without this.
    """
    assert _site().jobs, "the site workflow declares no jobs"


def test_the_browser_tests_run_in_the_workflow() -> None:
    """A browser test nobody runs is a file, not a gate."""
    runs = _runs(_site())
    assert "test:e2e" in runs, "the site workflow never runs the acceptance tests"


def test_the_browser_is_installed_before_it_is_driven() -> None:
    """Playwright is optional by design, so the runner installs it explicitly."""
    runs = _runs(_site())
    assert "e2e:install" in runs, "the workflow drives a browser it never installed"
    assert runs.index("e2e:install") < runs.index("test:e2e"), (
        "the browser is driven before it is installed"
    )


def test_every_job_runs_on_linux() -> None:
    """The laptop is macOS; a Linux-only regression merges unless a runner sees it."""
    wrong = {
        name: job.runs_on for name, job in _site().jobs.items() if job.runs_on != "ubuntu-latest"
    }
    assert wrong == {}, f"jobs not on Linux: {wrong}"


def test_it_runs_before_a_merge_rather_than_after() -> None:
    """A check that runs after merging cannot refuse anything."""
    assert _site().runs_on("pull_request"), "the site workflow does not run on pull requests"


def test_a_workflow_that_skips_the_browser_is_refused() -> None:
    """THE PAIRED NEGATIVE: the rule is shown to fire, not assumed to.

    EVERY ASSERTION ABOVE IS A TRUE NEGATIVE -- each passes when the workflow is
    right and would pass just as happily against a rule that examined nothing.
    What proves a rule is the fixture it REFUSES, so this builds a workflow that
    runs the site's unit tests on Linux and never drives a browser, and requires
    the same reading to reject it.

    CONSTRUCTED, NOT FOUND. A second real workflow to point at would tie this to
    whatever the repository happens to contain; the fixture is written here so
    the answer is the same on a laptop, a runner and a sandbox.
    """
    from otsafety_tooling.contracts.files import parse_yaml

    skipping = parse_yaml(
        "\n".join(
            (
                "name: test-site",
                "on:",
                "  pull_request:",
                "jobs:",
                "  site:",
                "    runs-on: ubuntu-latest",
                "    steps:",
                "      - run: mise run site:build",
                "      - run: mise run site:types",
            )
        ),
        Workflow,
    )
    assert skipping.jobs, "the fixture parsed no jobs, so it refuses nothing"
    assert skipping.runs_on("pull_request"), "the fixture is not comparable to the real one"
    assert all(job.runs_on == "ubuntu-latest" for job in skipping.jobs.values())
    assert "test:e2e" not in _runs(skipping), (
        "the fixture drives a browser, so it cannot show the rule refusing one that does not"
    )
