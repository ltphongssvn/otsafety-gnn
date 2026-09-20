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
    """The repository root three levels above `anchor`'s package, or raise."""
    root = anchor.resolve().parents[3]
    if not (root / ROOT_MARKER).is_file():
        raise RuntimeError(
            f"{root} is not the repository root ({ROOT_MARKER} not found). "
            "otsafety-tooling must be installed from the workspace in editable "
            "mode: run `mise run setup`."
        )
    return root


REPO_ROOT = locate_root(Path(__file__))
