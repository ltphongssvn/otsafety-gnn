# tooling/tests/conftest.py
"""Suite-wide isolation from the ambient git repository.

THIS EXISTS BECAUSE, IN cscie103-olap-oltp, A TEST COMMITTED TO THE REAL
REPOSITORY. A fixture ran `git commit` with cwd set to a scratch repo, and the
commit landed on the actual feature branch: GIT_DIR, GIT_WORK_TREE and
GIT_INDEX_FILE outrank the working directory, and git exports them while a hook
runs. The pre-push hook runs this suite, so pushing is what triggers it.

AUTOUSE, BECAUSE OPT-IN IS WHAT FAILED. The variables are removed here, once,
for every test, so a subprocess that inherits the environment is safe by
default and no fixture author has to know any of this.

monkeypatch RATHER THAN os.environ: it reverses every change after the test,
even when an assertion raises.

THE NAMES COME FROM scrubbed_env(), NOT FROM A LIST, so this cannot disagree
with the module production code depends on.
"""

import os

import pytest

from otsafety_tooling.git.env import scrubbed_env


def _routing_names() -> set[str]:
    """Whatever scrubbed_env() removes, derived by comparison."""
    return set(os.environ) - set(scrubbed_env())  # noqa: TID251


@pytest.fixture(autouse=True)
def _isolate_from_the_ambient_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove git's routing variables for the duration of every test."""
    for name in _routing_names():
        monkeypatch.delenv(name, raising=False)
