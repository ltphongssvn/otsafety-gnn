# tooling/src/otsafety_tooling/policy/exemptions.py
"""Every exemption declared once, with its reason, and checked in both directions.

The pre-commit hook runs main(), the floor; the test suite runs problems(), the
ceiling, in the pre-push hook and CI. A suppression with no register entry
fails, and so does an entry whose suppression is gone.

The detection patterns are assembled from fragments, so this file does not read
as containing the very comments it looks for.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from otsafety_tooling.contracts.exemptions import ExemptionRegister
from otsafety_tooling.contracts.files import read_toml, read_yaml
from otsafety_tooling.contracts.pyproject_config import WorkspacePyproject
from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

REGISTER = Path("context") / "exemptions.yaml"
SCANNED = (".py", ".ts", ".tsx", ".astro", ".mjs")
_NOQA = re.compile("#" + r"\s*noqa:\s*([A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)")
_IGNORE = re.compile("#" + r"\s*type:\s*" + "ignore" + r"(?:\[([a-z-]+(?:\s*,\s*[a-z-]+)*)\])?")
_ESLINT = re.compile("eslint" + "-disable" + r"(?:-next-line|-line)?\b")
_TS = re.compile("@" + "ts-" + r"(ignore|expect-error|nocheck)")


def candidates(root: Path) -> list[str]:
    """Every file a developer has: tracked, plus untracked files git does not ignore.

    Tracked files alone made the scan disagree with the working tree in both
    directions: a new file's suppression was invisible until staged, and a new
    file's register entries read as stale. In CI and at commit every relevant
    file is tracked, so there the two sets are the same.
    """
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=root)
    if listed.returncode != 0:
        raise SystemExit(f"git ls-files failed: {listed.stderr.strip()}")
    return sorted({path for path in listed.stdout.split("\0") if path})


def inline_suppressions(root: Path) -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    for path in candidates(root):
        if not path.endswith(SCANNED) or not (root / path).is_file():
            continue
        for line in (root / path).read_text(encoding="utf-8", errors="replace").splitlines():
            for m in _NOQA.finditer(line):
                found.update((path, rule) for rule in re.split(r"\s*,\s*", m.group(1).strip()))
            for m in _IGNORE.finditer(line):
                found.update(
                    (path, f"type:ignore[{code}]")
                    for code in re.split(r"\s*,\s*", m.group(1) or "all")
                )
            found.update((path, "eslint:disable") for _ in _ESLINT.finditer(line))
            found.update((path, f"ts:{m.group(1)}") for m in _TS.finditer(line))
    return found


def per_file_ignores(root: Path) -> dict[str, tuple[str, ...]]:
    ruff = read_toml(root / "pyproject.toml", WorkspacePyproject).tool.ruff
    return {} if ruff is None or ruff.lint is None else dict(ruff.lint.per_file_ignores)


def problems(root: Path, register: ExemptionRegister) -> list[str]:
    out: list[str] = []
    found = inline_suppressions(root)
    declared = {(i.path, i.rule): i.count for i in register.inline}
    for key, n in sorted(found.items()):
        if key not in declared:
            out.append(f"{key[0]}: {n} x {key[1]} with no register entry")
        elif declared[key] != n:
            out.append(f"{key[0]}: {n} x {key[1]}, but the register says {declared[key]}")
    out += [
        f"{p}: register lists {r}, which the file no longer has"
        for (p, r) in sorted(declared)
        if (p, r) not in found
    ]
    config = {g: tuple(sorted(r)) for g, r in per_file_ignores(root).items()}
    scoped = {s.glob: tuple(sorted(s.rules)) for s in register.scoped}
    out += [
        f"per-file ignore {g} {config.get(g)} differs from the register's {scoped.get(g)}"
        for g in sorted(set(config) | set(scoped))
        if config.get(g) != scoped.get(g)
    ]
    return out


def main() -> int:
    found = problems(REPO_ROOT, read_yaml(REPO_ROOT / REGISTER, ExemptionRegister))
    if found:
        message = f"refusing: every exemption needs its entry in {REGISTER}:\n  " + "\n  ".join(
            found
        )
        print(message, file=sys.stderr)  # noqa: T201 -- this is the command's output
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
