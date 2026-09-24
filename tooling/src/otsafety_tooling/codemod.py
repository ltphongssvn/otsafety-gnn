# tooling/src/otsafety_tooling/codemod.py
"""Structural edits to Python source: found in the tree, never by text.

EVERY EDIT FAILURE THIS REPOSITORY HAS SEEN came from matching text. An anchor
stopped matching after the formatter reflowed its line. An import was appended
where isort rejects it, twice. A replacement was written against a function that
had moved. Counting occurrences before replacing catches a miss, but cannot make
a hit correct -- it only proves the text appears once, not that it is the thing
meant.

A transform here states a structural intent and finds its target in the syntax
tree. It applies exactly, or raises CodemodRefusedError naming why; it never returns
source it has half-changed, and every transform re-parses its result before
returning it.
"""

from __future__ import annotations

import ast


class CodemodRefusedError(Exception):
    """A transform could not apply, and says what it was looking for."""


def _verified(source: str, what: str) -> str:
    """Re-parse before returning: unparsable output is worse than a bad anchor."""
    try:
        ast.parse(source)
    except SyntaxError as error:
        raise CodemodRefusedError(f"{what} produced source that does not parse: {error}") from error
    return source


def _import_block(tree: ast.Module) -> tuple[int, int]:
    """The first and last line of the module's leading import block."""
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not imports:
        raise CodemodRefusedError("the module has no import block to add to")
    return imports[0].lineno, max(n.end_lineno or n.lineno for n in imports)


def add_import(source: str, module: str) -> str:
    """Add `import <module>` where isort keeps third-party imports.

    BEFORE THE PROJECT'S OWN IMPORTS, after the standard library and __future__:
    appending to the end of the block is what ruff rejected as unsorted.
    """
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Import) and any(a.name == module for a in node.names):
            return source
    lines = source.splitlines(keepends=True)
    first_project = next(
        (
            n.lineno
            for n in tree.body
            if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("otsafety_tooling")
        ),
        None,
    )
    if first_project is not None:
        lines.insert(first_project - 1, f"import {module}\n\n")
    else:
        _, last = _import_block(tree)
        lines.insert(last, f"\nimport {module}\n")
    return _verified("".join(lines), f"adding import {module}")


def replace_function(source: str, name: str, replacement: str) -> str:
    """Replace a top-level function by NAME, wherever and however it is written."""
    tree = ast.parse(source)
    found = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if not found:
        raise CodemodRefusedError(f"no function named {name} at module level")
    if len(found) > 1:
        raise CodemodRefusedError(f"{len(found)} functions named {name}; the intent is ambiguous")
    node = found[0]
    start = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1
    lines = source.splitlines(keepends=True)
    lines[start : node.end_lineno or node.lineno] = [
        replacement if replacement.endswith("\n") else replacement + "\n"
    ]
    return _verified("".join(lines), f"replacing {name}")


def add_module_marker(source: str, requirement: str) -> str:
    """Claim a requirement for the whole module, after its imports.

    ONE CLAIM PER MODULE: a second pytestmark assignment silently replaces the
    first, so a module that already claims one is refused rather than stacked.
    """
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", "") == "pytestmark" for target in node.targets
        ):
            raise CodemodRefusedError("the module already claims a requirement")
    with_pytest = add_import(source, "pytest")
    tree = ast.parse(with_pytest)
    _, last = _import_block(tree)
    lines = with_pytest.splitlines(keepends=True)
    lines.insert(last, f'\npytestmark = pytest.mark.requirement("{requirement}")\n')
    return _verified("".join(lines), f"claiming {requirement}")
