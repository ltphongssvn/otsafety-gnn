# tooling/src/otsafety_tooling/git/keepalive.py
"""A push survives its own gate, because the transport is kept alive through it.

GIT OPENS THE CONNECTION BEFORE PRE-PUSH RUNS. It sends the packfile only after
the hook returns, so the socket sits idle for the whole gate -- 372 seconds
here. GitHub hangs up well before that, and the push dies after paying the full
cost, reporting a message that reads like a rejection.

THE HOOK CANNOT FIX ITSELF. Setting GIT_SSH_COMMAND inside pre-push does nothing
for a transport already open; the setting belongs on the clone, before any push
begins. core.sshCommand is where it goes, and every worktree of a clone shares
that configuration.

AND IT MUST TRAVEL. This exact failure has recurred across several repositories
for months because the fix lived in one operator's uncommitted config. setup
stamps it, so a fresh clone is protected on its first push rather than on the
day someone remembers.

THE TWO FAILURES LOOK IDENTICAL AND ARE NOT. A declined hook and a dropped
transport both exit non-zero with no confirmation line, and the reassuring
reading -- the hook rejected it -- is the wrong one when the gate has just
passed. Asking the remote is what settles it.
"""

from __future__ import annotations

from pathlib import Path

from otsafety_tooling.git.env import git
from otsafety_tooling.paths import REPO_ROOT

# THE GATE'S OWN BOUND, from scripts/check_all.py: no gate may exceed it, so the
# keepalive must outlast it. Ten minutes.
BOUND = 600
# TWENTY SECONDS IS FREQUENT ENOUGH FOR AN IDLE LIMIT MEASURED IN MINUTES and
# infrequent enough to be invisible; the count is what carries it past the gate.
INTERVAL = 20
COUNT = 90

COMMAND = f"ssh -o ServerAliveInterval={INTERVAL} -o ServerAliveCountMax={COUNT}"


def configured(root: Path = REPO_ROOT) -> bool:
    """Whether this clone carries the keepalive on its ssh command."""
    # --get-all over a name that may be unset returns nothing rather than
    # failing, where --get exits non-zero and git() would raise.
    found = git("config", "--get-all", "core.sshCommand", cwd=root).stdout
    return "ServerAliveInterval" in found


def stamp(root: Path = REPO_ROOT) -> str:
    """Put the keepalive on the clone, where every worktree inherits it."""
    git("config", "core.sshCommand", COMMAND, cwd=root)
    return COMMAND


def landed(ref: str, root: Path = REPO_ROOT) -> bool:
    """Whether the ref actually reached the remote.

    THE QUESTION THAT TELLS THE TWO FAILURES APART. A declined hook and a
    dropped transport end the same way on this side; only the remote knows
    which happened, and asking it costs one round trip.
    """
    local = git("rev-parse", ref, cwd=root).stdout.strip()
    remote = git("ls-remote", "origin", ref, cwd=root).stdout.split()
    return bool(remote) and remote[0] == local


def main() -> int:
    """Stamp the keepalive, and say what was put where."""
    from pydantic import BaseModel, ConfigDict

    from otsafety_tooling.cli import note, result

    class Stamped(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid")

        command: str
        seconds: int

    command = stamp()
    note(f"core.sshCommand = {command}")
    return result(
        "git:keepalive",
        "success",
        "keepalive_stamped",
        f"the transport survives {INTERVAL * COUNT}s of gate",
        Stamped(command=command, seconds=INTERVAL * COUNT),
    )


if __name__ == "__main__":
    raise SystemExit(main())
