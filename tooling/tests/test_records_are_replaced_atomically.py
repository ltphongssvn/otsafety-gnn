# tooling/tests/test_records_are_replaced_atomically.py
"""A record is replaced atomically or not at all (G.81).

TWENTY-FIVE CALL SITES USED Path.write_text, which opens for writing and
truncates before a byte is written. An interruption there leaves the plan, the
ledger, the trace or the matrix as neither the old file nor the new one -- and
every writer here runs unattended, where nobody is watching to notice.

THE SEQUENCE IS SETTLED. Stage into a temporary file IN THE TARGET'S OWN
DIRECTORY, because os.replace is atomic only within one filesystem and fails
across devices; flush and fsync, because flush reaches the operating system
cache and no further; replace, which is atomic on POSIX and on Windows; then
fsync the parent directory so the new entry survives power loss. Carry the
original mode across, because mkstemp creates at 0600.

AND THE BAN IS THE FIX, not the helper. A helper anyone may forget is the
treadmill; this repository already refuses raw parsing and bare environment
reads through the same mechanism, so truncating writes join them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.81")

# WHERE A TRUNCATING WRITE IS STILL FINE: build output is regenerated wholly and
# tracked by nothing, so a partial one is discarded rather than believed.
EXEMPT = (
    "scripts/build_arch_onepager.py",
    "scripts/build_plan_report.py",
    # RUNS BEFORE THE PACKAGE EXISTS, so it cannot import the helper: it stages,
    # fsyncs and replaces with the standard library alone, and its own docstring
    # says so three times.
    "scripts/bootstrap_toolchain.py",
)


def test_writing_replaces_rather_than_truncates(tmp_path: Path) -> None:
    """The helper exists and leaves the file complete."""
    from otsafety_tooling.atomic import write_text

    target = tmp_path / "record.yaml"
    write_text(target, "first\n")
    assert target.read_text(encoding="utf-8") == "first\n"
    write_text(target, "second\n")
    assert target.read_text(encoding="utf-8") == "second\n"


def test_no_temporary_file_survives(tmp_path: Path) -> None:
    """A staged file left behind is litter the next reader may find."""
    from otsafety_tooling.atomic import write_text

    write_text(tmp_path / "record.yaml", "content\n")
    assert [p.name for p in tmp_path.iterdir()] == ["record.yaml"]


def test_the_mode_of_an_existing_file_is_kept(tmp_path: Path) -> None:
    """mkstemp creates at 0600, so a replaced file would lose its permissions."""
    from otsafety_tooling.atomic import write_text

    target = tmp_path / "script.sh"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o755)
    write_text(target, "new\n")
    assert target.stat().st_mode & 0o777 == 0o755


def test_a_failed_write_leaves_the_original(tmp_path: Path) -> None:
    """THE LIVENESS CONTROL: the guarantee, exercised rather than asserted."""
    from otsafety_tooling.atomic import write_text

    target = tmp_path / "record.yaml"
    write_text(target, "original\n")

    class Unserialisable:
        def __str__(self) -> str:
            raise RuntimeError("interrupted mid-write")

    with pytest.raises(RuntimeError):
        write_text(target, str(Unserialisable()))
    assert target.read_text(encoding="utf-8") == "original\n", "the original was lost"


def test_no_shipped_writer_truncates_in_place() -> None:
    """The ban, over the tree: every durable record goes through the helper."""
    offenders: list[str] = []
    for folder in ("tooling/src", "scripts", "python"):
        for path in sorted((REPO_ROOT / folder).rglob("*.py")):
            relative = str(path.relative_to(REPO_ROOT))
            if relative in EXEMPT or relative.endswith("atomic.py"):
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not (
                    isinstance(node, ast.Attribute) and node.attr in {"write_text", "write_bytes"}
                ):
                    continue
                on = node.value
                if isinstance(on, ast.Name) and on.id == "atomic":
                    continue
                offenders.append(f"{relative}:{node.lineno}")
    assert offenders == [], f"{len(offenders)} truncating writes: {offenders[:6]}"
