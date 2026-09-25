# tooling/tests/test_architecture_is_one_source.py
"""The architecture is stated once, and everything reads it (8.5).

THE NINE LAYERS WERE TYPED TWICE. Once in the sheet's generator, once in
apps/site/src/data/architecture.ts, and the two had already diverged where
nobody was looking: REALITY's failure reads two sentences in the generator and
one on the site, and the site carries neither the as-code nor the as-data
column. The names matched, which is the weakest possible agreement.

A THIRD COPY WAS ABOUT TO BE WRITTEN. The README needs the layers, and copying
them again is what this step exists to prevent -- so the architecture becomes a
contract-validated document that the sheet, the site and the README all read.

WHAT A LAYER MUST CARRY. Its number and name, the question it answers, the
failure if it goes unguarded, the guard, and both the as-code and as-data sides
-- the last two are exactly what the TypeScript round trip dropped.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.architecture import Architecture
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("8.5")

SOURCE = REPO_ROOT / "context" / "architecture.yaml"


def _architecture() -> Architecture:
    from otsafety_tooling.contracts.files import read_yaml

    return read_yaml(SOURCE, Architecture)


def test_the_architecture_is_stated_in_one_document() -> None:
    assert SOURCE.is_file(), f"{SOURCE} does not exist; the layers are still typed twice"


def test_every_layer_carries_both_sides() -> None:
    """The as-code and as-data columns are what the round trip lost."""
    architecture = _architecture()
    layers = architecture.layers
    assert len(layers) == 9, f"{len(layers)} layers; the model has nine"
    for layer in layers:
        assert layer.as_code, f"layer {layer.n} states no as-code artifact"
        assert layer.as_data, f"layer {layer.n} states no as-data record"
        assert len(layer.failure) > 40, f"layer {layer.n}'s failure is a fragment"


def test_the_sheet_reads_the_document_rather_than_typing_it() -> None:
    """A table typed in the generator is a second copy by definition."""
    from importlib import util

    spec = util.spec_from_file_location(
        "build_arch_onepager", REPO_ROOT / "scripts" / "build_arch_onepager.py"
    )
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (REPO_ROOT / "scripts" / "build_arch_onepager.py").read_text(encoding="utf-8")
    assert "LAYERS = [" not in source, "the sheet still types the layers"
    assert len(module.layer_rows()) > 0, "the sheet renders no layers at all"


def test_the_site_reads_the_document_rather_than_typing_it() -> None:
    """The copy that silently lost two columns."""
    typescript = REPO_ROOT / "apps" / "site" / "src" / "data" / "architecture.ts"
    if not typescript.is_file():
        return
    assert "REALITY" not in typescript.read_text(encoding="utf-8"), (
        "the site still types the layers beside the document"
    )


def test_layer_one_names_the_unresolvable_gap() -> None:
    """The model card's limitation statement begins here, and must survive."""
    architecture = _architecture()
    first = next(layer for layer in architecture.layers if layer.n == "1")
    assert "pharmacology" in first.failure
    assert "model card" in first.guard.lower()
