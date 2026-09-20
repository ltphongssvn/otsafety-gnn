# tooling/tests/test_paths.py
"""The repository root is derived from the package and verified by a marker."""

from pathlib import Path

import pytest

from otsafety_tooling.paths import REPO_ROOT, ROOT_MARKER, locate_root


def test_repo_root_contains_the_marker() -> None:
    assert (REPO_ROOT / ROOT_MARKER).is_file()


def test_repo_root_is_the_workspace_root() -> None:
    """The workspace pyproject sits beside the marker, not a member's."""
    assert "[tool.uv.workspace]" in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_a_location_without_the_marker_is_refused(tmp_path: Path) -> None:
    """An installed wheel would put __file__ in site-packages; that must fail loudly."""
    fake = tmp_path / "a" / "b" / "c" / "paths.py"
    fake.parent.mkdir(parents=True)
    fake.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match=ROOT_MARKER):
        locate_root(fake)
