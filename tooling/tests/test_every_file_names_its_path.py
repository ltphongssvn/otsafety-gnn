# tooling/tests/test_every_file_names_its_path.py
"""Every tracked file opens with its repository path (G.21).

WHY A PATH ON THE FIRST LINE. A file read on its own -- in a diff, a search
result, a terminal pager, an agent's context window -- says nothing about where
it lives. The path says it, and costs one line. The working rules have asked for
it since the first plan; one test checked it for .gitignore alone, so everywhere
else it was habit, and habit had already lapsed in thirty-five files.

WHERE THE PATH MAY SIT. A shebang must be the first line of a script and a `---`
must open an Astro file, so the path follows whichever of those the format
requires. It must appear within the first three lines, which is exactly enough
for either and not enough to bury.

WHAT IS EXEMPT, AND WHY IT IS NAMED. A generated file carries the path its
GENERATOR writes, and hand-editing one would be undone on the next run: those are
fixed at the generator instead. Formats with no comment syntax -- JSON above all
-- cannot carry one at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from otsafety_tooling.paths import REPO_ROOT
from otsafety_tooling.policy.file_headers import missing_path_header

pytestmark = pytest.mark.requirement("G.21")


def test_every_tracked_file_names_its_own_path() -> None:
    offenders = missing_path_header(REPO_ROOT)
    assert offenders == [], (
        f"{len(offenders)} tracked files do not name their path: {offenders[:8]}"
    )


def test_a_file_whose_path_is_absent_is_reported(tmp_path: Path) -> None:
    """The check fails when it should: a scan that cannot fail proves nothing."""
    from otsafety_tooling.policy.file_headers import names_its_path

    assert names_its_path("a/b.py", "# a/b.py\nx = 1\n")
    assert not names_its_path("a/b.py", "x = 1\n")


def test_a_shebang_or_frontmatter_may_come_first() -> None:
    """Both must be the first line of their format; the path follows."""
    from otsafety_tooling.policy.file_headers import names_its_path

    assert names_its_path("s.py", "#!/usr/bin/env python3\n# s.py\n")
    assert names_its_path("p.astro", "---\n// p.astro\n---\n")
