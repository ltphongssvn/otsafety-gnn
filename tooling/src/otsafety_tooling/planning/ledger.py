# tooling/src/otsafety_tooling/planning/ledger.py
"""The record of every id ever issued: append-only, one writer.

AN ID IS ASSIGNED ONCE AND NEVER REUSED, even after the thing it named is gone.
2026 traceability practice is blunt about why: renumber or reuse an id and every
link that ever pointed at it -- a trace candidate, a test file, a commit trailer
-- silently points at something else, and nothing notices. So an id leaves the
plan by being RETIRED here, not by disappearing, and issue() refuses one the
ledger has already seen.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.traceability import IdLedger, IssuedId
from otsafety_tooling.paths import REPO_ROOT


def ledger_path(root: Path = REPO_ROOT) -> Path:
    """Beside the plan, because it is the plan's own history of names."""
    return root / "context" / "plan-ids.yaml"


def load_ledger(path: Path | None = None) -> IdLedger:
    """The ledger, through its contract."""
    return read_yaml(path or ledger_path(), IdLedger)


def issue(ledger: IdLedger, entry: IssuedId) -> IdLedger:
    """A ledger with the id appended; an id already issued is refused."""
    if entry.id in {existing.id for existing in ledger.issued}:
        raise ValueError(f"{entry.id} was issued already; an id is never reused")
    return ledger.model_copy(update={"issued": (*ledger.issued, entry)})


def canonical(ledger: IdLedger) -> str:
    """The one serialization, as the plan writer has one."""
    return yaml.safe_dump(
        ledger.model_dump(mode="json", by_alias=True, exclude_none=True),
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


def save_ledger(ledger: IdLedger, path: Path | None = None) -> Path:
    """Write the ledger in its canonical form, and nothing else."""
    target = path or ledger_path()
    target.write_text(canonical(ledger), encoding="utf-8")
    return target
