# tooling/src/otsafety_tooling/policy/inventory.py
"""Read every command out of the tree, and how it reports its outcome.

WHY THE SYNTAX TREE AND NOT A SEARCH. A first inventory matched strings and gave
three false negatives: the emitter is imported as `result`, as `emit_result` and,
in the scripts that run before anything is installed, defined locally as `emit`.
A gate fooled the same way would pass by omission, which is worse than no gate.
A module emits if it CALLS a name that resolves to the emitter.
"""

from __future__ import annotations

import ast
from pathlib import Path

from otsafety_tooling.contracts.inventory import Command, CommandInventory
from otsafety_tooling.paths import REPO_ROOT

ROOTS = ("tooling/src", "scripts")
EMITTER = "otsafety_tooling.cli"
# What a declared exception must say, at the line where it applies.
DECLARATIONS = {
    "A VALUE, NOT AN ENVELOPE": "its stdout is a value a shell substitutes",
    "NO ENVELOPE OF ITS OWN": "it wraps a task whose envelope is already stdout",
}


def _emitter_names(tree: ast.Module) -> set[str]:
    """Every local name that reaches the emitter: imported, aliased, or defined."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == EMITTER:
            names |= {alias.asname or alias.name for alias in node.names if alias.name == "result"}
        # The scripts define their own emit(): they run where the contracts cannot.
        if isinstance(node, ast.FunctionDef) and node.name == "emit":
            names.add("emit")
    return names


def _declared(text: str) -> str | None:
    for marker, reason in DECLARATIONS.items():
        if marker in text:
            return reason
    return None


def build(root: Path = REPO_ROOT) -> CommandInventory:
    """Every module with a main(), and whether it emits an envelope."""
    commands: list[Command] = []
    for where in ROOTS:
        for path in sorted((root / where).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            if not any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body):
                continue
            names = _emitter_names(tree)
            emits = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names
                for n in ast.walk(tree)
            )
            commands.append(
                Command(
                    module=str(path.relative_to(root)),
                    emits=emits,
                    exempt_because=None if emits else _declared(text),
                )
            )
    return CommandInventory(commands=tuple(commands))


def main(argv: list[str] | None = None) -> int:
    """Write the inventory for the policy to read; the destination may be named.

    NAMED, NOT GUESSED: the policy probe writes it into its own world, as the
    matrix does. A caller that had to find the file made the test depend on where
    this command chose to put it.
    """
    import sys

    from otsafety_tooling.artifacts import artifacts_root
    from otsafety_tooling.cli import result

    args = sys.argv[1:] if argv is None else argv
    inventory = build()
    out = Path(args[0]) if args else artifacts_root(REPO_ROOT) / "policy" / "command-inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(inventory.model_dump_json(indent=2) + "\n", encoding="utf-8")
    silent = [c.module for c in inventory.commands if not c.emits and not c.exempt_because]
    return result(
        "policy:inventory",
        "refused" if silent else "success",
        "command_silent" if silent else "commands_report",
        f"{len(inventory.commands)} commands, {len(silent)} silent",
        inventory,
    )


if __name__ == "__main__":
    raise SystemExit(main())
