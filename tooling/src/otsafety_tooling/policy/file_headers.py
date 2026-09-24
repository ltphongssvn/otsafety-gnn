# tooling/src/otsafety_tooling/policy/file_headers.py
"""Every tracked file opens with its repository path (G.21).

A FILE READ ON ITS OWN SAYS NOTHING ABOUT WHERE IT LIVES -- in a diff, a search
result, a pager, an agent's context. The path says it, and costs one line. The
working rules have asked for it since the first plan, and one test checked it for
.gitignore alone; everywhere else it was habit, and habit had lapsed in
thirty-five files by the time this was written.

WHERE THE PATH MAY SIT. A shebang must be the first line of a script and `---`
must open an Astro file, so the path follows whichever the format requires. HEAD
lines is enough for either and too few to bury it.

WHAT IS EXEMPT. A format with no comment syntax cannot carry one: JSON above all,
and the lockfiles and data files beside it. A GENERATED file is fixed at its
generator rather than by hand, since a hand-edit is undone on the next run -- so
those are listed here as the generator's job, not excused.
"""

from __future__ import annotations

from pathlib import Path

from otsafety_tooling.git.env import git

# HOW MANY LINES MAY PRECEDE THE PATH: one for a shebang or a frontmatter
# delimiter, and one spare. More would let it sink out of sight.
HEAD = 3

# EVERY FORMAT THAT CAN CARRY A COMMENT. A suffix absent here is not checked,
# which is why the set is explicit rather than a list of exclusions: a new
# format is unchecked until someone says how its comments are written.
COMMENTABLE = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".mts",
        ".mjs",
        ".astro",
        ".css",
        ".toml",
        ".yaml",
        ".yml",
        ".rego",
        ".nix",
        ".sh",
    }
)


def names_its_path(relative: str, text: str) -> bool:
    """Whether a file's opening lines carry its own repository path."""
    return any(relative in line for line in text.splitlines()[:HEAD])


def tracked(root: Path) -> list[str]:
    """Every file git tracks, as repository-relative paths.

    THROUGH THE SANCTIONED HELPER. A raw subprocess.run inherits whatever
    environment the caller had and resolves git from PATH; two existing gates
    caught this one immediately -- S607 for the partial path and the isolation
    test for the missing env. git() scrubs the environment and is what every
    other module already calls.
    """
    return git("ls-files", cwd=root).stdout.split()


def missing_path_header(root: Path) -> list[str]:
    """Every commentable tracked file whose opening lines omit its path."""
    offenders: list[str] = []
    for relative in tracked(root):
        path = root / relative
        if path.suffix not in COMMENTABLE or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not names_its_path(relative, text):
            offenders.append(relative)
    return offenders
