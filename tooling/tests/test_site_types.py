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
from pathlib import Path

import pytest

from otsafety_tooling.contracts.files import read_json, read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.site_package import SitePackage
from otsafety_tooling.contracts.toolchain import Toolchain
from otsafety_tooling.paths import REPO_ROOT

# THIS FILE PROVES G.37: the claim the requirement matrix joins on.
pytestmark = pytest.mark.requirement("G.37")

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


def test_every_site_dependency_is_pinned_exactly() -> None:
    """A RANGE LETS TWO MACHINES BUILD DIFFERENT SITES. Three of the five runtime
    dependencies carried carets while every devDependency was pinned, so the rule
    was applied to half the file."""
    for name, version in {**SITE.dependencies, **SITE.dev_dependencies}.items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{name} is {version}, not a pin"


def test_the_site_declares_no_framework_it_does_not_use() -> None:
    """REACT WAS DECLARED FOR NOTHING: no .tsx file and no client: directive uses it,
    and the integration drags in vite:react-babel, whose esbuild and
    optimizeDeps.esbuildOptions options Vite 8 deprecates. Three warnings on every
    build, for a framework the site never renders with."""
    declared = {**SITE.dependencies, **SITE.dev_dependencies}
    for absent in ("@astrojs/react", "react", "react-dom"):
        assert absent not in declared, f"{absent} is declared but nothing uses it"
    source = REPO_ROOT / "apps" / "site" / "src"

    def uses_an_island(path: Path) -> bool:
        if not path.is_file():
            return False
        if path.suffix == ".tsx":
            return True
        return "client:" in path.read_text(encoding="utf-8", errors="replace")

    used = [path.relative_to(REPO_ROOT) for path in source.rglob("*") if uses_an_island(path)]
    assert used == [], f"these use a framework island: {used}"


def test_the_site_declares_its_own_jsx_element_type() -> None:
    """THE SITE OWNS ITS JSX TYPE, rather than a framework it does not render with.

    Astro defines astroHTML.JSX.Element as HTMLElement | any, and resolves that any
    through whichever framework supplies JSX types. React was the only one here, so
    removing it left every .astro template returning an unresolvable type and
    typescript-eslint reported fourteen no-unsafe-return errors -- the caveat
    eslint-plugin-astro documents for a project with no framework present.

    It passed locally only because bun install left React in node_modules; a clean
    install, which is what CI does, reproduced all fourteen.
    """
    declaration = REPO_ROOT / "apps" / "site" / "src" / "jsx.d.ts"
    assert declaration.is_file(), "the site declares JSX.Element itself"
    text = declaration.read_text(encoding="utf-8")
    assert 'import "astro/astro-jsx"' in text
    assert "type Element = HTMLElement" in text
