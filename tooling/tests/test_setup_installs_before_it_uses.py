# tooling/tests/test_setup_installs_before_it_uses.py
"""Setup installs before it uses, and the order is what is proved (G.72).

I PUT THE KEEPALIVE AT THE TOP OF SETUP, above the sync that installs the
package it calls. Every new worktree then failed halfway -- virtualenv created,
package absent -- and the retry was refused by the very directory the failure
had left behind. One line, and worktree creation was broken for the repository.

THE TEST IS WHY IT SHIPPED. It asserted "keepalive" in the task body, which is
true wherever the line sits. 2026 practice names this exact trap: an ordering
test that checks presence rather than position passes even when the install step
is absent entirely, so it restores the failure it exists to prevent.

THE RULE IS THE ONE PACKAGE MANAGERS STATE: dependencies are not on disk when an
early step runs, so it cannot import any of them; work that needs them belongs
after the install.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.72")

# WHAT INSTALLS THE PACKAGE, and what cannot run before it.
INSTALL = "uv sync"


def _setup() -> str:
    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["setup"]
    return task.run if isinstance(task.run, str) else "\n".join(task.run)


def test_setup_installs_the_package() -> None:
    """The positive control the ordering test needs.

    WITHOUT IT THE ORDER PROVES NOTHING: a missing install reads as position
    -1, which sorts before everything, so every ordering assertion passes at
    the moment the install disappears.
    """
    assert INSTALL in _setup(), "setup no longer installs the package"


def test_nothing_runs_the_package_before_it_is_installed() -> None:
    """Every call to this repository's own modules comes after the sync."""
    body = _setup()
    install_at = body.index(INSTALL)
    early = [
        line.strip()
        for line in body[:install_at].splitlines()
        if "otsafety_tooling" in line and not line.strip().startswith("#")
    ]
    assert early == [], f"setup calls the package before installing it: {early}"


def test_the_keepalive_is_stamped_after_the_install() -> None:
    """The specific line that broke it, by position rather than presence."""
    body = _setup()
    assert "keepalive" in body, "setup no longer stamps the keepalive"
    assert body.index(INSTALL) < body.index("keepalive"), (
        "the keepalive is stamped before the package that provides it is installed"
    )
