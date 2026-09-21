# tooling/tests/test_site_deploy.py
"""How the site is served on Railway, asserted before any of it exists.

BUILT HERE, UPLOADED THERE. /evidence and /results are computed from .artifacts/
when the site is built, and .artifacts/ is ignored by git. A build on Railway's
builder would have no evidence and publish both pages empty, so the site is built
where the evidence lives and only its output is uploaded.

A DOCKERFILE, NOT BUILDER CONFIG. A 2026 Railway template records why: build
instructions written for one builder stop being read when the platform switches
to another, and Hugo's nixpacks.toml broke silently when Railway moved to
Railpack. A Dockerfile is read the same way by every builder.

NOT AN SPA. Every Railway static-site example ends `try_files {path} /index.html`,
the single-page-app fallback. This site's pages are separate HTML files, so that
line would answer every mistyped URL with the home page and a 200: a broken link
would look like a working page. It gets a real 404.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_json, read_toml
from otsafety_tooling.contracts.mise_config import MiseConfig
from otsafety_tooling.contracts.railway_config import RailwayConfig
from otsafety_tooling.contracts.toolchain import Toolchain
from otsafety_tooling.paths import REPO_ROOT

DEPLOY = REPO_ROOT / "deploy" / "site"
AMD64 = "sha256:040e9f7480b80b6d4a7e5013a21159b950a63dcbdb956e38abe2387fb28d9ec0"


def _read(name: str) -> str:
    path = DEPLOY / name
    if not path.is_file():
        pytest.fail(f"no {name} at {path}")
    return path.read_text(encoding="utf-8")


def _directives(text: str) -> str:
    """The configuration with comments removed.

    The Caddyfile explains in a comment why the SPA fallback is absent, quoting
    it; checking raw text failed on that explanation. Tests judge directives.
    """
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _toolchain() -> Toolchain:
    return read_json(REPO_ROOT / "toolchain.json", Toolchain)


def test_the_serving_image_is_declared_beside_every_other_executable() -> None:
    entry = _toolchain().site_image
    assert entry.platform == "linux/amd64"
    assert entry.digest == AMD64, "the amd64 manifest, never the multi-platform index"
    assert "2.11.4" in entry.reference


def test_the_dockerfile_pins_the_same_digest() -> None:
    assert AMD64 in _read("Dockerfile")


def test_caddy_leaves_tls_to_railway_and_listens_on_its_port() -> None:
    """Railway terminates TLS; Caddy obtaining its own certificates would fail."""
    caddyfile = _directives(_read("Caddyfile"))
    assert "auto_https off" in caddyfile
    assert "admin off" in caddyfile
    assert "{$PORT" in caddyfile
    assert "trusted_proxies" in caddyfile


def test_a_missing_page_is_a_404_not_the_home_page() -> None:
    """The SPA fallback would turn every broken link into a working-looking page."""
    caddyfile = _directives(_read("Caddyfile"))
    assert "try_files {path} /index.html" not in caddyfile
    assert "handle_errors" in caddyfile
    assert (REPO_ROOT / "apps/site/src/pages/404.astro").is_file(), "no 404 page to serve"


def test_railway_is_told_to_use_the_dockerfile() -> None:
    """Config as code, rather than relying on detection by whichever builder runs."""
    config = RailwayConfig.model_validate_json(_read("railway.json"))
    assert config.build.builder == "DOCKERFILE"
    assert config.deploy.healthcheck_path == "/"


PROJECT = "1e5d094a-e1f5-4b16-943a-9a499fc29576"
SERVICE = "979ff174-ffc2-444f-a91d-54175c55d3a2"


def _deploy_task() -> str:
    tasks = read_toml(REPO_ROOT / "mise.toml", MiseConfig).tasks
    assert "deploy:site" in tasks, "no deploy:site task"
    return "\n".join(tasks["deploy:site"].scripts)


def test_the_upload_is_the_stage_and_nothing_is_dropped() -> None:
    """Both flags fail SILENTLY when absent, which is why they are asserted.

    build/ is ignored by git, so without --no-gitignore the stage uploads empty;
    without --path-as-root the archive root is the project directory and the
    Dockerfile is not at its root. Read from `railway up --help` for v5.54.1.
    """
    run = _deploy_task()
    assert "--no-gitignore" in run
    assert "--path-as-root" in run
    assert "build/deploy-site" in run


def test_the_target_is_explicit_not_this_machines_link() -> None:
    """railway init links a directory in ~/.railway on ONE machine only."""
    run = _deploy_task()
    assert PROJECT in run
    assert SERVICE in run


def test_a_deploy_names_the_commit_and_is_smoke_tested_first() -> None:
    run = _deploy_task()
    assert "site:smoke" in run, "an image that has not served a request is not deployed"
    assert "git status --porcelain" in run, "a dirty tree would deploy code no commit describes"
    assert "-m " in run, "the deployment carries the commit it came from"
