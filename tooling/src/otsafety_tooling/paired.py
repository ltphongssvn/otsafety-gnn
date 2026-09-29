# tooling/src/otsafety_tooling/paired.py
"""Show that a rule refuses something, rather than that its tool ran.

A BAN PROVED BY A FILE EXISTING IS INSPECTION. Control practice separates
checking from validating: checking confirms a thing is there, validating
confirms it works, and inquiry alone is insufficient evidence that a control
operates. Nineteen completed steps here claim to refuse something and rest on a
file or a task being present.

THE PAIRED NEGATIVE, which is 2026's name for the answer: run the tool over a
deliberately VIOLATING fixture and require it to refuse, then over a CLEAN one
and require it to pass. A check with only the second half is a tautology.

A NON-ZERO EXIT IS NOT THE RULE FIRING. A tool reports malformed input, a
missing file and an unmatched glob with the same status it uses for a real
violation, so the rule's own name must appear in what the tool said -- otherwise
the harness has proved only that something went wrong.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from otsafety_tooling.git.env import inherited_env
from otsafety_tooling.paths import REPO_ROOT


@dataclass(frozen=True)
class Verdict:
    """What the tool did on each fixture, and why that reading was taken."""

    fired_on_the_violation: bool
    silent_on_the_clean_one: bool
    why: str

    @property
    def holds(self) -> bool:
        """The rule refuses what it bans and accepts what it does not."""
        return self.fired_on_the_violation and self.silent_on_the_clean_one


def _run(command: Sequence[str], text: str) -> tuple[int, str]:
    finished = subprocess.run(  # noqa: S603
        list(command),
        input=text,
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=inherited_env(),
        timeout=120,
    )
    return finished.returncode, finished.stdout + finished.stderr


def refuses(command: Sequence[str], *, violating: str, clean: str, naming: str) -> Verdict:
    """Whether `command` refuses `violating` BY THE NAMED RULE, and accepts `clean`."""
    bad_code, bad_said = _run(command, violating)
    good_code, good_said = _run(command, clean)

    fired = bad_code != 0 and naming in bad_said
    silent = good_code == 0

    why = (
        f"violating: exit {bad_code}, "
        f"{'names' if naming in bad_said else 'does not name'} {naming}; "
        f"clean: exit {good_code}"
    )
    if bad_code != 0 and naming not in bad_said:
        why += f" -- refused for another reason: {bad_said.strip()[:120]}"
    if good_code != 0:
        why += f" -- the clean fixture was refused too: {good_said.strip()[:120]}"
    return Verdict(fired_on_the_violation=fired, silent_on_the_clean_one=silent, why=why)
