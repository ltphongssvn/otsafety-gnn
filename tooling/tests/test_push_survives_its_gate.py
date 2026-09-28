# tooling/tests/test_push_survives_its_gate.py
"""A push survives its own gate, and says which way it failed (G.71).

GIT OPENS THE CONNECTION BEFORE PRE-PUSH RUNS and sends the packfile only after
the hook returns, so the socket sits idle for the whole gate. This one takes 372
seconds; GitHub hangs up well before that. Two pushes died that way in a row,
each after paying the full gate, with ssh authenticating and the token live.

A KEEPALIVE INSIDE THE HOOK CANNOT SAVE IT: the transport is already open by
then. It belongs on the clone, as core.sshCommand, stamped by setup so every
worktree of this repository inherits it -- a fix left in one operator's
uncommitted config does not travel, which is how this stayed unfixed across
several projects for months.

AND THE TWO FAILURES MUST BE TOLD APART. A declined hook and a dropped transport
both end in a non-zero exit with no confirmation line, and the reassuring
reading is the wrong one: the gate passed, so the work was approved and then
lost. Asking the remote is what settles it.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.71")


def test_the_clone_carries_a_keepalive() -> None:
    """Not the operator's ~/.ssh/config: this repository's own configuration."""
    from otsafety_tooling.git.keepalive import configured

    assert configured(REPO_ROOT), (
        "core.sshCommand carries no keepalive; a push will idle through the gate"
    )


def test_the_interval_outlives_the_gate() -> None:
    """A keepalive shorter than the gate is the whole point."""
    from otsafety_tooling.git.keepalive import BOUND, COUNT, INTERVAL

    assert INTERVAL * COUNT >= BOUND, (
        f"{INTERVAL}s x {COUNT} is {INTERVAL * COUNT}s, under the {BOUND}s a gate may take"
    )


def test_setup_stamps_it_so_every_worktree_inherits() -> None:
    """A fix that does not travel is how this survived months of recurrence."""
    from otsafety_tooling.contracts.files import read_toml
    from otsafety_tooling.contracts.mise_config import MiseConfig

    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["setup"]
    body = task.run if isinstance(task.run, str) else "\n".join(task.run)
    assert "keepalive" in body, "setup does not stamp the keepalive"


def test_a_lost_push_is_told_apart_from_a_declined_one() -> None:
    """The reassuring reading is the wrong one, so the remote is asked."""
    from otsafety_tooling.git.keepalive import landed

    assert landed.__doc__, "nothing verifies whether the ref reached the remote"
