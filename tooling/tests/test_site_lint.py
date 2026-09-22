# tooling/tests/test_site_lint.py
"""The site's ESLint policy runs as a floor and a ceiling, like every other policy here."""

from __future__ import annotations

from otsafety_tooling.contracts.files import read_json, read_toml, read_yaml
from otsafety_tooling.contracts.lefthook_config import LefthookConfig
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.site_package import SitePackage
from otsafety_tooling.paths import REPO_ROOT


def test_the_site_lints_with_its_own_script() -> None:
    site = read_json(REPO_ROOT / "apps" / "site" / "package.json", SitePackage)
    assert site.scripts["lint"] == "eslint ."
    task = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks["site:lint"]
    assert "bun --bun run --cwd apps/site lint" in "\n".join(task.scripts)


def test_the_floor_runs_it_on_every_commit() -> None:
    hook = read_yaml(REPO_ROOT / "lefthook.yml", LefthookConfig).pre_commit
    assert hook is not None and any(job.run == "mise run site:lint" for job in hook.jobs)
