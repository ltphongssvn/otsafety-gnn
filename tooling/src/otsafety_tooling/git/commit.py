# tooling/src/otsafety_tooling/git/commit.py
"""Commit exactly the named paths, with a conventional message, through the hooks.

WHY A TASK. cscie103-olap-oltp made every git operation a task except the
commit itself, which stayed a hand-typed `git add` / `git commit`. Those are
the two commands where a stray path or an unrelated staged file silently
changes what a commit contains.

WHAT IT GUARANTEES
  focused   only the named paths are staged; anything ALREADY staged outside
            them is a refusal, not a surprise passenger
  non-empty a path with no changes is a refusal, so a typo cannot produce a
            commit that omits the file you meant
  typed     the subject follows Conventional Commits, so history can be read
            by type and scope
  checked   `git commit` runs normally, so the pre-commit hook (branch guard,
            format, lint) still decides; its output is shown, not captured
  clean     build artifacts (bytecode, tool caches, OS metadata) are refused
            even if .gitignore misses them

WHY THE ARTIFACT CHECK DOES NOT TRUST .gitignore. Committing __pycache__ is a
recurring, well-documented failure: someone runs the tests, then commits a
directory, and the bytecode rides along because nothing ignored it. It
happened here when the new tooling/ member was committed before the root
.gitignore covered it. The ignore file is the first layer; this is the layer
that holds when the first one has a gap.

`commit:undo` reverses the last commit when it has not been pushed, so a
mistake is fixed before it reaches history anyone else can see.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from otsafety_tooling.git.env import git, scrubbed_env
from otsafety_tooling.paths import REPO_ROOT

# BUILD ARTIFACTS: regenerable, machine- and version-specific, never source.
ARTIFACT_DIRS = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "node_modules"}
)
ARTIFACT_SUFFIXES = (".pyc", ".pyo", ".pyd")
ARTIFACT_NAMES = frozenset({".DS_Store"})

TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)
SUBJECT = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([a-z0-9-]+\))?!?: \S.*$")
MAX_SUBJECT = 100


def validate_subject(subject: str) -> None:
    """Refuse a subject that is not `type(scope): summary`."""
    if "\n" in subject:
        raise SystemExit("commit refused: the subject must be one line; put detail in --body")
    if len(subject) > MAX_SUBJECT:
        raise SystemExit(
            f"commit refused: subject is {len(subject)} characters (max {MAX_SUBJECT})"
        )
    if not SUBJECT.match(subject):
        raise SystemExit(
            "commit refused: subject must be `type(scope): summary` with type one of "
            + ", ".join(TYPES)
        )


def is_within(path: str, roots: Sequence[str]) -> bool:
    """Whether a repository-relative path is one of `roots` or inside one."""
    target = Path(path)
    return any(target == Path(root) or Path(root) in target.parents for root in roots)


def outsiders(staged: Sequence[str], roots: Sequence[str]) -> list[str]:
    """Staged paths that are not covered by the paths being committed."""
    return [path for path in staged if not is_within(path, roots)]


def is_artifact(path: str) -> bool:
    """Whether a repository-relative path is a build artifact."""
    parts = Path(path).parts
    return (
        any(part in ARTIFACT_DIRS for part in parts)
        or path.endswith(ARTIFACT_SUFFIXES)
        or (bool(parts) and parts[-1] in ARTIFACT_NAMES)
    )


def pending_paths(roots: Sequence[str], root: Path) -> list[str]:
    """What `git add -- roots` WOULD stage, read without touching the index.

    Modified, deleted and untracked-but-not-ignored files, NUL-separated so a
    path with a space or newline cannot be misread.
    """
    result = git(
        "ls-files",
        "-z",
        "--modified",
        "--deleted",
        "--others",
        "--exclude-standard",
        "--",
        *roots,
        cwd=root,
    )
    if result.returncode != 0:
        raise SystemExit(f"could not list changes: {result.stderr.strip()}")
    return sorted({path for path in result.stdout.split("\0") if path})


def staged_paths(root: Path) -> list[str]:
    result = git("diff", "--cached", "--name-only", "-z", cwd=root)
    if result.returncode != 0:
        raise SystemExit(f"could not read the index: {result.stderr.strip()}")
    return [path for path in result.stdout.split("\0") if path]


def normalise(paths: Sequence[str], root: Path) -> list[str]:
    """Repository-relative forms of the given paths, refusing ones outside it."""
    normalised = []
    for raw in paths:
        absolute = (Path.cwd() / raw).resolve()
        try:
            normalised.append(absolute.relative_to(root.resolve()).as_posix() or ".")
        except ValueError:
            raise SystemExit(f"commit refused: {raw} is outside the repository") from None
    return normalised


def commit(subject: str, body: str, paths: Sequence[str], root: Path) -> int:
    validate_subject(subject)
    if not paths:
        raise SystemExit("commit refused: name at least one path")
    roots = normalise(paths, root)

    already = outsiders(staged_paths(root), roots)
    if already:
        raise SystemExit(
            "commit refused: already staged outside the named paths: " + ", ".join(already)
        )

    artifacts = [path for path in pending_paths(roots, root) if is_artifact(path)]
    if artifacts:
        raise SystemExit(
            "commit refused: build artifacts under the named paths (add them to "
            ".gitignore, or delete them):\n  " + "\n  ".join(artifacts)
        )

    added = git("add", "--", *roots, cwd=root)
    if added.returncode != 0:
        raise SystemExit(f"git add failed: {added.stderr.strip()}")

    staged = staged_paths(root)
    unchanged = [r for r in roots if not any(is_within(path, [r]) for path in staged)]
    if unchanged:
        raise SystemExit("commit refused: no changes under " + ", ".join(unchanged))

    print("committing:")
    for path in staged:
        print(f"  {path}")

    message = ["-m", subject] + (["-m", body] if body.strip() else [])
    # OUTPUT IS NOT CAPTURED: the hook's report is the point of running it.
    result = subprocess.run(  # noqa: S603
        ["git", "commit", *message],  # noqa: S607
        cwd=root,
        env=scrubbed_env(),
        check=False,
    )
    if result.returncode != 0:
        print(
            "\ncommit refused by git or a hook; the files remain staged. "
            "Fix the report above and run the task again.",
            file=sys.stderr,
        )
        return result.returncode

    head = git("log", "-1", "--format=%h %s", cwd=root).stdout.strip()
    print(f"\ncommitted {head}")
    return 0


PROTECTED = frozenset({"develop", "main"})


def undo_last(root: Path) -> int:
    """Undo the last commit, keeping its changes in the working tree, if unpushed.

    REFUSES WHEN UNDOING WOULD REWRITE SHARED OR PROTECTED HISTORY:
      - on develop or main
      - the commit is already on any remote-tracking branch (it was pushed)
      - the commit is a merge, or the first commit of the repository
      - something is staged, which a mixed reset would silently mix in
    """
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).stdout.strip()
    if branch in PROTECTED:
        raise SystemExit(f"undo refused: on protected branch {branch!r}")

    if staged_paths(root):
        raise SystemExit("undo refused: changes are staged; commit or unstage them first")

    parents = git("rev-list", "--parents", "-n", "1", "HEAD", cwd=root).stdout.split()
    if len(parents) != 2:
        kind = "the first commit" if len(parents) < 2 else "a merge commit"
        raise SystemExit(f"undo refused: HEAD is {kind}")

    remotes = git("branch", "-r", "--contains", "HEAD", cwd=root)
    if remotes.returncode != 0:
        raise SystemExit(f"could not check remote branches: {remotes.stderr.strip()}")
    if remotes.stdout.strip():
        raise SystemExit(
            "undo refused: HEAD is already pushed ("
            + ", ".join(line.strip() for line in remotes.stdout.splitlines())
            + "); fix it with a new commit instead"
        )

    subject = git("log", "-1", "--format=%h %s", cwd=root).stdout.strip()
    reset = git("reset", "--mixed", "--quiet", "HEAD~1", cwd=root)
    if reset.returncode != 0:
        raise SystemExit(f"undo failed: {reset.stderr.strip()}")
    print(f"undid {subject}; its changes are back in the working tree, unstaged")
    return 0


def unstage(paths: Sequence[str], root: Path) -> int:
    """Remove the named paths from the index, leaving the working tree alone.

    For a file staged by something other than the commit task -- an IDE that
    adds new files automatically, for example. Refuses a path with nothing
    staged under it, so a typo cannot report success while changing nothing.
    """
    if not paths:
        raise SystemExit("unstage refused: name at least one path")
    roots = normalise(paths, root)
    staged = staged_paths(root)
    missing = [r for r in roots if not any(is_within(path, [r]) for path in staged)]
    if missing:
        raise SystemExit("unstage refused: nothing staged under " + ", ".join(missing))

    targets = [path for path in staged if is_within(path, roots)]
    has_head = git("rev-parse", "--verify", "--quiet", "HEAD", cwd=root).returncode == 0
    command = (
        ["restore", "--staged", "--"] if has_head else ["rm", "--cached", "-r", "--quiet", "--"]
    )
    result = git(*command, *targets, cwd=root)
    if result.returncode != 0:
        raise SystemExit(f"unstage failed: {result.stderr.strip()}")
    for path in targets:
        print(f"unstaged {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args_list = sys.argv[1:] if argv is None else list(argv)
    if args_list == ["undo"]:
        return undo_last(REPO_ROOT)
    if args_list[:1] == ["unstage"]:
        rest = args_list[1:]
        return unstage(rest[1:] if rest[:1] == ["--"] else rest, REPO_ROOT)

    parser = argparse.ArgumentParser(prog="commit", description=__doc__.splitlines()[0])
    parser.add_argument("--message", "-m", required=True, help="type(scope): summary")
    parser.add_argument("--body", "-b", default="", help="explanatory paragraph")
    parser.add_argument("paths", nargs="+", help="files or directories to commit")
    args = parser.parse_args(args_list)
    return commit(args.message, args.body, args.paths, REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
