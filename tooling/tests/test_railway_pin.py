# tooling/tests/test_railway_pin.py
"""The deploy tool is pinned like every other executable, past a release cooldown.

WHY NOT brew OR npm. Every executable this repository runs is the vendor's own
release artifact, recorded with its digest in toolchain.json and asserted by nix
flake check. A deploy tool installed ad hoc is the unpinned-renderer mistake
again: the one executable nobody pins is the one that differs between machines.

WHY v5.54.1 AND NOT THE LATEST. Railway ships several releases a day; the newest
was published hours before this pin. Compromised releases are typically caught
within days, which is why uv has exclude-newer and pnpm has minimumReleaseAge. A
tool that deploys to production is pinned to the newest release at least seven
days old.

WHY GITHUB'S DIGESTS. Railway publishes no checksum file. The digests below are
the ones GitHub recorded for each asset at upload, not ones computed from a local
download -- a digest of my own download only proves I downloaded something.
"""

from __future__ import annotations

from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.toolchain import BinaryTool, Platform, Toolchain
from otsafety_tooling.paths import REPO_ROOT

VERSION = "5.54.1"
DIGESTS: dict[Platform, str] = {
    "aarch64-darwin": "703fb3988326ea9814c0dbe7ffdaaa26ac35075d8bd7bb2e5fc61cb79472611a",
    "x86_64-linux": "f9311cc8a8b9102e1728306e60c588f0fdb40ab8e42307e6b8fe1ae109be5b9c",
}


def _railway() -> BinaryTool:
    return read_json(REPO_ROOT / "toolchain.json", Toolchain).railway


def test_railway_is_pinned_to_the_cooled_down_release() -> None:
    assert _railway().version == VERSION


def test_both_platforms_carry_the_digest_github_recorded() -> None:
    artifacts = _railway().artifacts
    for system, digest in DIGESTS.items():
        assert artifacts[system].sha256 == digest, f"{system} digest differs"
        assert f"v{VERSION}" in artifacts[system].url


def test_the_linux_build_is_the_static_musl_one() -> None:
    """Statically linked, so it runs on any runner without patching."""
    assert "linux-musl" in _railway().artifacts["x86_64-linux"].url


def test_the_binary_sits_at_the_archive_root() -> None:
    """The first tool with no top-level directory in its archive."""
    entry = _railway()
    assert entry.binaries == ("railway",)
    for system in DIGESTS:
        assert entry.artifacts[system].dir == "."
