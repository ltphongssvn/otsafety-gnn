# tooling/src/otsafety_tooling/paths.py
"""Where the repository is, derived from this file rather than from cwd.

A GIT HOOK RUNS FROM WHEREVER THE USER HAPPENED TO BE. A root keyed on the
working directory would read a different repository depending on who invoked
it, so the root comes from this file's location instead.

    tooling/src/otsafety_tooling/paths.py  ->  up three  ->  repository root

THE ROOT IS VERIFIED, NOT ASSUMED. The workspace installs this package in
editable mode, so __file__ lives in the checkout. If it were ever installed as
a regular wheel, __file__ would point into site-packages and "up three" would
land somewhere unrelated -- silently. toolchain.json is the marker: it exists
only at this repository's root.
"""

from __future__ import annotations

from pathlib import Path

ROOT_MARKER = "toolchain.json"


def locate_root(anchor: Path) -> Path:
    """The working tree this file is in, ASKED OF GIT rather than counted off.

    UP-THREE WAS WRONG AND MUTATION TESTING PROVED IT. mutmut copies the source
    into ./mutants and runs the suite from there, so __file__ lands in the
    scratch tree -- and because that copy carries toolchain.json, the marker
    check passed and a wrong root was returned in silence. The guard was
    defeated by the very copy that made the suite runnable.

    --show-toplevel ANSWERS "THE TREE I AM IN", which is what this wants: it is
    right in a linked worktree and right in the main checkout. artifacts_root
    asks a DIFFERENT question -- where the MAIN checkout is, so evidence
    outlives a removed worktree -- and rightly uses `git worktree list`, which
    reports the whole clone wherever it runs.
    """
    import os
    import subprocess

    minimal = {
        key: value
        for key, value in os.environ.items()  # noqa: TID251
        if key in ("PATH", "HOME")
    }
    located = subprocess.run(  # noqa: S603
        ["git", "-C", str(anchor.resolve().parent), "rev-parse", "--show-toplevel"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env=minimal,
    )
    if located.returncode == 0 and located.stdout.strip():
        found = Path(located.stdout.strip())
        if (found / ROOT_MARKER).is_file():
            return found

    # NO GIT, OR NOT A REPOSITORY: an installed wheel or a released archive.
    # Counting parents is the fallback, and the marker must still be there.
    root = anchor.resolve().parents[3]
    if not (root / ROOT_MARKER).is_file():
        raise RuntimeError(
            f"{root} is not the repository root ({ROOT_MARKER} not found). "
            "otsafety-tooling must be installed from the workspace in editable "
            "mode: run `mise run setup`."
        )
    return root


def __getattr__(name: str) -> Path:
    """REPO_ROOT, found once and cached, rather than on every import."""
    if name != "REPO_ROOT":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    found = locate_root(Path(__file__))
    globals()["REPO_ROOT"] = found
    return found
