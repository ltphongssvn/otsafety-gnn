# tooling/src/otsafety_tooling/policy/annotations.py
"""Implicit Any: the forms mypy's ban does not see (G.46).

disallow_any_explicit CATCHES THE WORD Any AND NOTHING ELSE. Two shapes mean the
same thing and pass it:

    Callable[..., int]    the parameters are elided, so any call type-checks
    def f(x: dict)        the members are elided, so any contents type-check

Both are Any wearing a different name, and one of them hid in this repository
until a type error happened to expose it -- the seams in two contract tests, where
a stand-in could have been handed anything and nothing would have said so.

WHY A SCAN AND NOT A LINT RULE. ruff's ANN401 checks a function ARGUMENT annotated
Any, which is the explicit form in one position; nothing in the toolchain reads
these two. The scan is the gate, and it runs where the other policy inputs do.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOTS = ("tooling/src", "tooling/tests", "scripts", "apps/site/tests")
BARE = {"dict", "list", "set", "tuple", "frozenset"}


def _elides_parameters(node: ast.expr) -> bool:
    """Callable[..., X]: the ellipsis stands for any parameter list at all."""
    if not isinstance(node, ast.Subscript):
        return False
    named = node.value
    name = named.attr if isinstance(named, ast.Attribute) else getattr(named, "id", "")
    if name != "Callable" or not isinstance(node.slice, ast.Tuple):
        return False
    return any(
        isinstance(element, ast.Constant) and element.value is Ellipsis
        for element in node.slice.elts
    )


def _bare_container(node: ast.expr) -> bool:
    """dict, list, set: the members are elided, so anything satisfies them."""
    return isinstance(node, ast.Name) and node.id in BARE


def implicit_any(root: Path) -> list[str]:
    """Every annotation that elides a type it could name, as `path:line  form`."""
    offenders: list[str] = []
    for where in ROOTS:
        for path in sorted((root / where).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                annotations: list[ast.expr] = []
                if isinstance(node, ast.AnnAssign):
                    annotations.append(node.annotation)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    annotations += [
                        argument.annotation
                        for argument in (*node.args.args, *node.args.kwonlyargs)
                        if argument.annotation is not None
                    ]
                    if node.returns is not None:
                        annotations.append(node.returns)
                for annotation in annotations:
                    where_at = f"{path.relative_to(root)}:{annotation.lineno}"
                    if _elides_parameters(annotation):
                        offenders.append(f"{where_at}  Callable[..., X] elides its parameters")
                    elif _bare_container(annotation):
                        offenders.append(f"{where_at}  a bare container elides its members")
    return offenders
