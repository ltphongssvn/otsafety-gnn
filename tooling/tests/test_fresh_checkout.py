# tooling/tests/test_fresh_checkout.py
"""A fresh checkout runs only the tools its lockfiles installed.

WHY THIS EXISTS. setup installed Python and the git hooks but not the site, so a
new worktree failed four of ten gates with "astro: command not found" until
someone knew to run site:install. Worse, a test invoked astro through a package
runner, and with nothing installed the runner fetched the latest release from
the registry and ran it -- an unpinned tool, downloaded at test time, in a
repository that pins every other binary by digest. 2026 practice: run
development binaries through the project, and never let a package runner install
one. The markers below are assembled from fragments, so this file does not
itself read as carrying what it forbids.
"""

from __future__ import annotations

import re

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.exemptions import candidates

RUNNER = re.compile(r"\b(bun" + "x|np" + "x|bun[ \t]+" + "x)\b")


def test_setup_installs_both_halves_of_the_toolchain() -> None:
    setup = "\n".join(read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["setup"].scripts)
    assert "uv sync --locked" in setup
    assert "site:install" in setup, "a fresh checkout must have the site installed too"


def test_no_tracked_file_lets_a_package_runner_install_a_tool() -> None:
    """A runner that may install fetches the latest version, unpinned, at run time.

    Only what RUNS is scanned: the plan and its trace are prose about this repository,
    and inside code or configuration the text after a comment marker is prose too.
    """
    offenders = []
    for relative in candidates(REPO_ROOT):
        path = REPO_ROOT / relative
        if (
            not path.is_file()
            or path.suffix in {".lock", ".json"}
            or relative.startswith("context/")
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            code = re.split(r"#|//", line, maxsplit=1)[0]
            if RUNNER.search(code) and "--no-install" not in code:
                offenders.append(f"{relative}:{number}")
    assert offenders == [], offenders
