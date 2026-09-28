# tooling/src/otsafety_tooling/policy/licences.py
"""Whether anything a closed source withholds is tracked in this repository.

OBSERVED, NOT ASSERTED. The rule asks git what it tracks and matches each
withheld pattern against it. A pattern matching nothing is the expected result,
so the caller must establish separately that the matcher can match -- a check
that cannot fail has not been shown to work.
"""

from __future__ import annotations

from pathlib import Path

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.sources import DataSources
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

SOURCES = Path("context") / "sources.yaml"


def tracked(root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Every path git tracks, which is what redistribution means here."""
    return tuple(git("ls-files", cwd=root).stdout.split())


def offending(patterns: tuple[str, ...], paths: tuple[str, ...]) -> list[str]:
    """The pure rule, so a caller can prove it able to fire."""
    from fnmatch import fnmatch

    return sorted({path for pattern in patterns for path in paths if fnmatch(path, pattern)})


def redistributed(root: Path = REPO_ROOT) -> list[str]:
    """Tracked files matching what a closed source says must not ship."""
    sources = read_yaml(root / SOURCES, DataSources)
    withheld = tuple(
        pattern for source in sources.sources if not source.open for pattern in source.withheld
    )
    return offending(withheld, tracked(root))
