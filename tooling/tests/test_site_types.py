# tooling/tests/test_site_types.py
"""The site's TypeScript is type-checked, against the runtime that runs it.

WHY THIS EXISTS. The site installed no TypeScript, so Astro stripped its types
and nothing ever checked them: every z.infer type derived from the generated Zod
was declared and never verified. The first run found 11 errors, in the two files
that read records from disk, all from missing runtime definitions. The runtime is
bun, so the definitions are @types/bun, at the version toolchain.json pins.
The behavioural probe lives in apps/site/tests, where the site is installed.
"""

from __future__ import annotations

import re

from otsafety_tooling.contracts.files import read_json, read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.site_package import SitePackage
from otsafety_tooling.contracts.toolchain import Toolchain
from otsafety_tooling.paths import REPO_ROOT

SITE = read_json(REPO_ROOT / "apps" / "site" / "package.json", SitePackage)


def test_the_task_runs_the_sites_own_check_script() -> None:
    assert SITE.scripts["check"] == "astro check --minimumFailingSeverity hint"
    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["site:types"]
    assert "bun run --cwd apps/site check" in "\n".join(task.scripts)


def test_the_types_describe_the_runtime_that_runs_the_code() -> None:
    assert (
        SITE.dev_dependencies["@types/bun"]
        == read_json(REPO_ROOT / "toolchain.json", Toolchain).bun.version
    )


def test_typescript_and_its_checker_are_pinned_exactly() -> None:
    for name in ("typescript", "@astrojs/check", "@types/bun"):
        assert re.fullmatch(r"\d+\.\d+\.\d+", SITE.dev_dependencies[name]), (
            f"{name} is a range, not a pin"
        )
