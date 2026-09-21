# tooling/tests/test_toolchain_declaration.py
"""Every executable the project needs is declared once, with a digest.

THE GAP THIS CLOSES. Setting up FAS OnDemand needed gh and mise installed by
hand, because toolchain.json declared uv, bun and gh but not mise -- so the
bootstrap could not have installed it even if the bootstrap had existed.

THE DIGESTS ARE NOT INVENTED. mise's entry carries the checksums published in
that release's own SHASUMS256.txt; the Linux one is the value that matched the
downloaded bytes on the cluster, byte for byte.
"""

import tomllib

import pytest

from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.toolchain import BinaryTool, Toolchain
from otsafety_tooling.paths import REPO_ROOT

PLATFORMS = ("x86_64-linux", "aarch64-darwin")
MISE_LINUX_DIGEST = "e4767e4854af5daeff2191b2bbdc94f834742a23efad591dbd33187861d41604"


def _tools() -> dict[str, BinaryTool]:
    return read_json(REPO_ROOT / "toolchain.json", Toolchain).binaries


def test_every_tool_the_bootstrap_installs_is_declared() -> None:
    assert set(_tools()) >= {"uv", "gh", "mise"}


def test_mise_is_declared_at_the_version_the_project_requires() -> None:
    """A machine installing a different mise is drift, not convenience."""
    mise = tomllib.loads((REPO_ROOT / "mise.toml").read_text(encoding="utf-8"))
    assert _tools()["mise"].version == mise["min_version"]


@pytest.mark.parametrize("platform", PLATFORMS)
def test_every_tool_has_an_artifact_for_every_machine(platform: str) -> None:
    for name, entry in _tools().items():
        assert platform in entry.artifacts, f"{name} has no {platform} artifact"


def test_every_artifact_carries_a_sha256_and_a_directory() -> None:
    for name, entry in _tools().items():
        for platform, artifact in entry.artifacts.items():
            digest = artifact.sha256
            assert len(digest) == 64, f"{name}/{platform} has no full digest"
            assert artifact.url.startswith("https://"), f"{name}/{platform} url"
            assert artifact.dir, f"{name}/{platform} has no dir"


def test_mise_carries_the_digest_verified_on_the_cluster() -> None:
    assert _tools()["mise"].artifacts["x86_64-linux"].sha256 == MISE_LINUX_DIGEST


def test_every_tool_names_the_binaries_it_provides() -> None:
    for name, entry in _tools().items():
        assert entry.binaries, f"{name} names no binaries"
