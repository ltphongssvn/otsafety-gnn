# tooling/src/otsafety_tooling/git/commit_domain.py
"""What a commit subject is, as a type.

THE INVARIANTS ARE THE TYPE. A subject is one line, at most a hundred characters,
and shaped `type(scope): summary` with a known type -- three checks that lived
inside the command, where each caller had to remember to run them. A subject that
breaks any of them cannot be constructed.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

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
SUBJECT_LIMIT = 100
SUBJECT = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([a-z0-9-]+\))?!?: \S.*$")


class CommitSubject(BaseModel):
    """One line, bounded, conventional: the first line of a commit message."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1, max_length=SUBJECT_LIMIT, pattern=SUBJECT.pattern)
