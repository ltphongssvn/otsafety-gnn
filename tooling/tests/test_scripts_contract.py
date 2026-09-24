# tooling/tests/test_scripts_contract.py
"""The standalone scripts speak in envelopes too (G.42).

WHY SEPARATELY. scripts/ runs BEFORE anything is installed -- the bootstrap calls
it on a bare machine -- so these three import only the standard library and cannot
use the contract model. Each builds the same command-outcome/v1 envelope as plain
data, and this test validates every one THROUGH the model, so a drifting shape
fails here rather than in a caller.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from otsafety_tooling.contracts.outcome import CommandOutcome
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.42")

SCRIPTS = ("bootstrap_toolchain", "build_arch_onepager", "check_site")


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", SCRIPTS)
def test_the_script_can_build_its_envelope(name: str) -> None:
    """Each script emits the contract, and the model is what says so."""
    module = _load(name)
    assert hasattr(module, "emit"), f"{name}.py has no emit()"
    assert module.CONTRACT == "command-outcome/v1"


def test_the_bootstrap_reports_what_it_decided(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bootstrap run names its platform, its destination and every tool decision."""
    module = _load("bootstrap_toolchain")
    # AN UNKNOWN ARGUMENT IS REFUSED, where it used to be taken as a destination.
    code = module.main([str(tmp_path / "bin"), "--plan-only"])
    envelope = CommandOutcome.model_validate_json(capsys.readouterr().out)
    assert code == 2 and envelope.command == "bootstrap"
    assert envelope.code == "usage"


def test_the_site_check_reports_each_assertion(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The site check's PASS/FAIL lines become data; the lines stay on stderr."""
    module = _load("check_site")

    def fake(url: str) -> tuple[int, str]:
        """The module's own network seam: no raising=False, which hid a wrong name."""
        if url.endswith("/results"):
            return (308, url + "/")
        return (200, '<b data-verdict="pass"></b>')

    monkeypatch.setattr(module, "status", fake)
    code = module.main(["https://example.invalid"])
    envelope = CommandOutcome.model_validate_json(capsys.readouterr().out)
    assert envelope.command == "site:check"
    assert (code == 0) == (envelope.outcome == "success")
    checks = envelope.data["checks"]
    assert isinstance(checks, list) and checks
