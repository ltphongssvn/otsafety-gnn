# tooling/tests/test_compliance_is_checked.py
"""Licence terms are checked mechanically, not asserted in a comment (G.13).

THE CONSTRAINT LIVED ON LINE 55 OF conf/config.yaml, in prose: MedDRA is
proprietary and its hierarchy cannot be redistributed. True, and no gate reads
it. 2026 audits call this exactly what it is -- declarations rich and
enforcement theatre -- and measure a project by the share of its requirements
carrying a real mechanical check.

FACTS, NOT LEGAL READINGS. The rule checks what can be observed: that every
source declares a licence and whether it is open, that a source declared closed
ships no data file, and that the config's MedDRA slot stays empty unless a
subscriber mounts one. Recording engineering facts is the work; interpreting
terms is not something to encode without the maintainer.

AN UNDECLARED LICENCE BLOCKS INGESTION, which is the shape 2026 licence gates
take: an unknown licence is not permission, and a source whose terms nobody
recorded cannot be used.
"""

from __future__ import annotations

import pytest

from otsafety_tooling.contracts.files import read_yaml
from otsafety_tooling.contracts.sources import DataSources
from otsafety_tooling.paths import REPO_ROOT

pytestmark = pytest.mark.requirement("G.13")

SOURCES = REPO_ROOT / "context" / "sources.yaml"
RULE = REPO_ROOT / "policy" / "licences.rego"


def _sources() -> DataSources:
    return read_yaml(SOURCES, DataSources)


def test_every_source_declares_its_terms() -> None:
    """A source whose licence nobody recorded cannot be used."""
    silent = [s.name for s in _sources().sources if not s.licence.strip()]
    assert silent == [], f"sources with no recorded terms: {silent}"


def test_a_closed_source_names_what_may_not_be_redistributed() -> None:
    """Knowing a source is closed is not enough to act on."""
    for source in _sources().sources:
        if not source.open:
            assert source.withheld, f"{source.name} is closed and names nothing withheld"


def test_meddra_is_closed_and_its_hierarchy_is_not_in_the_tree() -> None:
    """The constraint that was a comment, as an observation."""
    sources = _sources()
    meddra = next(s for s in sources.sources if "meddra" in s.name.lower())
    assert not meddra.open
    from otsafety_tooling.policy.licences import redistributed

    assert redistributed(REPO_ROOT) == [], (
        "files matching a closed source's withheld artefacts are tracked"
    )


def test_the_matcher_can_see_a_withheld_file() -> None:
    """THE LIVENESS CONTROL, beside the assertion that depends on it.

    redistributed() returning nothing is the expected result and therefore
    proves nothing on its own: a pattern matching nothing is evidence only once
    it has been shown able to match. This runs the same matcher against a path
    that must offend, and against one that must not.
    """
    from otsafety_tooling.policy.licences import offending

    sources = _sources()
    withheld = tuple(
        pattern for source in sources.sources if not source.open for pattern in source.withheld
    )
    assert withheld, "no closed source withholds anything; the gate would pass vacuously"
    assert offending(withheld, ("data/meddra/llt.asc",)) == ["data/meddra/llt.asc"]
    assert offending(withheld, ("data/opentargets/target.parquet",)) == []


def test_the_config_mounts_no_licensed_hierarchy() -> None:
    """Empty by default: a subscriber mounts one, this repository ships none."""
    from otsafety_tooling.contracts.opentargets_config import OpenTargetsConfig

    config = read_yaml(REPO_ROOT / "conf" / "config.yaml", OpenTargetsConfig)
    assert config.endpoints.meddra_hierarchy is None


def test_the_rule_exists_and_the_engine_runs_it() -> None:
    """G.5's engine judges this, as it judges the other policy."""
    assert RULE.is_file(), f"no rule at {RULE.relative_to(REPO_ROOT)}"
    text = RULE.read_text(encoding="utf-8")
    assert "package policy" in text, "every rule here is in the flat policy package"
    assert "deny" in text, "a rule that denies nothing checks nothing"
