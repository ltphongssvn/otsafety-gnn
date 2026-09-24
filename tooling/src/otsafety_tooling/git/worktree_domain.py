# tooling/src/otsafety_tooling/git/worktree_domain.py
"""The worktree domain: what a slug is, and what a worktree reference is.

THE INVARIANTS ARE THE TYPES, not checks scattered through the commands. A slug is
lowercase kebab-case or it does not exist. A worktree reference derives its branch
and its path from that slug, so the two can never disagree -- the bug where a
command reports one branch and acts on another is unrepresentable here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

BRANCH_PREFIX = "feature/"

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", min_length=1)]


class WorktreeRef(BaseModel):
    """One worktree: its slug, and the branch and path that follow from it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: Slug
    main: Path

    @property
    def branch(self) -> str:
        return f"{BRANCH_PREFIX}{self.slug}"

    @property
    def path(self) -> Path:
        return self.main.parent / f"{self.main.name}-{self.slug}"
