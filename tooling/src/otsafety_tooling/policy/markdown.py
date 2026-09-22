# tooling/src/otsafety_tooling/policy/markdown.py
"""No Markdown in the repository: the one rule behind the hook and the gate.

Git is the record of this repository's documentation: commit bodies, and the
comments in the code and configuration they explain. A prose document beside
the code describes it from outside, and nothing checks the two against each
other -- a merged commit message once cited a context document never written.

The pre-commit hook runs main() over staged files, the floor. The test suite
runs forbidden() over tracked files, the ceiling, in the pre-push hook and in
CI, so a skipped hook still cannot land a Markdown file through a pull request.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

FORBIDDEN_SUFFIXES: tuple[str, ...] = (".md", ".markdown", ".mdx")


def forbidden(paths: Iterable[str]) -> list[str]:
    """Every path that is Markdown, whatever its case or depth."""
    return [path for path in paths if path.lower().endswith(FORBIDDEN_SUFFIXES)]


def _listed(root: Path, *args: str) -> list[str]:
    result = git(*args, "-z", cwd=root)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [path for path in result.stdout.split("\0") if path]


def tracked(root: Path) -> list[str]:
    return _listed(root, "ls-files")


def staged(root: Path) -> list[str]:
    return _listed(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")


def main() -> int:
    found = forbidden(staged(REPO_ROOT))
    if found:
        print(  # noqa: T201
            "refusing: Markdown is not kept in this repository. Record it in the commit "
            "message, or in the code and configuration it explains:\n  " + "\n  ".join(found),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
