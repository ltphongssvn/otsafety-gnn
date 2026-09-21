#!/usr/bin/env python3
"""Run every gate, report every result, exit nonzero if any failed.

PORTED FROM cscie103-data-engineering, WHOSE COMMIT EXPLAINS WHY IT EXISTS:
`check` was a mise task with depends, and mise runs dependencies in PARALLEL,
reporting failure as soon as one fails. Observed there: test failed at 1.4s and
types never reported at all. "A gate whose result is never printed is
indistinguishable from one that passed."

THIS SESSION IS THE PROOF. Gates were run by hand in sequence -- lint, then fmt,
then lint again, then types, then test -- finding one failure per round trip.
Worse, MLflow's seven tests skipped on every CI run for a whole session while the
summary line read green, because nothing installed the extra. 2026 practice names
that exactly: "a skipped job and a passing job are indistinguishable".

NOT fail-fast, DELIBERATELY. Fail-fast minimises wasted work after a decisive
failure; running everything maximises the diagnostic information from one commit.
A quality gate wants the second.

THREE MODES, NOT TWO. cscie103 used a boolean ci_only, which assumes every
expensive gate belongs to CI. Here nix flake check can ONLY run locally -- the
runner has no Nix, MISE_ENV=ood exists for that -- while Docker rendering and the
browser tests only run where those are installed. A boolean would have to lie
about one of them.
"""

from __future__ import annotations

import subprocess
import sys

# WHERE A GATE CAN RUN, NOT WHERE IT MUST. The first version marked the browser
# and container gates CI, so a default local run skipped the two things this
# laptop is best placed to check -- it has Docker and Chromium. Only Nix is
# genuinely local-only: the runner has none, which is why mise.ood.toml exists.
#
# SLOW IS A SEPARATE AXIS FROM WHERE. --fast exists for the hooks, so a slow gate
# is excluded by being slow rather than by pretending it cannot run here.
ANYWHERE, LOCAL = "anywhere", "local"

# (name, command, where, fast)
GATES: list[tuple[str, list[str], str, bool]] = [
    ("lint", ["mise", "run", "lint"], ANYWHERE, True),
    ("types", ["mise", "run", "types"], ANYWHERE, True),
    ("test", ["mise", "run", "test"], ANYWHERE, True),
    # Needs bun, Chromium and a built site: minutes, not seconds.
    ("test:e2e", ["mise", "run", "test:e2e"], ANYWHERE, False),
    # Needs Docker, and pulls a pinned image on a cold machine.
    ("pdf:render", ["mise", "run", "pdf:render"], ANYWHERE, False),
    ("nix flake", ["mise", "run", "nix:flake-check"], LOCAL, False),
]


def main() -> int:
    argv = set(sys.argv[1:])
    if "--fast" in argv:
        selected = [g for g in GATES if g[3]]
    elif "--ci" in argv:
        selected = [g for g in GATES if g[2] == ANYWHERE]
    else:
        selected = list(GATES)

    chosen = {name for name, _, _, _ in selected}
    skipped = [name for name, _, _, _ in GATES if name not in chosen]
    if skipped:
        print(f"skipping: {', '.join(skipped)}\n")

    results: list[tuple[str, bool, str]] = []

    for name, command, _, _ in selected:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
        passed = completed.returncode == 0
        output = (completed.stdout + completed.stderr).strip()
        results.append((name, passed, output))
        print(f"{'PASS' if passed else 'FAIL'}  {name}", flush=True)

    failed = [(name, output) for name, passed, output in results if not passed]
    if failed:
        for name, output in failed:
            print(f"\n{'=' * 70}\nFAILED: {name}\n{'=' * 70}", file=sys.stderr)
            print(output, file=sys.stderr)
        print(
            f"\n{len(failed)} of {len(results)} gates failed: "
            f"{', '.join(name for name, _ in failed)}",
            file=sys.stderr,
        )
        return 1

    print(f"\nall {len(results)} gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
