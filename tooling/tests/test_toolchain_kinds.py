# tooling/tests/test_toolchain_kinds.py
"""A toolchain artifact is an archive with a folder, or a bare binary without one.

Regal ships bare binaries, which toolchain.json, the flake and the bootstrap could
not express: all three assumed an archive unpacking into a declared folder. An
artifact now declares its kind, and the pairing is enforced: an archive must
name its folder, a binary must not, and a binary installs exactly one file.
"""

from __future__ import annotations

import hashlib
import importlib.util
import stat
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from otsafety_tooling.contracts.files import read_json
from otsafety_tooling.contracts.toolchain import BinaryTool, Toolchain
from otsafety_tooling.paths import REPO_ROOT

DIGEST = "0" * 64


def _tool(**artifact: object) -> dict[str, object]:
    base: dict[str, object] = {"url": "https://example.invalid/x", "sha256": DIGEST}
    return {
        "version": "1.0.0",
        "artifacts": {"x86_64-linux": {**base, **artifact}},
        "binaries": ["x"],
    }


def test_an_archive_must_name_its_folder() -> None:
    with pytest.raises(ValidationError):
        BinaryTool.model_validate(_tool())


def test_a_binary_must_not_name_a_folder() -> None:
    with pytest.raises(ValidationError):
        BinaryTool.model_validate(_tool(kind="binary", dir="."))


def test_a_binary_installs_exactly_one_file() -> None:
    with pytest.raises(ValidationError):
        BinaryTool.model_validate({**_tool(kind="binary"), "binaries": ["a", "b"]})


def test_conftest_is_an_archive_and_regal_a_binary() -> None:
    chain = read_json(REPO_ROOT / "toolchain.json", Toolchain)
    assert {a.kind for a in chain.conftest.artifacts.values()} == {"archive"}
    assert {a.kind for a in chain.regal.artifacts.values()} == {"binary"}


def test_the_bootstrap_installs_a_bare_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location(
        "bootstrap", REPO_ROOT / "scripts" / "bootstrap_toolchain.py"
    )
    assert spec is not None and spec.loader is not None
    bootstrap = importlib.util.module_from_spec(spec)
    # A dataclass looks up its module in sys.modules while it is built.
    monkeypatch.setitem(sys.modules, spec.name, bootstrap)
    spec.loader.exec_module(bootstrap)
    payload = tmp_path / "published"
    payload.write_bytes(b"#!/bin/sh\necho 1.0.0\n")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    entry = {
        "version": "1.0.0",
        "binaries": ["tool"],
        "artifacts": {
            "x86_64-linux": {"url": payload.as_uri(), "sha256": digest, "kind": "binary"}
        },
    }
    plan = bootstrap.plan_tool("tool", entry, "x86_64-linux", None)
    installed = bootstrap.install(plan, entry, "x86_64-linux", tmp_path / "bin")
    assert installed == [tmp_path / "bin" / "tool"]
    assert installed[0].stat().st_mode & stat.S_IXUSR
