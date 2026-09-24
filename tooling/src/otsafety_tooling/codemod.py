# tooling/src/otsafety_tooling/codemod.py
"""Structural edits to Python source: found in the tree, never by text.

EVERY EDIT FAILURE THIS REPOSITORY HAS SEEN came from matching text. An anchor
stopped matching after the formatter reflowed its line. An import was appended
where isort rejects it. A replacement was written against a function that had
moved. Counting occurrences before replacing catches a miss but cannot make a hit
correct: it proves the text appears once, not that it is the thing meant.

A CONCRETE SYNTAX TREE, NOT ast. Python's ast is lossy by design -- its own
documentation says the original source cannot be reprinted from it -- so the first
version of this module parsed with ast and then SLICED LINES BY NUMBER. That
inherits every weakness it set out to remove: a replacement that omitted a
decorator dropped it silently, turning a pytest fixture into a plain function and
erroring seven tests at setup. LibCST keeps comments, whitespace and structure, so
a function is replaced AS A NODE and its decorators come with it.

A transform applies exactly, or raises CodemodRefusedError naming what it looked
for. A module it does not change is returned byte for byte.
"""

from __future__ import annotations

import libcst as cst
import libcst.matchers as m


class CodemodRefusedError(Exception):
    """A transform could not apply, and says what it was looking for."""


class _ReplaceFunction(cst.CSTTransformer):
    """Swap one top-level function for another, decorators and all."""

    def __init__(self, name: str, replacement: cst.FunctionDef) -> None:
        self.name = name
        self.replacement = replacement
        self.found = 0

    def leave_FunctionDef(  # noqa: N802
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.BaseStatement:
        if original_node.name.value != self.name:
            return updated_node
        self.found += 1
        return updated_node.with_changes(
            params=self.replacement.params,
            body=self.replacement.body,
            returns=self.replacement.returns,
            asynchronous=self.replacement.asynchronous,
            decorators=self.replacement.decorators or updated_node.decorators,
        )


def replace_function(source: str, name: str, replacement: str) -> str:
    """Replace a function by NAME, wherever and however it is written."""
    try:
        parsed = cst.parse_statement(replacement)
    except cst.ParserSyntaxError as error:
        raise CodemodRefusedError(f"the replacement for {name} does not parse: {error}") from error
    if not isinstance(parsed, cst.FunctionDef):
        raise CodemodRefusedError(f"the replacement for {name} is not a function definition")
    transformer = _ReplaceFunction(name, parsed)
    changed = cst.parse_module(source).visit(transformer)
    if transformer.found == 0:
        raise CodemodRefusedError(f"no function named {name} at module level")
    if transformer.found > 1:
        raise CodemodRefusedError(
            f"{transformer.found} functions named {name}; the intent is ambiguous"
        )
    if changed.code == source:
        raise CodemodRefusedError(
            f"replacing {name} left the source identical; the replacement says nothing new"
        )
    return changed.code


def has_import(source: str, module_name: str) -> bool:
    """Whether the module imports `module_name`, asked of the tree.

    NOT A SUBSTRING CHECK. A driver script asked whether "from pathlib import Path"
    appeared in the text, found the phrase INSIDE A DOCSTRING, and skipped adding
    the import -- the file then failed with NameError. Text cannot tell code from
    prose about code; matchers can.
    """
    found = m.findall(cst.parse_module(source), m.Import() | m.ImportFrom())
    for node in found:
        if m.matches(
            node,
            m.Import(
                names=[m.ZeroOrMore(), m.ImportAlias(name=m.Name(module_name)), m.ZeroOrMore()]
            ),
        ):
            return True
        if m.matches(node, m.ImportFrom(module=m.Name(module_name))):
            return True
    return False


def add_import(source: str, module_name: str) -> str:
    """Add `import <module>` where isort keeps third-party imports.

    BEFORE THIS PROJECT'S OWN IMPORTS, after the standard library: appending to the
    end of the block is what ruff rejected as unsorted, twice.
    """
    module = cst.parse_module(source)
    if has_import(source, module_name):
        return module.code
    statement = cst.parse_statement(f"import {module_name}\n")
    body = list(module.body)
    at = len(body)
    for index, item in enumerate(body):
        if not isinstance(item, cst.SimpleStatementLine):
            continue
        for small in item.body:
            if isinstance(small, cst.ImportFrom) and small.module is not None:
                dotted = cst.Module(body=()).code_for_node(small.module)
                if dotted.startswith("otsafety_tooling"):
                    at = min(at, index)
        if isinstance(item.body[0], (cst.Import, cst.ImportFrom)):
            at = min(at, len(body)) if at != len(body) else at
    if at == len(body):
        last = max(
            (
                index
                for index, item in enumerate(body)
                if isinstance(item, cst.SimpleStatementLine)
                and isinstance(item.body[0], (cst.Import, cst.ImportFrom))
            ),
            default=None,
        )
        if last is None:
            raise CodemodRefusedError("the module has no import block to add to")
        at = last + 1
    body.insert(at, statement.with_changes(leading_lines=[cst.EmptyLine()]))
    return module.with_changes(body=body).code


def add_module_marker(source: str, requirement: str) -> str:
    """Claim a requirement for the whole module, after its imports.

    ONE CLAIM PER MODULE: a second pytestmark assignment silently replaces the
    first, so a module that already claims one is refused rather than stacked.
    """
    module = cst.parse_module(source)
    for statement in module.body:
        if isinstance(statement, cst.SimpleStatementLine):
            for small in statement.body:
                if isinstance(small, cst.Assign) and any(
                    isinstance(target.target, cst.Name) and target.target.value == "pytestmark"
                    for target in small.targets
                ):
                    raise CodemodRefusedError("the module already claims a requirement")
    with_pytest = cst.parse_module(add_import(source, "pytest"))
    body = list(with_pytest.body)
    last = max(
        (
            index
            for index, item in enumerate(body)
            if isinstance(item, cst.SimpleStatementLine)
            and isinstance(item.body[0], (cst.Import, cst.ImportFrom))
        ),
        default=None,
    )
    if last is None:
        raise CodemodRefusedError("the module has no import block to add to")
    claim = cst.parse_statement(f'pytestmark = pytest.mark.requirement("{requirement}")\n')
    body.insert(last + 1, claim.with_changes(leading_lines=[cst.EmptyLine()]))
    return with_pytest.with_changes(body=body).code
