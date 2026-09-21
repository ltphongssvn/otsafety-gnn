# tooling/tests/test_runs_acceptance.py
"""Acceptance: every task run is recorded, with its output kept in order.

REAL CHILD PROCESSES. Each scenario runs a small command through the recorder
and then reads the record and the output file back. The command runner is
injected so these tests do not need mise, but nothing else is replaced: the
pipe, the truncation, the digest and the exit code are the real ones.

THE TWO DEFECTS THIS CLOSES
    P9  fixed log names overwrote each other; a pull request log was lost
    P7  a task's own output and its children's arrived out of order in a file
"""

import hashlib
from pathlib import Path

from otsafety_tooling.contracts.run_record import RunRecord
from otsafety_tooling.git.env import git
from otsafety_tooling.runs import OUTPUT_LIMIT_BYTES, machine_id, record_run


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


def _shell(script: str) -> list[str]:
    """A command list that runs one shell script, standing in for a mise task."""
    return ["bash", "-c", script]


def _only_record(records: Path) -> RunRecord:
    files = sorted(records.glob("*.json"))
    assert len(files) == 1, files
    return RunRecord.model_validate_json(files[0].read_text(encoding="utf-8"))


def test_a_successful_run_is_recorded(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    exit_code = record_run("test", (), root, records, command=_shell("echo done"))

    assert exit_code == 0
    record = _only_record(records)
    assert (record.task, record.outcome, record.exit_code) == ("test", "success", 0)
    assert record.error_type is None
    assert record.repository == "demo"
    assert record.branch == "feature/x"


def test_a_failing_run_keeps_its_exit_code_and_names_the_error(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    exit_code = record_run("lint", (), root, records, command=_shell("echo nope >&2; exit 3"))

    assert exit_code == 3
    record = _only_record(records)
    assert (record.outcome, record.exit_code, record.error_type) == ("failure", 3, "NonZeroExit")


def test_both_streams_are_captured_in_the_order_they_were_produced(tmp_path: Path) -> None:
    """P7: a separate stderr stream arrived out of order in the saved log."""
    root, records = _repo(tmp_path), tmp_path / "runs"
    script = "echo first; echo second >&2; echo third"
    record_run("test", (), root, records, command=_shell(script))

    record = _only_record(records)
    output = (records / record.output_file).read_text(encoding="utf-8")
    assert output.splitlines() == ["first", "second", "third"]


def test_long_output_is_truncated_but_its_digest_covers_everything(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    line = "x" * 1000 + "\n"
    repeats = (OUTPUT_LIMIT_BYTES // len(line)) + 10
    script = f"for i in $(seq {repeats}); do echo '{line.strip()}'; done"
    record_run("test", (), root, records, command=_shell(script))

    record = _only_record(records)
    kept = (records / record.output_file).read_bytes()
    assert record.truncated
    assert len(kept) <= OUTPUT_LIMIT_BYTES
    assert record.output_bytes > OUTPUT_LIMIT_BYTES
    assert record.output_sha256 == hashlib.sha256(line.encode() * repeats).hexdigest()


def test_short_output_is_recorded_whole(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    record_run("test", (), root, records, command=_shell("printf 'hello\\n'"))

    record = _only_record(records)
    assert not record.truncated
    assert record.output_bytes == 6
    assert record.output_sha256 == hashlib.sha256(b"hello\n").hexdigest()


def test_arguments_are_recorded(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    record_run("branches-prune", ("--apply",), root, records, command=_shell("true"))
    assert _only_record(records).arguments == ("--apply",)


def test_two_runs_of_one_task_never_overwrite_each_other(tmp_path: Path) -> None:
    """P9: fixed names meant every run replaced the previous one's evidence."""
    root, records = _repo(tmp_path), tmp_path / "runs"
    record_run("test", (), root, records, command=_shell("echo one"))
    record_run("test", (), root, records, command=_shell("echo two"))

    written = sorted(records.glob("*.json"))
    assert len(written) == 2
    logs = sorted(path.name for path in records.glob("*.log"))
    assert len(logs) == 2
    kept = {(records / path.name).read_text(encoding="utf-8") for path in records.glob("*.log")}
    assert kept == {"one\n", "two\n"}


def test_the_machine_is_an_opaque_identifier(tmp_path: Path) -> None:
    """A hostname would carry the owner's name into shared evidence."""
    first = machine_id(tmp_path / "machine-id")
    second = machine_id(tmp_path / "machine-id")
    assert first == second
    assert len(first) == 36


def test_a_command_that_cannot_run_is_still_recorded(tmp_path: Path) -> None:
    root, records = _repo(tmp_path), tmp_path / "runs"
    exit_code = record_run("test", (), root, records, command=["./definitely-not-here"])

    assert exit_code != 0
    record = _only_record(records)
    assert record.outcome == "failure"
    assert record.error_type == "CommandNotExecutable"
