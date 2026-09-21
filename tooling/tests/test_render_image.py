# tooling/tests/test_render_image.py
"""The renderer is pinned, like every other executable this project runs.

WHY THIS EXISTS. toolchain.json pins uv, bun, gh and mise by digest, and
nix flake check runs each one and asserts the version it reports. The pdf was
the exception: Chromium came from `playwright install`, and the text-shaping
stack -- fontconfig and FreeType on Linux, CoreText on macOS -- came from
whatever the machine had. The one deliverable whose correctness depends on text
metrics was the only thing built outside the pinned toolchain, and it showed:
identical HTML rendered one page on a laptop and two on a runner, and four
successive fixes inside the sheet all missed, because the unpinned thing was the
renderer rather than the document.

THE amd64 MANIFEST DIGEST, NOT THE INDEX. The index digest resolves to arm64 on
this laptop and amd64 on a runner, which is the same divergence wearing a
different hat. Pinning the single-platform image means both machines run the
same bytes. cs1090a-recsys reached the same conclusion for its compose services:
pin by digest, target linux/amd64.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from otsafety_tooling.paths import REPO_ROOT

TOOLCHAIN = REPO_ROOT / "toolchain.json"
DOCKERFILE = REPO_ROOT / "docker" / "render.Dockerfile"

# Read from the registry on 2026-09-20 for v1.63.0-noble, the tag matching the
# pinned playwright library. A digest that no longer matches means the tag moved,
# which is exactly what a pin is for.
EXPECTED_PLATFORM = "linux/amd64"
DIGEST_PREFIX = "sha256:96b39581"


def _toolchain() -> dict[str, Any]:
    if not TOOLCHAIN.is_file():
        pytest.fail(f"no toolchain at {TOOLCHAIN}")
    loaded: dict[str, Any] = json.loads(TOOLCHAIN.read_text(encoding="utf-8"))
    return loaded


def test_the_render_image_is_declared_beside_every_other_executable() -> None:
    """A renderer pinned somewhere else is a renderer nobody audits."""
    toolchain = _toolchain()
    assert "render_image" in toolchain, (
        "toolchain.json pins uv, bun, gh and mise but not the browser that renders the deliverable"
    )


def test_the_render_image_is_pinned_by_digest_to_one_platform() -> None:
    entry = _toolchain()["render_image"]
    assert entry["platform"] == EXPECTED_PLATFORM
    assert entry["digest"].startswith(DIGEST_PREFIX), (
        "the digest must be the linux/amd64 manifest, not the multi-platform "
        "index: an index resolves to arm64 on a laptop and amd64 on a runner"
    )
    assert "@sha256:" in entry["reference"], "the reference must carry its digest"


def test_the_render_image_matches_the_pinned_playwright() -> None:
    """A browser from a different Playwright is a different browser."""
    entry = _toolchain()["render_image"]
    assert "v1.63.0" in entry["reference"], (
        "the image tag must match the playwright version in uv.lock"
    )


def test_the_dockerfile_pins_the_same_digest() -> None:
    if not DOCKERFILE.is_file():
        pytest.fail(f"no render Dockerfile at {DOCKERFILE}")
    body = DOCKERFILE.read_text(encoding="utf-8")
    assert _toolchain()["render_image"]["digest"] in body, (
        "the Dockerfile and toolchain.json name different images"
    )
