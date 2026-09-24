# tooling/src/otsafety_tooling/runs.py
"""Run a task and record what it did, as run-record/v1.

    context (git) -> child process -> streamed output -> record -> exit code

ONE PIPE, IN ORDER. The child's stderr is merged into its stdout and read as a
single stream, so the saved output keeps the order it was produced in. Written
separately, a task's own lines and its children's arrived shuffled in the file
-- visible in this project's own logs, where "setup complete" preceded the
"created" line that caused it.

NAMED BY THE RUN. The record and its output are <timestamp>-<task>-<id>, so no
two runs overwrite one another. Fixed names cost this project a merged pull
request's log earlier.

BOUNDED, BUT COMPLETE. Output is kept up to a limit and the digest covers the
WHOLE stream, so a truncated record still proves what the full output was.

THE EXIT CODE IS THE CHILD'S. Recording a run must not change whether it
failed; a command that could not start at all is recorded as a failure with the
shell's not-executable code.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import os
import pty
import shutil
import struct
import subprocess
import sys
import termios
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from otsafety_tooling.contracts.run_record import RunRecord
from otsafety_tooling.git.env import inherited_env

# 64 KiB of output kept per run: enough for a failing gate's report, small
# enough that a year of runs stays readable. The digest covers the rest.
OUTPUT_LIMIT_BYTES = 64 * 1024
BLOCK_BYTES = 8 * 1024
# The shell's code for "command not executable"; used when the child never ran.
NOT_EXECUTABLE = 127

MACHINE_ID_PATH = Path.home() / ".config" / "otsafety-gnn" / "machine-id"

# A FRESH PSEUDO-TERMINAL HANDS THE CHILD A 0x0 WINDOW unless a size is set, and
# every size-aware program then reads zero. Used when the parent has no size.
DEFAULT_WINDOW = (80, 24)


def should_use_tty(stdout: object, stderr: object) -> bool:
    """Whether the child should run on a pseudo-terminal.

    BOTH STREAMS MUST BE TERMINALS. With output redirected or piped, the child
    keeps a pipe, so a pipeline never receives colours or carriage returns --
    the behaviour a reader of `mise run ... | grep` depends on.
    """
    for stream in (stdout, stderr):
        checker = getattr(stream, "isatty", None)
        if checker is None or not checker():
            return False
    return True


def task_command(task: str, arguments: Sequence[str]) -> list[str]:
    """The command that runs a task with mise out of the way.

    --raw MATTERS MORE THAN IT LOOKS. mise's default `prefix` output style reads
    the child's output line by line to label it, which puts a pipe between the
    child and whatever terminal exists -- so gh's check watcher reprinted its
    whole block every ten seconds instead of redrawing one in place, even once
    the recorder ran on a pseudo-terminal. mise's own source describes raw as
    needing inherited stdio for stdin passthrough: the child then gets the
    terminal the recorder allocated, and behaves exactly as it would unwrapped.

    It also drops mise's `[task] $ command` lines and sets jobs to one, which a
    single wrapped task already was.
    """
    return ["mise", "run", "--raw", task, *arguments]


def _window_size() -> tuple[int, int]:
    """(columns, lines) of the parent's terminal, or the default."""
    size = shutil.get_terminal_size(fallback=DEFAULT_WINDOW)
    columns = size.columns or DEFAULT_WINDOW[0]
    lines = size.lines or DEFAULT_WINDOW[1]
    return columns, lines


def _open_pty() -> tuple[int, int]:
    """A master/slave pair whose window size the child can actually read."""
    master, slave = pty.openpty()
    columns, lines = _window_size()
    # TIOCSWINSZ takes rows, columns, and two pixel fields that terminals ignore.
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", lines, columns, 0, 0))
    return master, slave


def _stream_pty(master: int, destination: Path) -> tuple[int, str, bool]:
    """Copy the pty master to the terminal and a file; digest all of it.

    EIO IS END OF OUTPUT, NOT AN ERROR. Reading a master whose child has exited
    raises EIO on Linux and returns empty on other platforms; both mean the same
    thing, so they are normalised here.
    """
    digest = hashlib.sha256()
    total = 0
    with destination.open("wb") as kept:
        while True:
            try:
                block = os.read(master, BLOCK_BYTES)
            except OSError as error:
                if error.errno == errno.EIO:
                    break
                raise
            if not block:
                break
            digest.update(block)
            sys.stdout.buffer.write(block)
            sys.stdout.buffer.flush()
            if total < OUTPUT_LIMIT_BYTES:
                kept.write(block[: OUTPUT_LIMIT_BYTES - total])
            total += len(block)
    return total, digest.hexdigest(), total > OUTPUT_LIMIT_BYTES


def machine_id(path: Path = MACHINE_ID_PATH) -> str:
    """A stable, opaque identifier for this machine, created once.

    NOT A HOSTNAME. This laptop's name contains its owner's name, and records
    are shared evidence; a random identifier distinguishes machines without
    naming anyone.
    """
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    generated = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generated + "\n", encoding="utf-8")
    return generated


def _git_value(root: Path, *args: str, default: str) -> str:
    from otsafety_tooling.git.env import git

    result = git(*args, cwd=root)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else default


def _repository_name(root: Path) -> str:
    url = _git_value(root, "remote", "get-url", "origin", default="").rstrip("/")
    name = url.rsplit("/", 1)[-1].rsplit(":", 1)[-1].removesuffix(".git")
    return name or root.name


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%S%fZ")


def _stream(source: IO[bytes], destination: Path) -> tuple[int, str, bool]:
    """Copy the child's output to the terminal and a file; digest all of it.

    THE STREAM IS PASSED IN, NOT THE PROCESS. Popen types stdout as optional
    because it is None when no pipe was requested; an `assert` would narrow that
    for the type checker while disappearing under python -O, which is what
    ruff's S101 objects to. The caller checks once, and raises.
    """
    digest = hashlib.sha256()
    total = 0
    with destination.open("wb") as kept:
        while True:
            block = source.read(BLOCK_BYTES)
            if not block:
                break
            digest.update(block)
            sys.stdout.buffer.write(block)
            sys.stdout.buffer.flush()
            if total < OUTPUT_LIMIT_BYTES:
                kept.write(block[: OUTPUT_LIMIT_BYTES - total])
            total += len(block)
    return total, digest.hexdigest(), total > OUTPUT_LIMIT_BYTES


def record_run(
    task: str,
    arguments: Sequence[str],
    root: Path,
    records: Path,
    *,
    command: Sequence[str] | None = None,
    tty: bool | None = None,
) -> int:
    """Run one task, record it, and return the child's exit code.

    ON A PSEUDO-TERMINAL when this process's own output is one, so the child
    sees a terminal and behaves exactly as it would unwrapped: colours, a real
    window size, and a watcher that redraws in place rather than reprinting its
    whole block every ten seconds. The bytes read from the master are what a
    terminal would have received, and those are what is recorded.

    STDIN IS INHERITED EITHER WAY, so a prompt still reads from the keyboard and
    Ctrl-C still reaches the child, with no raw-mode handling here.
    """
    started_at = datetime.now(UTC)
    run_id = uuid.uuid4().hex[:12]
    records.mkdir(parents=True, exist_ok=True)
    base = f"{_stamp(started_at)}-{task}-{run_id}"
    output_file = records / f"{base}.log"

    argv = list(command) if command is not None else task_command(task, arguments)
    on_tty = should_use_tty(sys.stdout, sys.stderr) if tty is None else tty
    master, slave = _open_pty() if on_tty else (-1, -1)
    error_type: str | None = None
    try:
        process = subprocess.Popen(  # noqa: S603
            argv,
            env=inherited_env(),
            stdout=slave if on_tty else subprocess.PIPE,
            stderr=slave if on_tty else subprocess.STDOUT,
            cwd=root,
        )
    except OSError as error:
        if on_tty:
            os.close(master)
            os.close(slave)
        output_file.write_bytes(b"")
        total, digest, truncated = 0, hashlib.sha256(b"").hexdigest(), False
        exit_code = NOT_EXECUTABLE
        error_type = "CommandNotExecutable"
        sys.stderr.write(f"could not run {argv[0]}: {error}\n")
        sys.stderr.flush()
    else:
        if on_tty:
            # THE PARENT MUST CLOSE THE SLAVE, or the master never reaches end of
            # output: the pty stays open as long as any process holds that end.
            os.close(slave)
            total, digest, truncated = _stream_pty(master, output_file)
            os.close(master)
        else:
            stream = process.stdout
            if stream is None:
                raise RuntimeError("the child was started with a pipe but has no stdout")
            total, digest, truncated = _stream(stream, output_file)
        exit_code = process.wait()
        if exit_code != 0:
            error_type = "NonZeroExit"

    ended_at = datetime.now(UTC)
    record = RunRecord(
        id=run_id,
        task=task,
        arguments=tuple(arguments),
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=round((ended_at - started_at).total_seconds() * 1000),
        exit_code=exit_code,
        outcome="success" if exit_code == 0 else "failure",
        error_type=error_type,
        repository=_repository_name(root),
        branch=_git_value(root, "rev-parse", "--abbrev-ref", "HEAD", default="(detached)"),
        commit=_git_value(root, "rev-parse", "HEAD", default="0" * 40),
        machine=machine_id(),
        output_file=output_file.name,
        output_bytes=total,
        output_sha256=digest,
        truncated=truncated,
    )
    (records / f"{base}.json").write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m otsafety_tooling.runs <task> [arguments...]`, recorded.

    THE EXIT CODE IS THE TASK'S, so wrapping a task changes nothing except that
    it leaves evidence behind.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("usage: python -m otsafety_tooling.runs <task> [arguments...]")

    from otsafety_tooling.artifacts import artifacts_root
    from otsafety_tooling.paths import REPO_ROOT

    return record_run(args[0], args[1:], REPO_ROOT, artifacts_root(REPO_ROOT) / "runs")


if __name__ == "__main__":
    raise SystemExit(main())
