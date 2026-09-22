# tooling/src/otsafety_tooling/artifacts.py
"""Where evidence is recorded: one .artifacts/ per clone, in the main checkout.

WHY NOT THE CURRENT WORKTREE. git documents that `worktree remove` refuses only
for untracked or modified tracked files, then deletes the whole directory, and
ignored files are neither. An ignored .artifacts/ inside a linked worktree --
its reports, logs and records -- would be deleted with it. Every worktree
therefore records into the MAIN checkout's .artifacts/, which outlives them.

HOW THE MAIN CHECKOUT IS FOUND. git lists the main worktree first; the list is
read with the same fail-closed parser the worktree tasks use.

A BARE MAIN REPOSITORY IS REFUSED. It has no working tree to hold evidence, and
guessing a location would put records somewhere nobody looks.

NO SIDE EFFECTS. The directory is created by whoever writes into it, so asking
where evidence belongs never changes the filesystem.

OTSAFETY_ARTIFACTS OVERRIDES ALL OF THIS, and it is the one variable both readers
honour: this module and the site's build. Two things forced it. The site
resolved .artifacts relative to its own source file, so built from a linked
worktree it read that worktree's empty folder while every record lived in the
main checkout. And the site's acceptance tests seeded fixtures into the real
root, where seven fabricated experiment records landed; the tests now point this
variable at a disposable directory, and the real root is never touched.

FROM THE SHELL. `mise run -q artifacts:path` prints the root and nothing else,
so any worktree can write a log with
    "$(mise run -q artifacts:path)/logs/<name>.log"
"""

from __future__ import annotations

from pathlib import Path

from otsafety_tooling.contracts.settings import settings
from otsafety_tooling.git.worktree import parse_records
from otsafety_tooling.paths import REPO_ROOT

ARTIFACTS_DIR = ".artifacts"
OVERRIDE_VARIABLE = "OTSAFETY_ARTIFACTS"


def artifacts_root(root: Path) -> Path:
    """The evidence root: OTSAFETY_ARTIFACTS if set, else the main checkout's."""
    override = settings().artifacts
    if override is not None:
        return override.resolve()
    main = parse_records(root)[0]
    if "bare" in main:
        raise RuntimeError(
            f"the main repository at {main['worktree']} is bare; it has no working "
            "tree in which to record evidence"
        )
    return Path(main["worktree"]).resolve() / ARTIFACTS_DIR


def main() -> int:
    """Print the shared evidence root, as the only line of output."""
    print(artifacts_root(REPO_ROOT), flush=True)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
