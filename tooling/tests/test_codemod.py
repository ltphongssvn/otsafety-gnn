# tooling/tests/test_codemod.py
"""Source edits go through the syntax tree, not string anchors (G.43).

WHY. Every edit failure this repository has seen came from matching text: an
anchor that stopped matching after the formatter reflowed the line, an import
appended where isort rejects it, a replacement applied to a function that had
moved. The guard against it was counting occurrences before replacing, which
catches a miss but cannot make a hit correct.

A transform here states a structural intent -- add this import, replace this
function, add this decorator -- and is applied by rewriting the tree. It either
applies or refuses with the reason; it never half-applies.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.codemod import (
    CodemodRefusedError,
    add_import,
    add_module_marker,
    has_import,
    replace_function,
)

pytestmark = pytest.mark.requirement("G.43")


def test_an_import_lands_where_isort_puts_it() -> None:
    """THE FAILURE THIS PREVENTS, twice this session: pytest appended after the
    project imports, which ruff's isort rules reject as an unsorted block."""
    before = (
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "from otsafety_tooling.paths import REPO_ROOT\n"
    )
    lines = [line for line in add_import(before, "pytest").splitlines() if line.strip()]
    project = lines.index("from otsafety_tooling.paths import REPO_ROOT")
    assert lines.index("from pathlib import Path") < lines.index("import pytest") < project


def test_adding_an_import_twice_changes_nothing() -> None:
    before = "import pytest\n\nX = 1\n"
    assert add_import(before, "pytest") == before


def test_a_function_is_replaced_wherever_it_sits() -> None:
    """No anchor: the function is found by name, however it was formatted."""
    before = "def a() -> int:\n    return 1\n\n\ndef b() -> int:\n    return 2\n"
    after = replace_function(before, "b", "def b() -> int:\n    return 22\n")
    assert "return 22" in after and "return 1" in after
    assert after.count("def b(") == 1


def test_replacing_a_function_that_is_not_there_refuses() -> None:
    with pytest.raises(CodemodRefusedError, match="no function named"):
        replace_function("x = 1\n", "missing", "def missing() -> None:\n    pass\n")


def test_a_marker_is_added_after_the_imports() -> None:
    before = "import pytest\n\n\ndef test_x() -> None:\n    pass\n"
    after = add_module_marker(before, "G.43")
    assert 'pytestmark = pytest.mark.requirement("G.43")' in after
    assert after.index("pytestmark") < after.index("def test_x")


def test_a_second_marker_refuses_rather_than_stacking() -> None:
    before = 'import pytest\n\npytestmark = pytest.mark.requirement("G.1")\n'
    with pytest.raises(CodemodRefusedError, match="already claims"):
        add_module_marker(before, "G.43")


def test_every_transform_returns_parseable_source() -> None:
    """A transform that produced unparsable source would be worse than a bad anchor."""
    import ast as syntax

    before = "from pathlib import Path\n\n\ndef f() -> None:\n    pass\n"
    syntax.parse(add_import(before, "pytest"))
    syntax.parse(replace_function(before, "f", "def f() -> int:\n    return 0\n"))


def test_a_replacement_keeps_the_decorators_and_the_comments() -> None:
    """WHY A CONCRETE SYNTAX TREE. ast is lossy by design -- its own documentation
    says the original source cannot be reprinted from it -- so this module replaced
    functions by slicing lines, and a replacement without the decorator dropped it
    silently: a pytest fixture became a plain function and seven tests errored at
    setup. A CST replaces the node, and a decorator is part of that node.
    """
    before = (
        "# a comment ast discards\n"
        "import pytest\n"
        "\n\n"
        "@pytest.fixture\n"
        "def handed() -> int:\n"
        "    return 1  # trailing\n"
    )
    after = replace_function(before, "handed", "def handed() -> int:\n    return 2\n")
    assert "@pytest.fixture" in after, "the decorator is part of the function it decorates"
    assert "# a comment ast discards" in after, "comments elsewhere are untouched"
    assert "return 2" in after and "return 1" not in after


def test_an_unchanged_module_is_returned_byte_for_byte() -> None:
    """A transform that rewrote formatting it was not asked to change would make
    every edit a review burden, and the formatter would fight it. ast cannot give
    this: reprinting from it loses comments, blank lines and quote style."""
    before = (
        "# tooling/tests/sample.py\n"
        '"""A docstring with \'mixed\' quotes."""\n'
        "\n"
        "import pytest\n"
        "\n\n"
        "@pytest.fixture  # a trailing comment\n"
        "def thing() -> int:\n"
        "    return 1\n"
    )
    assert add_import(before, "pytest") == before


def test_a_docstring_that_mentions_an_import_is_not_one() -> None:
    """THE FAILURE THIS ENDS: a driver script checked whether the text contained
    "from pathlib import Path", matched the phrase inside a docstring, and skipped
    the import it was asked to add. The file then failed with NameError."""
    prose = '"""This module needs `import pytest` to run."""\n\nimport sys\n'
    assert not has_import(prose, "pytest")
    assert "import pytest" in add_import(prose, "pytest")


def test_a_replacement_may_add_a_decorator() -> None:
    """THE MIRROR OF THE FIRST BUG. Replacing the node wholesale dropped the
    decorators it already had; keeping them wholesale meant a replacement could not
    ADD one, and the transform reported success while changing nothing. A
    replacement that names decorators brings them; one that names none keeps what
    the node had."""
    before = "def thing() -> int:\n    return 1\n"
    after = replace_function(
        before, "thing", "@pytest.fixture\ndef thing() -> int:\n    return 1\n"
    )
    assert "@pytest.fixture" in after


def test_a_transform_that_changes_nothing_says_so() -> None:
    """Silence is how both halves of this bug survived: a caller cannot tell an
    applied transform from one that matched and did nothing."""
    before = "@pytest.fixture\ndef thing() -> int:\n    return 1\n"
    with pytest.raises(CodemodRefusedError, match="identical"):
        replace_function(before, "thing", "@pytest.fixture\ndef thing() -> int:\n    return 1\n")
