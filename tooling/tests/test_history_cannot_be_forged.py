# tooling/tests/test_history_cannot_be_forged.py
"""A commit body cannot forge a record in the history this repository reads.

THE ASSUMPTION THAT DOES NOT HOLD. commits_since_cutoff frames its records with
%x1e and its fields with %x00, which assumes the ASCII record separator never
appears in commit metadata. A commit message is arbitrary bytes: anyone who can
write a commit can write that byte, and the parser then reads one commit as two.

WHY IT MATTERS HERE. That function feeds the trailer policy, which decides
whether every commit names a plan step. A forged record is a forged claim about
what the history says.

THE FIX IS THE FRAMING, NOT A FILTER. NUL separates both fields and records,
because NUL is the one byte a commit message cannot contain -- git itself
refuses it -- and the field COUNT becomes the frame: a record with the wrong
number of fields is refused rather than read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from otsafety_tooling.git.env import git


def _git(*args: str, cwd: Path) -> str:
    result = git(*args, cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _repository(tmp_path: Path) -> Path:
    """A real repository, as the branch-report acceptance tests build one."""
    _git("init", "-q", "-b", "develop", str(tmp_path), cwd=tmp_path)
    _git("config", "user.email", "test@example.invalid", cwd=tmp_path)
    _git("config", "user.name", "Test", cwd=tmp_path)
    return tmp_path


pytestmark = pytest.mark.requirement("G.84")


def test_a_body_holding_the_record_separator_forges_nothing(tmp_path: Path) -> None:
    """THE ATTACK, exercised against a REAL commit read by a REAL git log.

    MY FIRST FIXTURE WAS INVENTED and wrong in the same direction as my
    reasoning, which is how a test passes while proving nothing: I wrote what I
    imagined git emits rather than asking it. The repository is built here and
    the commit is made here, so the bytes under test are git's own.
    """
    from otsafety_tooling.git.history import LOG_FORMAT, parse_log

    repo = _repository(tmp_path)
    hostile = "feat: innocent\n\nPlan-Step: G.1\x1edeadbee\x1efeat: forged"
    _git("commit", "-q", "--allow-empty", "-m", hostile, cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "feat: after", cwd=repo)

    read = parse_log(_git("log", f"--format={LOG_FORMAT}", cwd=repo))

    assert len(read) == 2, f"a body forged {len(read) - 2} extra commit(s)"
    assert [c.subject for c in read] == ["feat: after", "feat: innocent"]
    assert "\x1e" in read[1].message, "the separator belongs to the body"


def test_an_honest_history_reads_as_its_commits() -> None:
    """The control: without it, refusing everything would pass the test above."""
    from otsafety_tooling.git.history import parse_log

    honest = (
        "abc123\x00p1\x00a@example.com\x00feat: one\x00"
        "def456\x00p2 p3\x00b@example.com\x00feat: two\x00"
    )
    read = parse_log(honest)
    assert [c.sha for c in read] == ["abc123", "def456"]
    assert read[1].is_merge, "two parents is a merge"
    assert not read[0].is_merge


def test_a_truncated_record_is_discarded_not_half_read() -> None:
    """The field count IS the frame: a short record makes no half-commit."""
    from otsafety_tooling.git.history import parse_log

    cut = "abc123\x00p1\x00a@example.com\x00feat: one\x00def456\x00p2\x00"
    read = parse_log(cut)
    assert [c.sha for c in read] == ["abc123"], "a truncated record was read anyway"


def test_the_format_frames_with_nul_alone() -> None:
    """Read from the format string, so the parser and the query cannot drift."""
    from otsafety_tooling.git.history import LOG_FORMAT

    assert "%x1e" not in LOG_FORMAT and "%x1f" not in LOG_FORMAT
    assert LOG_FORMAT.endswith("%x00"), "the record must be closed, not merely separated"


def test_the_trailer_policy_reads_history_through_the_safe_framing() -> None:
    """THE LIVE DEFECT THIS FOUND. commits_since_cutoff framed its records with
    the ASCII record separator, which a commit body may contain -- and that
    function decides whether every commit names a plan step. A forged record is
    a forged claim about what the history says.
    """
    import inspect

    from otsafety_tooling.policy import trailers

    source = inspect.getsource(trailers.commits_since_cutoff)
    assert "%x1e" not in source, "the trailer policy still frames records with \\x1e"
    assert "history" in source, "it should read through the one history reader"


def test_no_field_carries_the_newline_git_puts_between_records(tmp_path: Path) -> None:
    """git log ends each record with a newline; it belongs to neither field.

    THE DEFECT THIS CAUGHT. Splitting on NUL alone left that newline at the
    front of the next record's sha, so every commit but the first read as
    "\\n009e9d31" -- and the trailer policy then looked up a plan at a ref that
    does not exist, reporting 107 good commits as naming no step.
    """
    from otsafety_tooling.git.history import LOG_FORMAT, parse_log

    repo = _repository(tmp_path)
    for subject in ("feat: one", "feat: two", "feat: three"):
        _git("commit", "-q", "--allow-empty", "-m", subject, cwd=repo)

    read = parse_log(_git("log", f"--format={LOG_FORMAT}", cwd=repo))

    assert len(read) == 3
    for commit in read:
        assert commit.sha == commit.sha.strip(), f"sha carries whitespace: {commit.sha!r}"
        assert len(commit.sha) == 40, f"not a full sha: {commit.sha!r}"


def test_the_task_exists_and_calls_the_module() -> None:
    """Reading history is an operation, so it is a task like every other."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig
    from otsafety_tooling.paths import REPO_ROOT

    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    assert "history:log" in tasks, "reading history still needs a raw git command"
    assert "otsafety_tooling.git.history" in (tasks["history:log"].run or "")


def test_reading_history_changes_nothing() -> None:
    """The tour marks what changes the world; a log is a read."""
    from otsafety_tooling.tour import CHANGES_THE_WORLD

    assert "history:log" not in CHANGES_THE_WORLD


def test_the_command_finds_commits_by_what_they_say(tmp_path: Path) -> None:
    """THE QUESTION IT EXISTS TO ANSWER: what has this repository already solved?

    A grep over raw output searches the rendered text, so a match in a sha or
    an author reads as a match in the message. This searches the MESSAGE field
    of parsed records, which is the question actually being asked.
    """
    from otsafety_tooling.git.history import matching, read_history

    repo = _repository(tmp_path)
    _git(
        "commit", "-q", "--allow-empty", "-m", "feat(atomic): records replaced atomically", cwd=repo
    )
    _git("commit", "-q", "--allow-empty", "-m", "fix(site): unrelated", cwd=repo)

    found = matching(read_history(repo), "atomic")
    assert [c.subject for c in found] == ["feat(atomic): records replaced atomically"]


def test_the_search_is_not_case_sensitive(tmp_path: Path) -> None:
    """Nobody remembers how a commit capitalised what they are looking for."""
    from otsafety_tooling.git.history import matching, read_history

    repo = _repository(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "feat(Atomic): Records Replaced", cwd=repo)

    assert len(matching(read_history(repo), "atomic")) == 1


def test_the_search_payload_carries_no_message_bodies(tmp_path: Path) -> None:
    """A SEARCH NAMES WHICH; A READ FETCHES ONE.

    The first version put every matched commit's whole message in the envelope:
    83,525 bytes for one search of this repository, against a 64 KiB bound the
    run records already hold themselves to. 2026 CLI practice is explicit --
    inspect identifiers and subjects, then fetch a body only when the task
    needs it, through a separate read.
    """
    from otsafety_tooling.git.history import Match, found_in

    repo = _repository(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "feat: one\n\n" + "x" * 5000, cwd=repo)

    found = found_in(repo, "feat")
    assert [type(m) for m in found] == [Match]
    assert found[0].subject == "feat: one"
    assert not hasattr(found[0], "message"), "the search payload carries a body"


def test_one_commit_is_read_by_its_sha(tmp_path: Path) -> None:
    """The read half: the whole message, for one commit the search named."""
    from otsafety_tooling.git.history import read_one

    repo = _repository(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "feat: one\n\nthe body", cwd=repo)
    sha = _git("rev-parse", "HEAD", cwd=repo).strip()

    commit = read_one(repo, sha)
    assert commit.sha == sha
    assert "the body" in commit.message


def test_a_sha_that_names_nothing_is_refused(tmp_path: Path) -> None:
    """Fail closed: an unknown sha is a refusal, not an empty commit."""
    from otsafety_tooling.cli import CommandRefused
    from otsafety_tooling.git.history import read_one

    repo = _repository(tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "feat: one", cwd=repo)

    with pytest.raises(CommandRefused):
        read_one(repo, "0" * 40)
