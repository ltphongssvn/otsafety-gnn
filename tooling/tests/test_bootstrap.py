# tooling/tests/test_bootstrap.py
"""The bootstrap installs the declared toolchain, or refuses and installs nothing.

WHY IT CANNOT BE A TASK. It runs before uv, mise or the virtual environment
exist, so scripts/bootstrap_toolchain.py imports nothing but the standard
library and is loaded here by path. Everything it decides is pure: which
artifact this platform needs, whether a tool is already correct, and whether a
downloaded file may be installed.

WHAT TODAY PROVED. Two hand-typed installs on FAS OnDemand were saved by a
checksum gate: a placeholder digest refused gh, and a misread checksums file
refused mise. Both refusals installed nothing, which is the behaviour these
tests fix in place.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from otsafety_tooling.paths import REPO_ROOT


def _load_bootstrap() -> Any:
    """Load the standalone script by path; it is not an installed module."""
    location = REPO_ROOT / "scripts" / "bootstrap_toolchain.py"
    spec = importlib.util.spec_from_file_location("bootstrap_toolchain", location)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bootstrap_toolchain"] = module
    spec.loader.exec_module(module)
    return module


bootstrap = _load_bootstrap()

TOOLCHAIN: dict[str, Any] = {
    "uv": {
        "version": "0.12.7",
        "artifacts": {
            "x86_64-linux": {"url": "https://example.invalid/uv.tar.gz", "sha256": "a" * 64},
            "aarch64-darwin": {"url": "https://example.invalid/uv-mac.tar.gz", "sha256": "b" * 64},
        },
        "binaries": ["uv"],
    }
}


def test_this_platform_is_recognised() -> None:
    key = bootstrap.platform_key("Linux", "x86_64")
    assert key == "x86_64-linux"
    assert bootstrap.platform_key("Darwin", "arm64") == "aarch64-darwin"


def test_an_unsupported_platform_is_refused_by_name() -> None:
    with pytest.raises(SystemExit, match="Windows"):
        bootstrap.platform_key("Windows", "AMD64")


def test_an_already_correct_tool_is_skipped(tmp_path: Path) -> None:
    """FAS OnDemand ships uv 0.12.7 system-wide; the bootstrap must not fight it."""
    plan = bootstrap.plan_tool("uv", TOOLCHAIN["uv"], "x86_64-linux", installed="0.12.7")
    assert plan.action == "skip"
    assert "0.12.7" in plan.reason


def test_a_missing_tool_is_installed() -> None:
    plan = bootstrap.plan_tool("uv", TOOLCHAIN["uv"], "x86_64-linux", installed=None)
    assert plan.action == "install"


def test_a_wrong_version_is_replaced() -> None:
    plan = bootstrap.plan_tool("uv", TOOLCHAIN["uv"], "x86_64-linux", installed="0.10.2")
    assert plan.action == "install"
    assert "0.10.2" in plan.reason


def test_a_tool_without_an_artifact_for_this_platform_is_refused() -> None:
    entry = {"version": "1.0", "artifacts": {"aarch64-darwin": {}}, "binaries": ["x"]}
    with pytest.raises(SystemExit, match="x86_64-linux"):
        bootstrap.plan_tool("thing", entry, "x86_64-linux", installed=None)


def test_a_plan_is_made_for_every_declared_tool() -> None:
    plans = bootstrap.plan_all(TOOLCHAIN, "x86_64-linux", installed={"uv": None})
    assert [plan.tool for plan in plans] == ["uv"]


def test_a_matching_digest_is_accepted(tmp_path: Path) -> None:
    payload = tmp_path / "artifact"
    payload.write_bytes(b"hello")
    digest = bootstrap.digest_of(payload)
    bootstrap.verify(payload, digest)


def test_a_mismatched_digest_refuses_and_says_both(tmp_path: Path) -> None:
    payload = tmp_path / "artifact"
    payload.write_bytes(b"hello")
    with pytest.raises(SystemExit) as refusal:
        bootstrap.verify(payload, "c" * 64)
    message = str(refusal.value)
    assert bootstrap.digest_of(payload) in message
    assert "c" * 64 in message


def test_the_version_a_tool_reports_is_read_from_its_output() -> None:
    """gh prints `gh version 2.101.0 (2026-09-15)`; uv prints `uv 0.12.7 (...)`."""
    assert bootstrap.parse_version("gh version 2.101.0 (2026-09-15)") == "2.101.0"
    assert bootstrap.parse_version("uv 0.12.7 (x86_64-unknown-linux-gnu)") == "0.12.7"
    assert bootstrap.parse_version("2026.9.9 linux-x64 (2026-09-15)") == "2026.9.9"


def test_output_without_a_version_reads_as_unknown() -> None:
    assert bootstrap.parse_version("command not found") is None
