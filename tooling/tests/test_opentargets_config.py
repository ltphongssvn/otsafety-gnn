# tooling/tests/test_opentargets_config.py
"""conf/config.yaml must name datasets that exist in the pinned release.

VERIFIED AGAINST THE LIVE SERVER, NOT REMEMBERED. Listing
ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/ returns the real
directory names. Three of the six the config named were camelCase from the
pre-25.03 layout -- mechanismOfAction, openfdaFaers, indication -- and a fourth,
targetPathway, is not a dataset at all. Post 25.03 the paths are snake_case,
singular, and Parquet only, so those four resolved to nothing.

WHY THE LISTING IS NOT FETCHED HERE. A test that reaches the network fails when
the network does, and says nothing about the code. The names below are recorded
from a listing taken on 2026-09-20; data:check reaches the server and records a
verdict as evidence, which is where a live claim belongs.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("yaml", reason="pyyaml is not installed")

import yaml

from otsafety_tooling.paths import REPO_ROOT

CONFIG = REPO_ROOT / "conf" / "config.yaml"

# Every directory in 26.03/output/, as the server returned it.
RELEASE_2603_DATASETS = {
    "association_by_datasource_direct",
    "association_by_datasource_indirect",
    "association_by_datatype_direct",
    "association_by_datatype_indirect",
    "association_overall_direct",
    "association_overall_indirect",
    "biosample",
    "clinical_indication",
    "clinical_report",
    "clinical_target",
    "colocalisation",
    "credible_set",
    "disease",
    "disease_hpo",
    "disease_phenotype",
    "drug_mechanism_of_action",
    "drug_molecule",
    "drug_warning",
    "enhancer_to_gene",
    "evidence_cancer_biomarkers",
    "evidence_cancer_gene_census",
    "evidence_clingen",
    "evidence_clinical_precedence",
    "evidence_crispr",
    "evidence_crispr_screen",
    "evidence_europepmc",
    "evidence_eva",
    "evidence_eva_somatic",
    "evidence_expression_atlas",
    "evidence_gene2phenotype",
    "evidence_gene_burden",
    "evidence_genomics_england",
    "evidence_gwas_credible_sets",
    "evidence_impc",
    "evidence_intogen",
    "evidence_orphanet",
    "evidence_reactome",
    "evidence_uniprot_literature",
    "evidence_uniprot_variants",
    "expression",
    "go",
    "interaction",
    "interaction_evidence",
    "l2g_prediction",
    "literature",
    "literature_vector",
    "mouse_phenotype",
    "openfda_significant_adverse_drug_reactions",
    "pharmacogenomics",
    "so",
    "study",
    "target",
    "target_essentiality",
    "target_prioritisation",
    "variant",
}

# Datasets this project cannot do without, with the section that must name each.
#
# NOT ALL OF THEM ARE RELATIONS. target, drug_warning and
# evidence_clinical_precedence are label and node sources: safety annotations
# live inside target, warnings are the Tier 1 labels, and clinical precedence is
# what EARNS a negative. Asserting them against data.relations demanded they be
# edges, which they are not.
REQUIRED = {
    "target": ("labels", "target safety lives here; there is no top-level safety dataset"),
    "drug_warning": ("labels", "withdrawals and black-box warnings, the Tier 1 label source"),
    "evidence_clinical_precedence": (
        "labels",
        "earns a NEGATIVE: phase 3 or above with no liability",
    ),
    "drug_mechanism_of_action": ("relations", "drug to target, the edge attribution deconvolves"),
    "openfda_significant_adverse_drug_reactions": (
        "relations",
        "drug to adverse event, Tier 3 only",
    ),
}


def _config() -> dict[str, Any]:
    if not CONFIG.is_file():
        pytest.fail(f"no config at {CONFIG}")
    loaded: dict[str, Any] = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return loaded


def test_the_pinned_release_is_the_current_one() -> None:
    """25.03 was pinned while 25.12 and 26.03 had shipped."""
    assert _config()["data"]["platform_version"] == "26.03"


def test_every_named_dataset_exists_in_the_release() -> None:
    """A dataset name that is not in the release downloads nothing at all."""
    relations = _config()["data"]["relations"]
    for name, spec in relations.items():
        dataset = spec[0]
        assert dataset in RELEASE_2603_DATASETS, (
            f"relation {name!r} names dataset {dataset!r}, which is not in 26.03"
        )


def _named_datasets(config: dict[str, Any]) -> dict[str, set[str]]:
    """Every dataset the config names, by the section that names it."""
    relations = {spec[0] for spec in config["data"]["relations"].values()}
    labels = set(config["labels"]["curated"]) | {config["labels"]["clinical_precedence"]}
    return {"relations": relations, "labels": labels}


def test_the_datasets_this_project_cannot_do_without_are_named() -> None:
    named = _named_datasets(_config())
    for dataset, (section, why) in REQUIRED.items():
        assert dataset in named[section], f"{dataset} is not named under {section}, and {why}"


def test_the_label_sources_are_not_also_relations() -> None:
    """A label source read as an edge would put the answer in the graph."""
    named = _named_datasets(_config())
    overlap = named["labels"] & named["relations"]
    assert not overlap, (
        f"{sorted(overlap)} appear as both a label source and an edge relation; "
        f"the model would read its own labels off the message graph"
    )
