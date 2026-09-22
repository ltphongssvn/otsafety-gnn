# tooling/tests/test_no_markdown.py
"""No Markdown in the repository: one rule, behind a floor and a ceiling.

WHY THIS EXISTS. A prose document beside the code describes it from outside,
and nothing checks the two against each other: a merged commit message once
cited a context document that was never written. Git is the record of this
repository's documentation -- commit bodies, and the comments in the code and
configuration they explain.

ONE RULE, TWO ENTRY POINTS. The pre-commit hook runs it over staged files, the
floor; this test runs it over tracked files, the ceiling, in the pre-push hook
and in CI, so skipping a hook still cannot land a Markdown file through a pull
request. A glob in lefthook.yml would be a second copy of the rule.
"""

from __future__ import annotations

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.lefthook_config import LefthookConfig
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.markdown import FORBIDDEN_SUFFIXES, forbidden, tracked


def test_the_rule_names_every_markdown_suffix() -> None:
    assert {".md", ".markdown", ".mdx"} <= set(FORBIDDEN_SUFFIXES)


def test_matching_ignores_case_and_depth() -> None:
    assert forbidden(["README.MD", "a/b/notes.markdown", "x.py", "mdfile.txt"]) == [
        "README.MD",
        "a/b/notes.markdown",
    ]


def test_no_markdown_is_tracked() -> None:
    assert forbidden(tracked(REPO_ROOT)) == []


def test_the_floor_runs_the_same_rule() -> None:
    hook = read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig).pre_commit
    assert hook is not None
    assert any(job.run == "mise run policy:no-markdown" for job in hook.jobs)
