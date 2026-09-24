# tooling/src/otsafety_tooling/git/ghcli.py
"""One place that knows what a gh exit code means.

WHY THIS MODULE EXISTS
Called with check=True, an authentication failure surfaces as
`CalledProcessError: ... returned non-zero exit status 4` -- a traceback that
reads like whatever the caller was asking about (a missing ruleset, a missing
pull request) and is not. On FAS OnDemand gh is also git's credential helper,
so an expired login must say so plainly.

So exit 4 is named HERE and nowhere else. A second caller adds an import, not a
second definition.

WHY A DISTINCT EXCEPTION RATHER THAN A BETTER MESSAGE
A caller can decide: fail when the environment promised credentials, report
`unknown` when it did not, without parsing a string.

Ported from cscie103-olap-oltp (src/cscie103_olap_oltp/git/ghcli.py).
"""

from __future__ import annotations

import subprocess

from pydantic import BaseModel, ValidationError

from otsafety_tooling.git.env import scrubbed_env

# gh's DOCUMENTED CODE FOR "NOT AUTHENTICATED", named once.
NOT_AUTHENTICATED = 4


class GhError(RuntimeError):
    """gh failed for a reason the caller may want to distinguish."""


class NotAuthenticatedError(GhError):
    """gh has no usable credentials.

    On a laptop gh reads a keyring; on FAS OnDemand a hosts file under
    GH_CONFIG_DIR; on a runner GH_TOKEN. None is ambient state this repository
    controls, so its absence is a first-class outcome rather than a crash.
    """


def gh(*args: str) -> str:
    """Run gh and return stdout, translating exit codes into meaning.

    S603 IS SUPPRESSED NARROWLY: `*args` makes the list computed; call sites
    pass literal subcommands and there is no shell.
    """
    result = subprocess.run(  # noqa: S603
        ["gh", *args],  # noqa: S607
        env=scrubbed_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == NOT_AUTHENTICATED:
        raise NotAuthenticatedError(
            "gh is not authenticated (exit 4).\n"
            "  laptop / Lightning:  gh auth login\n"
            "  FAS OnDemand:        gh auth login --git-protocol https --web\n"
            "  CI:                  set GH_TOKEN on the step that runs the gate\n"
            f"  gh said: {result.stderr.strip() or '(nothing)'}"
        )

    if result.returncode != 0:
        raise GhError(
            f"gh {' '.join(args)} failed with exit {result.returncode}: "
            f"{result.stderr.strip() or '(no stderr)'}"
        )

    return result.stdout


def gh_json[M: BaseModel](model: type[M], *args: str) -> M:
    """Run gh and validate its JSON into a model, naming the command if it does not fit.

    VALIDATED AT THE BOUNDARY IT READS FROM. This returned Any from json.loads, and
    its caller re-checked the type by hand before validating. Pydantic parses and
    validates in one step, so untyped gh output never reaches a caller.
    """
    raw = gh(*args)
    try:
        return model.model_validate_json(raw)
    except ValidationError as error:
        raise GhError(
            f"gh {' '.join(args)} returned JSON that does not fit {model.__name__}: {error}"
        ) from error
