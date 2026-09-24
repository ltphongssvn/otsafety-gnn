# tooling/src/otsafety_tooling/policy/inputs.py
"""Generate every generated input, and name the whole set for the policy to read.

ONE MANIFEST, THREE CONSUMERS: the policy task passes what this prints, the probe
builds its world from the same file, and the Rego derives its required set from
the manifest, which is itself an input. A set declared in three places drifts on
the first addition -- it did, the day the command inventory arrived.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from otsafety_tooling.artifacts import artifacts_root
from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.policy_inputs import PolicyInputs
from otsafety_tooling.paths import REPO_ROOT

MANIFEST = Path("contracts") / "policy-inputs.json"


def manifest(root: Path = REPO_ROOT) -> PolicyInputs:
    """The declared input set, through its contract."""
    return read_json(root / MANIFEST, PolicyInputs)


def paths(root: Path = REPO_ROOT, evidence: Path | None = None) -> list[str]:
    """Every input as the policy will read it: generated ones under the evidence root."""
    where = evidence or artifacts_root(root)
    return [
        str(where / entry.path) if entry.generated else entry.path
        for entry in manifest(root).inputs
    ]


def generate(root: Path = REPO_ROOT, evidence: Path | None = None) -> list[str]:
    """Run each generated input's command, writing it where the policy expects it."""
    where = evidence or artifacts_root(root)
    written: list[str] = []
    for entry in manifest(root).inputs:
        if not entry.generated:
            continue
        target = where / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603
            [*entry.generated.split(), str(target)],
            cwd=root,
            check=True,
            capture_output=True,
        )
        written.append(str(target))
    return written


def main(argv: list[str] | None = None) -> int:
    """`--paths` prints the input list a shell passes to conftest; otherwise generate."""
    from otsafety_tooling.cli import note, result

    args = sys.argv[1:] if argv is None else argv
    if args == ["--paths"]:
        # A VALUE, NOT AN ENVELOPE: the policy task substitutes this into conftest's
        # arguments, so the paths are the whole of stdout.
        sys.stdout.write("\n".join(paths()) + "\n")
        return 0
    written = generate()
    for path in written:
        note(f"wrote {path}")
    return result(
        "policy:inputs",
        "success",
        "inputs_written",
        f"{len(written)} generated inputs written",
        manifest(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
