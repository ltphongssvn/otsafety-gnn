#!/usr/bin/env python3
# 6.7: proves this step of the plan.
# scripts/check_all.py
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

import json
import re
import subprocess
import sys
from collections.abc import Mapping

# THE PAYLOAD IS BUILT AS PLAIN DATA, not through a model: scripts/ runs BEFORE
# anything is installed -- the bootstrap calls it -- so it imports only the
# standard library. The shape is the same command-outcome/v1 every command emits,
# and the aggregate's own test validates it through the contract.
CONTRACT = "command-outcome/v1"
ENVELOPE = re.compile(
    r'"contract":\s*"command-outcome/v1".*?"outcome":\s*"(?P<outcome>[a-z]+)".*?'
    r'"code":\s*"(?P<code>[a-z][a-z0-9_]*)"'
)

# WHERE A GATE CAN RUN, NOT WHERE IT MUST. The first version marked the browser
# and container gates CI, so a default local run skipped the two things this
# laptop is best placed to check -- it has Docker and Chromium. Only Nix is
# genuinely local-only: the runner has none, which is why mise.ood.toml exists.
#
# SLOW IS A SEPARATE AXIS FROM WHERE. --fast exists for the hooks, so a slow gate
# is excluded by being slow rather than by pretending it cannot run here.
ANYWHERE, LOCAL = "anywhere", "local"

# (name, command, where, fast)
# TEN MINUTES IS GENEROUS FOR THE SLOWEST GATE HERE -- nix flake check builds every
# pinned tool -- and far short of the forty-one minutes a registry fetch took.
BOUND = 600

GATES: list[tuple[str, list[str], str, bool]] = [
    # FIRST: every later gate runs on tools proved to be the pinned binaries.
    ("toolchain:verify", ["mise", "run", "toolchain:verify"], ANYWHERE, True),
    ("lint", ["mise", "run", "lint"], ANYWHERE, True),
    ("types", ["mise", "run", "types"], ANYWHERE, True),
    ("test", ["mise", "run", "test"], ANYWHERE, True),
    # Needs bun, Chromium and a built site: minutes, not seconds.
    ("site:types", ["mise", "run", "site:types"], ANYWHERE, False),
    ("site:lint", ["mise", "run", "site:lint"], ANYWHERE, False),
    ("policy", ["mise", "run", "policy"], ANYWHERE, False),
    ("test:e2e", ["mise", "run", "test:e2e"], ANYWHERE, False),
    # Needs Docker, and pulls a pinned image on a cold machine.
    ("pdf:render", ["mise", "run", "pdf:render"], ANYWHERE, False),
    ("nix flake", ["mise", "run", "nix:flake-check"], LOCAL, False),
]


# THE PAYLOAD IS JSON, AND THIS SCRIPT IS STANDARD LIBRARY ONLY: the contract
# model may not be installed where it runs, so the payload cannot be a Pydantic
# model. Mapping[str, object] is the honest stdlib type -- object rather than Any,
# so nothing is exempted from checking, and Mapping rather than dict because dict
# is INVARIANT in its value type: dict[str, str] is not a dict[str, object], which
# is what made an earlier alias need widening at every call site.
def emit(outcome: str, code: str, message: str, data: Mapping[str, object]) -> int:
    """The envelope on stdout, and the exit code the outcome carries."""
    envelope = {
        "contract": CONTRACT,
        "command": "check",
        "outcome": outcome,
        "code": code,
        "message": message,
        "data": data,
    }
    sys.stdout.write(json.dumps(envelope) + "\n")
    return {"success": 0, "failed": 1, "refused": 2}[outcome]


def inner_outcome(text: str) -> dict[str, str] | None:
    """A gate's own envelope, when it emitted one: its verdict, not its prose."""
    # NO RAW PARSING, EVEN HERE. scripts/ imports only the standard library, so it
    # cannot use the contract model; it reads the two fields it needs from the line
    # with a pattern that either matches the shape or does not, and never guesses.
    verdict: dict[str, str] | None = None
    for line in text.splitlines():
        found = ENVELOPE.search(line.strip())
        if found:
            verdict = {"outcome": found["outcome"], "code": found["code"]}
    return verdict


def main(argv_in: list[str] | None = None) -> int:
    argv = set(sys.argv[1:] if argv_in is None else argv_in)
    if "--fast" in argv:
        selected = [g for g in GATES if g[3]]
    elif "--ci" in argv:
        selected = [g for g in GATES if g[2] == ANYWHERE]
    else:
        selected = list(GATES)

    chosen = {name for name, _, _, _ in selected}
    skipped = [name for name, _, _, _ in GATES if name not in chosen]
    if skipped:
        print(f"skipping: {', '.join(skipped)}", file=sys.stderr)

    results: list[tuple[str, bool, str]] = []
    gates: list[Mapping[str, object]] = []

    for name, command, _, _ in selected:
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=BOUND
            )
            passed = completed.returncode == 0
            output = (completed.stdout + completed.stderr).strip()
        except subprocess.TimeoutExpired as expired:
            passed = False
            stdout = expired.stdout or b""
            partial = stdout.decode() if isinstance(stdout, bytes) else stdout
            output = (
                f"{name} exceeded {BOUND}s and was stopped. A gate that hangs holds the whole "
                f"check and prints nothing while it does.\n{partial.strip()}"
            )
            completed = subprocess.CompletedProcess(command, 124, partial, "")
        results.append((name, passed, output))
        # THE GATE'S OWN VERDICT, CARRIED: it already produced one, so the
        # aggregate keeps it rather than discarding it into a text blob.
        gates.append({"name": name, "passed": passed, "outcome": inner_outcome(completed.stdout)})
        print(f"{'PASS' if passed else 'FAIL'}  {name}", file=sys.stderr, flush=True)

    failed = [(name, output) for name, passed, output in results if not passed]
    if failed:
        for name, output in failed:
            print(f"\n{'=' * 70}\nFAILED: {name}\n{'=' * 70}", file=sys.stderr)
            print(output, file=sys.stderr)
        names = [name for name, _ in failed]
        print(
            f"\n{len(failed)} of {len(results)} gates failed: {', '.join(names)}",
            file=sys.stderr,
        )
        return emit(
            "refused",
            "gates_failed",
            f"{len(failed)} of {len(results)} gates failed: {', '.join(names)}",
            {"gates": gates, "failed": names},
        )

    print(f"\nall {len(results)} gates passed", file=sys.stderr)
    return emit(
        "success",
        "gates_passed",
        f"all {len(results)} gates passed",
        {"gates": gates, "failed": []},
    )


if __name__ == "__main__":
    raise SystemExit(main())
