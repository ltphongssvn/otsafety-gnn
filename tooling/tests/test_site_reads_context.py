# tooling/tests/test_site_reads_context.py
"""Every context and conf YAML reaches the site through the contracts pipeline (G.20).

ONE SOURCE, VALIDATED TWICE. The plan, its trace, the ledger, the exemption
register and the experiment configuration are read today by Python alone. The
site restates parts of them in hand-written TypeScript, which is the duplication
the schema-first policy removes everywhere else.

The pipeline already carries shapes: Pydantic to JSON Schema to generated Zod.
This carries the DATA the same way -- each file validated by its own model and
written as JSON the site loads as a content collection, checked again on the
other side by the Zod generated from that same model.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts import data
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.20")


def test_every_context_and_conf_yaml_is_exported() -> None:
    exported = {source.name for source in data.SOURCES}
    assert exported == {"plan", "plan-trace", "plan-ids", "exemptions", "config"}


def test_each_export_names_the_model_that_validates_it() -> None:
    for source in data.SOURCES:
        assert source.model is not None, f"{source.name}: nothing validates it"
        assert source.path.exists(), f"{source.name}: {source.path} is not in the tree"


def test_the_committed_json_is_what_the_yaml_holds() -> None:
    """THE DRIFT GATE: a hand-edited export would pass every other test."""
    for source in data.SOURCES:
        written = data.export(source)
        committed = (REPO_ROOT / data.TARGET / f"{source.name}.json").read_text(encoding="utf-8")
        assert committed == written, f"{source.name}.json differs; run mise run contracts:generate"
