# tooling/src/otsafety_tooling/toolchain_verify.py
"""toolchain:verify -- prove every task runs the pinned binary of each tool.

Pinning a version is not proving which binary runs. Tasks enter the Nix dev shell
through task_config.shell, so today they resolve pinned tools -- but that held by
one line of configuration, and nothing checked it. A global mise shim or a
Homebrew binary can shadow a tool; a task outside the dev shell would never know.

Run as a task, this checks the environment tasks actually use, in every mode.
Each tool must resolve to a /nix/store path named for it and its pinned version,
or to the bootstrap's directory, and must report that version through its probe
-- the probe the flake's build-time check is generated from.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from otsafety_tooling.cli import note, result
from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.toolchain import BinaryTool, Toolchain
from otsafety_tooling.paths import REPO_ROOT

# Where scripts/bootstrap_toolchain.py installs when given no destination: CI,
# FAS OnDemand and Lightning AI, which have no Nix dev shell.
BOOTSTRAP = Path.home() / ".local" / "bin"


def pinned(chain: Toolchain) -> dict[str, BinaryTool]:
    return {
        name: value
        for name in Toolchain.model_fields
        if isinstance(value := getattr(chain, name), BinaryTool)
    }


def problems(
    chain: Toolchain, *, path: str | None = None, bootstrap: Path = BOOTSTRAP
) -> list[str]:
    found: list[str] = []
    for name, tool in pinned(chain).items():
        binary = Path(tool.binaries[0]).name
        where = shutil.which(binary, path=path)
        if where is None:
            found.append(f"{name}: {binary} is not on PATH")
            continue
        located = Path(where)
        in_store = str(located.resolve()).startswith(
            "/nix/store/"
        ) and f"-{name}-{tool.version}/" in str(located.resolve())
        if not (in_store or located.parent == bootstrap):
            found.append(
                f"{name}: {where} is not the pinned {tool.version}; "
                f"it is neither its Nix store path nor {bootstrap}"
            )
            continue
        run = subprocess.run([where, *tool.probe.args], capture_output=True, text=True, check=False)  # noqa: S603
        first = (run.stdout.splitlines() or [""])[0]
        if not re.match(tool.probe.pattern.replace("{version}", re.escape(tool.version)), first):
            found.append(f"{name}: {where} reports {first!r}, not {tool.version}")
    return found


class ToolchainChecked(BaseModel):
    """Which tools were checked, and anything that was not the pinned binary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tools: list[str]
    problems: list[str]


def main() -> int:
    chain = read_json(REPO_ROOT / "toolchain.json", Toolchain)
    found = problems(chain)
    names = sorted(pinned(chain))
    payload = ToolchainChecked(tools=names, problems=found)
    if found:
        for line in found:
            note(line)
        return result(
            "toolchain:verify",
            "refused",
            "tool_not_pinned",
            "; ".join(found),
            payload,
        )
    return result(
        "toolchain:verify",
        "success",
        "tools_pinned",
        f"every task resolves the pinned {len(names)} tools",
        payload,
    )


if __name__ == "__main__":
    raise SystemExit(main())
