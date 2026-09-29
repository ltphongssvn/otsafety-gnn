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

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Protocol

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.34")


class _Plan(Protocol):
    """The plan bootstrap_toolchain makes for one tool."""

    @property
    def tool(self) -> str: ...

    @property
    def action(self) -> str: ...

    @property
    def reason(self) -> str: ...

    @property
    def url(self) -> str: ...

    @property
    def sha256(self) -> str: ...


class _Bootstrap(Protocol):
    """What these tests call on the script they load by path."""

    def platform_key(self, system: str, machine: str) -> str: ...

    def digest_of(self, path: Path) -> str: ...

    def installed_version(self, destination: Path, entry: object) -> str | None: ...

    def plan_tool(self, name: str, entry: object, key: str, installed: str | None) -> _Plan: ...

    def plan_all(
        self, toolchain: object, key: str, installed: dict[str, str | None]
    ) -> list[_Plan]: ...

    def install(self, plan: _Plan, entry: object, key: str, destination: Path) -> list[Path]: ...

    def verify(self, path: Path, expected: str) -> None: ...


def _load_bootstrap() -> _Bootstrap:
    """Load the standalone script by path; it is not an installed module."""
    location = REPO_ROOT / "scripts" / "bootstrap_toolchain.py"
    spec = importlib.util.spec_from_file_location("bootstrap_toolchain", location)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bootstrap_toolchain"] = module
    spec.loader.exec_module(module)
    loaded: _Bootstrap = module
    return loaded


bootstrap = _load_bootstrap()

TOOLCHAIN: dict[str, object] = {
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


GH = {
    "version": "2.101.0",
    "binaries": ["bin/gh"],
    "probe": {"args": ["--version"], "pattern": "^gh version {version} "},
}


def _fake(directory: Path, output: str, code: int = 0) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "gh").write_text(f"#!/bin/sh\necho '{output}'\nexit {code}\n", encoding="utf-8")
    (directory / "gh").chmod(0o755)


def test_an_ambient_binary_at_the_pinned_version_never_counts(tmp_path: Path) -> None:
    """The CI failure: a runner's own gh reported 2.101.0, and the pinned one was skipped."""
    _fake(tmp_path / "usr-bin", "gh version 2.101.0 (2026-09-15)")
    assert bootstrap.installed_version(tmp_path / "destination", GH) is None


def test_the_binary_at_the_destination_counts_when_it_reports_the_pinned_version(
    tmp_path: Path,
) -> None:
    _fake(tmp_path, "gh version 2.101.0 (2026-09-15)")
    assert bootstrap.installed_version(tmp_path, GH) == "2.101.0"


def test_the_binary_at_the_destination_is_replaced_at_another_version(tmp_path: Path) -> None:
    _fake(tmp_path, "gh version 2.100.0 (2026-08-01)")
    assert bootstrap.installed_version(tmp_path, GH) is None


def test_a_broken_binary_at_the_destination_is_replaced(tmp_path: Path) -> None:
    _fake(tmp_path, "command not found", code=127)
    assert bootstrap.installed_version(tmp_path, GH) is None


def test_the_bootstrap_writes_mises_pin_notice_beside_its_prefix(tmp_path: Path) -> None:
    """Without it, a standalone mise in ~/.local/bin self-updates over the pinned version."""
    import hashlib

    payload = tmp_path / "published"
    payload.write_bytes(b"#!/bin/sh\necho 2026.9.9\n")
    entry = {
        "version": "2026.9.9",
        "binaries": ["mise"],
        "self_update_notice": "lib/mise/mise-self-update-instructions.toml",
        "artifacts": {
            "x86_64-linux": {
                "url": payload.as_uri(),
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                "kind": "binary",
            }
        },
    }
    plan = bootstrap.plan_tool("mise", entry, "x86_64-linux", None)
    bootstrap.install(plan, entry, "x86_64-linux", tmp_path / "local" / "bin")
    written = (
        tmp_path / "local" / "lib" / "mise" / "mise-self-update-instructions.toml"
    ).read_text()
    assert written.startswith("message = ") and "toolchain.json" in written


def test_the_interpreter_floor_is_checked_before_it_is_needed() -> None:
    """A bootstrap refuses an old interpreter; it does not die inside an import.

    typing.Required arrived in 3.11 and this script exists to run under whatever
    python3 a bare machine has -- 3.9.6 on the laptop that found this. An
    ImportError from within the import block names a symbol rather than the
    reason, and byte-compiling the tree would not catch it because compilation
    does not resolve imports.

    SO THE CHECK COMES FIRST, textually. Everything the floor protects is
    imported after it, which is the only ordering that works when the failure
    mode is the import itself.
    """
    source = (REPO_ROOT / "scripts" / "bootstrap_toolchain.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    guard = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.If) and "version_info" in ast.unparse(node.test)
        ),
        None,
    )
    assert guard is not None, "the bootstrap declares no interpreter floor"

    needs_new = [
        node.lineno
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "typing"
        and any(alias.name in {"Required", "LiteralString", "Self"} for alias in node.names)
    ]
    assert needs_new, "nothing here needs the floor; the guard would be decoration"
    assert guard.lineno < min(needs_new), (
        f"the floor is checked at line {guard.lineno}, after the import at {min(needs_new)}"
    )


def test_an_old_interpreter_is_refused_by_name() -> None:
    """THE REFUSAL, exercised -- and hermetic, so the gate that merges sees it.

    THE FIRST VERSION WENT LOOKING FOR AN OLD INTERPRETER on this host. That
    test passes on a laptop with Command Line Tools and skips in a Nix sandbox
    and on every runner, which is the shape 2026 practice names outright: keyed
    to the host, it runs where nothing gates and is silent where everything
    does.

    SO THE CONDITION IS CONSTRUCTED, NOT FOUND. The interpreter is the one Nix
    provides; only its reported version is replaced, before the script's body
    runs. Same answer on a laptop, a runner and a sandbox.
    """
    import subprocess
    import sys

    script = REPO_ROOT / "scripts" / "bootstrap_toolchain.py"
    harness = (
        "import sys, collections;"
        "V = collections.namedtuple('v', 'major minor micro releaselevel serial');"
        "sys.version_info = V(3, 9, 6, 'final', 0);"
        f"exec(compile(open({str(script)!r}).read(), {str(script)!r}, 'exec'))"
    )
    refused = subprocess.run(
        [sys.executable, "-c", harness], capture_output=True, text=True, check=False
    )
    assert refused.returncode == 2, (
        f"exit {refused.returncode}, not a refusal: {refused.stderr[-300:]}"
    )
    assert "3.9.6" in refused.stderr, "the refusal does not name the version it found"
    assert "nothing was installed" in refused.stderr
