# tooling/tests/test_runs_tty.py
"""A recorded run still looks and behaves like a raw one.

THE DEFECT. The recorder gave the child a pipe, so every tool saw "not a
terminal" and changed behaviour: gh's check watcher reprinted its whole block
every ten seconds instead of redrawing one in place, mise truncated a task line
to an assumed width, colours vanished, and output arrived in bursts.

THE FIX. Run the child on a pseudo-terminal when the recorder's own output is
one, so isatty() is true for the child and the window size is real. The bytes
read from the master are exactly what a terminal would have received, including
the carriage returns a tty adds, and they are what gets recorded.

STDIN STAYS THE REAL TERMINAL. Only stdout and stderr move to the pty, so a
prompt still reads from the keyboard and Ctrl-C still reaches the child,
without raw-mode juggling.

WHEN OUTPUT IS NOT A TERMINAL (CI, a redirect, a pipe) the child keeps a pipe,
so a pipeline never receives colours or CRLF.
"""

import hashlib
import sys
from io import StringIO
from pathlib import Path

import pytest

from otsafety_tooling.contracts.run_record import RunRecord
from otsafety_tooling.git.env import git
from otsafety_tooling.runs import (
    _window_size,
    record_run,
    should_use_tty,
    task_command,
)


class _Terminal(StringIO):
    """A stream that claims to be a terminal, as sys.stdout does in a shell."""

    def isatty(self) -> bool:
        return True


def _git(*args: str, cwd: Path) -> None:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", "-b", "feature/x", cwd=root)
    _git("config", "user.email", "test@example.invalid", cwd=root)
    _git("config", "user.name", "Test", cwd=root)
    _git("commit", "-q", "--allow-empty", "-m", "base", cwd=root)
    _git("remote", "add", "origin", "https://example.invalid/owner/demo.git", cwd=root)
    return root


def _python(script: str) -> list[str]:
    return [sys.executable, "-c", script]


def _record(records: Path) -> RunRecord:
    files = sorted(records.glob("*.json"))
    assert len(files) == 1, files
    return RunRecord.model_validate_json(files[0].read_text(encoding="utf-8"))


def _output(records: Path) -> bytes:
    return (records / _record(records).output_file).read_bytes()


def test_a_terminal_on_both_streams_earns_a_pseudo_terminal() -> None:
    assert should_use_tty(_Terminal(), _Terminal())


def test_a_redirected_stdout_keeps_the_pipe() -> None:
    """A pipeline must never receive colours or carriage returns."""
    assert not should_use_tty(StringIO(), _Terminal())


def test_a_redirected_stderr_keeps_the_pipe() -> None:
    assert not should_use_tty(_Terminal(), StringIO())


def test_the_child_sees_a_terminal(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    script = "import sys; print(sys.stdout.isatty(), sys.stderr.isatty())"

    record_run("test", (), root, records, command=_python(script), tty=True)

    assert b"True True" in _output(records)


def test_without_a_pseudo_terminal_the_child_sees_a_pipe(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    script = "import sys; print(sys.stdout.isatty(), sys.stderr.isatty())"

    record_run("test", (), root, records, command=_python(script), tty=False)

    assert b"False False" in _output(records)


def test_the_child_is_given_a_real_window_size(tmp_path: Path) -> None:
    """A fresh pty hands the child a 0x0 window unless the size is set.

    ASSERTS WHAT THE RECORDER PASSES, NOT THE FALLBACK. Comparing against the
    fallback constant passed on a laptop only because pytest captures output
    there, so no terminal was found; on FAS OnDemand, where the terminal is
    real, the child correctly reported 167x44 and the test failed. The
    requirement is that the child receives THIS process's size, never a zero.
    """
    root, records = _repo(tmp_path), tmp_path / "runs"
    script = "import shutil; size = shutil.get_terminal_size(); print(size.columns, size.lines)"

    record_run("test", (), root, records, command=_python(script), tty=True)

    columns, lines = _window_size()
    assert columns > 0
    assert lines > 0
    assert f"{columns} {lines}".encode() in _output(records)


def test_the_recorded_bytes_are_what_a_terminal_would_have_received(
    tmp_path: Path,
) -> None:
    """A tty turns a newline into carriage-return newline; that is the raw output."""
    root, records = _repo(tmp_path), tmp_path / "runs"

    record_run("test", (), root, records, command=_python("print('hello')"), tty=True)

    kept = _output(records)
    assert b"hello\r\n" in kept
    record = _record(records)
    assert record.output_sha256 == hashlib.sha256(kept).hexdigest()
    assert record.output_bytes == len(kept)


@pytest.mark.parametrize("tty", [True, False])
def test_the_exit_code_survives_either_way(tmp_path: Path, tty: bool) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"

    command = _python("raise SystemExit(3)")
    exit_code = record_run("test", (), root, records, command=command, tty=tty)

    assert exit_code == 3
    assert _record(records).error_type == "NonZeroExit"


def test_a_task_is_run_with_mise_out_of_the_way() -> None:
    """mise's default `prefix` style reads the child line by line to label it.

    That pipe is what kept gh from seeing the pseudo-terminal: the watcher
    reprinted its whole block every ten seconds instead of redrawing one in
    place. mise's `raw` mode inherits stdio instead, so the child gets the
    terminal the recorder allocated.
    """
    assert task_command("branches", ()) == ["mise", "run", "--raw", "branches"]


def test_task_arguments_follow_the_task_name() -> None:
    assert task_command("branches:prune", ("--apply",)) == [
        "mise",
        "run",
        "--raw",
        "branches:prune",
        "--apply",
    ]
