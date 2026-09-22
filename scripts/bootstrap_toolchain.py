#!/usr/bin/env python3
# scripts/bootstrap_toolchain.py
"""Install the toolchain.json executables on a machine that has nothing yet.

RUNS BEFORE EVERYTHING. uv, mise and the virtual environment do not exist when
this runs, so it imports only the standard library and is not part of the
otsafety_tooling package. `scripts/bootstrap.sh` calls it with the system python3.

WHAT IT REPLACES. The FAS OnDemand session that proved this project runs there
installed gh and mise by hand, one typed command at a time. That is exactly
the knowledge this file exists to hold: the same steps, declared once, checked
by tests, and repeatable on Lightning AI or a teammate's machine.

DECIDE, THEN ACT. Every tool gets a plan first -- skip, install, or refuse --
so what will happen is printable before anything is downloaded.

A DIGEST MISMATCH INSTALLS NOTHING, and says both values. Two hand-typed
installs were saved by exactly that gate on the day this was written: a
placeholder digest refused gh, and a misread checksums file refused mise.

ALREADY-CORRECT TOOLS ARE LEFT ALONE. FAS OnDemand ships uv 0.12.7 system-wide,
which is the pinned version; installing a second copy would create the drift
this project removes.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BLOCK_BYTES = 64 * 1024
VERSION = re.compile(r"(\d+\.\d+(?:\.\d+)?)")

SUPPORTED = {
    ("Linux", "x86_64"): "x86_64-linux",
    ("Darwin", "arm64"): "aarch64-darwin",
    ("Darwin", "aarch64"): "aarch64-darwin",
}


@dataclass(frozen=True)
class Plan:
    """What the bootstrap intends to do about one tool, and why."""

    tool: str
    action: str
    reason: str
    url: str = ""
    sha256: str = ""


def platform_key(system: str, machine: str) -> str:
    """The toolchain.json artifact key for this platform, or refuse by name."""
    key = SUPPORTED.get((system, machine))
    if key is None:
        raise SystemExit(f"unsupported platform: {system} {machine}")
    return key


def installed_version(destination: Path, entry: dict[str, Any]) -> str | None:
    """The pinned version, if the binary AT THE DESTINATION reports it through its probe.

    NEVER WHAT IS ON PATH. A runner shipped gh 2.101.0 in /usr/bin, so the bootstrap
    logged "gh: skip (2.101.0 already installed)", never placed the verified artifact,
    and toolchain:verify found the runner's binary. A binary from an unverified source
    that reports the right version is not the pinned binary. The probe is the one
    toolchain.json declares, which the flake and toolchain:verify also read.
    """
    executable = destination / Path(entry["binaries"][0]).name
    if not executable.is_file():
        return None
    probe = entry["probe"]
    try:
        result = subprocess.run(
            [str(executable), *probe["args"]],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError:
        return None
    first = (result.stdout.splitlines() or [""])[0]
    pattern = probe["pattern"].replace("{version}", re.escape(entry["version"]))
    return entry["version"] if re.match(pattern, first) else None


def plan_tool(name: str, entry: dict[str, Any], key: str, installed: str | None) -> Plan:
    """Skip, install, or refuse, for one declared tool."""
    wanted = entry["version"]
    artifact = entry["artifacts"].get(key)
    if artifact is None:
        raise SystemExit(f"{name} declares no artifact for {key}")

    if installed == wanted:
        return Plan(tool=name, action="skip", reason=f"{wanted} already installed")

    found = installed or "absent"
    return Plan(
        tool=name,
        action="install",
        reason=f"{found} found, {wanted} required",
        url=artifact["url"],
        sha256=artifact["sha256"],
    )


def plan_all(toolchain: dict[str, Any], key: str, installed: dict[str, str | None]) -> list[Plan]:
    """A plan for every declared tool, in declaration order."""
    return [
        plan_tool(name, entry, key, installed.get(name))
        for name, entry in toolchain.items()
        if isinstance(entry, dict) and "artifacts" in entry
    ]


def digest_of(path: Path) -> str:
    """The SHA-256 of a file, read in blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(BLOCK_BYTES):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    """Refuse unless the bytes match the declared digest, showing both."""
    observed = digest_of(path)
    if observed != expected:
        raise SystemExit(
            f"REFUSED: {path.name} does not match its declared digest\n"
            f"  expected {expected}\n"
            f"  observed {observed}\n"
            "nothing was installed"
        )


def _extract(archive: Path, into: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(into)
        return
    with tarfile.open(archive) as bundle:
        bundle.extractall(into, filter="data")


def write_pin_notice(tool: str, entry: dict[str, Any], destination: Path) -> list[Path]:
    """A pin notice beside the install prefix, where the tool reads one.

    mise reads it relative to its own binary; its self-update then refuses and names
    toolchain.json. Written for every artifact kind: a bare binary once returned early
    and would have skipped it.
    """
    notice = entry.get("self_update_notice")
    if not notice:
        return []
    written = destination.parent / notice
    written.parent.mkdir(parents=True, exist_ok=True)
    message = f"{tool} is pinned by toolchain.json in this repository; change its version there."
    written.write_text(f'message = "{message}"\n')
    return [written]


def install(plan: Plan, entry: dict[str, Any], key: str, destination: Path) -> list[Path]:
    """Download, verify, extract, and place every declared binary."""
    artifact = entry["artifacts"][key]
    installed: list[Path] = []
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        workspace = Path(work)
        archive = workspace / Path(plan.url).name
        urllib.request.urlretrieve(plan.url, archive)
        verify(archive, plan.sha256)
        if artifact.get("kind") == "binary":
            # A BARE BINARY: verified by its digest, then placed as it is.
            target = destination / entry["binaries"][0]
            shutil.copy2(archive, target)
            target.chmod(0o755)
            return [target, *write_pin_notice(plan.tool, entry, destination)]
        _extract(archive, workspace)

        root = workspace / artifact["dir"] if artifact.get("dir") else workspace
        for relative in entry["binaries"]:
            source = root / relative
            if not source.is_file():
                raise SystemExit(f"{plan.tool}: {relative} is missing from the archive")
            target = destination / Path(relative).name
            shutil.copy2(source, target)
            target.chmod(0o755)
            installed.append(target)
        installed.extend(write_pin_notice(plan.tool, entry, destination))
    return installed


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path(__file__).resolve().parent.parent
    destination = Path(args[0]) if args else Path.home() / ".local" / "bin"

    # EXEMPT FROM THE SCHEMA-FIRST BAN, AND ONLY HERE. This installs the toolchain
    # on a machine with nothing, under the system python3 -- Pydantic cannot exist
    # yet. The file is not unchecked: test_config_contracts.py validates it against
    # the Toolchain model in the gate, before any bootstrap reads it.
    toolchain = json.loads((repo_root / "toolchain.json").read_text(encoding="utf-8"))  # noqa: TID251
    key = platform_key(platform.system(), platform.machine())
    print(f"platform: {key}")
    print(f"destination: {destination}")

    names = [n for n, e in toolchain.items() if isinstance(e, dict) and "artifacts" in e]
    installed = {name: installed_version(destination, toolchain[name]) for name in names}
    plans = plan_all(toolchain, key, installed)

    for plan in plans:
        print(f"  {plan.tool}: {plan.action} ({plan.reason})")

    for plan in plans:
        if plan.action != "install":
            continue
        placed = install(plan, toolchain[plan.tool], key, destination)
        for path in placed:
            print(f"installed {path.name} -> {path}")

    print("bootstrap complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
