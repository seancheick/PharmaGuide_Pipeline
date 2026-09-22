"""Regression cases from Codex's 2026-09-22 registry audit and the second review.

Each finding was reproduced against live PubMed / Europe PMC before it was applied:
scripts/audits/closure_20260921/CODEX_AUDIT_RESPONSE_20260922.json.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from clinical_evidence_schema import validate_frozen_context
from probiotic_measurements import (
    derived_context_evidence,
    identity_review_accepted,
    strain_literature_review_concluded,
)
from studied_formulas import _clinical_strain_registry, clinical_strain_identity_matches, valid_native_study_context

ROOT = Path(__file__).resolve().parents[2]


def _registry() -> dict:
    return {e["id"]: e for e in json.loads(
        (ROOT / "scripts/data/clinically_relevant_strains.json").read_text())["clinically_relevant_strains"]}


def _contexts(sid: str) -> dict:
    return {c["context_id"]: c for c in _registry()[sid].get("study_contexts") or []}


def test_a_single_strain_label_is_not_the_prodentis_blend():
    prodentis = _registry()["STRAIN_REUTERI_PRODENTIS"]
    for label in ("L. reuteri ATCC PTA 5289", "L. reuteri ATCC 55730"):
        assert label not in prodentis["aliases"]
        assert not clinical_strain_identity_matches(label, prodentis)
    assert prodentis["cfu_thresholds"]["evidence"]["effect_direction"] == "unresolved"


def test_an_oral_label_cannot_inherit_vaginal_ctv05_efficacy():
    evidence = _registry()["STRAIN_CRISPATUS_CTV05"]["cfu_thresholds"]["evidence"]
    assert evidence["effect_direction"] == "unresolved"
    assert "vaginal" in evidence["effect_direction_basis"]


def test_m16v_carries_neither_the_combination_trial_nor_nec_credit():
    entry = _registry()["STRAIN_BREVE_M16V"]
    evidence = entry["cfu_thresholds"]["evidence"]
    assert evidence["pmid"] == "28796951" and evidence["effect_direction"] == "null"
    assert evidence["previous_citation"]["pmid"] == "40085083"
    assert "NEC prevention" not in entry["key_benefits"]


def test_dracma_lgg_results_do_not_transfer_to_crl431_bb12():
    context = _contexts("STRAIN_LACTIS_BB12")["casei431_bb12_dracma_cma_tolerance_39310372"]
    assert context["scoring_eligible"] is False
    assert all(o["direction"] != "positive" for o in context["outcomes"])
    assert any("LGG" in limitation for limitation in context["limitations"])


def test_the_uabla12_arm_is_its_own_single_strain_record():
    context = _contexts("STRAIN_LACTIS_UABla12")["uabla12_ibs_three_arm_32019158"]
    assert context["identity_scope"] == "exact_strain" and context["components"] == ["STRAIN_LACTIS_UABla12"]
    dds1 = _contexts("STRAIN_ACIDOPHILUS_DDS1")["dds1_ibs_three_arm_32019158"]
    assert context["trial_family"] == dds1["trial_family"]
    assert valid_native_study_context(context, "STRAIN_LACTIS_UABla12")


@pytest.mark.parametrize("sid,pmid", [("STRAIN_PLANTARUM_HEAL9", "37571403"),
                                      ("STRAIN_ACIDOPHILUS_LAFTI_L10", "27363733")])
def test_an_incomplete_search_no_longer_reads_as_no_human_evidence(sid, pmid):
    entry = _registry()[sid]
    assert not strain_literature_review_concluded(entry)
    assert entry["literature_review"]["conclusion"] == "exact_strain_contexts_recorded"
    assert any(pmid in c["source_pmids"] for c in entry["study_contexts"])
    assert identity_review_accepted(entry)


def test_cncm_i745_evidence_is_not_inherited_by_an_unidentified_boulardii_label():
    registry = _registry()
    generic, i745 = registry["STRAIN_SACCHAROMYCES"], registry["STRAIN_BOULARDII_CNCM_I745"]
    assert not any("i745" in c["context_id"] for c in generic["study_contexts"])
    assert "Florastor" not in generic["aliases"] and "Saccharomyces boulardii CNCM I-745" not in generic["aliases"]
    assert len(i745["study_contexts"]) == 6
    assert all(c["components"] == ["STRAIN_BOULARDII_CNCM_I745"] for c in i745["study_contexts"])


def test_enterogermina_evidence_stays_formula_level():
    assert "Enterogermina" not in _registry()["STRAIN_CLAUSII"]["aliases"]


def test_a_primary_outcome_cannot_be_a_subgroup_finding():
    context = deepcopy(_contexts("STRAIN_LGG")["lgg_pediatric_pain_17229242"])
    assert validate_frozen_context(context, known_component_ids=set(_clinical_strain_registry())) == []
    context["outcomes"][0]["outcome_role"] = "post_hoc_subgroup"
    assert "outcome[0].primary_role_contradiction" in validate_frozen_context(
        context, known_component_ids=set(_clinical_strain_registry()))


def _positive_rct(context_id, condition, role=None):
    base = deepcopy(_contexts("STRAIN_LACTIS_BB12")["bb12_infant_colic_breastfed_31797399"])
    base.update(context_id=context_id, condition=condition, trial_family=context_id, source_pmids=[context_id[-8:]])
    base["dose"]["source_provenance"]["pmid"] = context_id[-8:]
    if role:
        base["outcomes"][0]["outcome_role"] = role
    return base


def test_positive_trials_of_different_conditions_are_not_replication():
    entry = deepcopy(_registry()["STRAIN_LACTIS_BB12"])
    entry["study_contexts"] = [_positive_rct("synthetic_a_00000001", "infant_colic"),
                               _positive_rct("synthetic_b_00000002", "adult_constipation")]
    assert derived_context_evidence(entry)["evidence_strength"] == "medium"
    entry["study_contexts"][1]["condition"] = "infant_colic"
    assert derived_context_evidence(entry)["evidence_strength"] == "strong"


def test_a_within_group_primary_change_earns_no_efficacy_credit():
    entry = deepcopy(_registry()["STRAIN_LACTIS_BB12"])
    entry["study_contexts"] = [_positive_rct("synthetic_a_00000001", "infant_colic", role="within_group_change")]
    assert derived_context_evidence(entry)["effect_direction"] == "unresolved"


def test_bb12_null_in_adults_is_not_a_global_verdict():
    derived = derived_context_evidence(_registry()["STRAIN_LACTIS_BB12"])
    assert derived["effect_direction"] == "mixed"  # positive infant-colic RCTs beside the null adult trial
    assert derived["evidence_strength"] == "strong"  # two positive trials of the same condition


@pytest.mark.parametrize("label,expected", [
    ("resistant maltodextrin", "Resistant Dextrin"),
    ("Resistant Starch", "Resistant Starch"),
])
def test_resistant_maltodextrin_is_not_resistant_starch(label, expected):
    from prebiotic_catalog import prebiotic_catalog, match_prebiotic

    prebiotic_catalog.cache_clear()
    assert match_prebiotic(label).standard_name == expected


@pytest.mark.parametrize("label", ["guar fiber", "polyphenol-based prebiotic"])
def test_generic_prebiotic_phrases_are_not_a_specific_identity(label):
    from prebiotic_catalog import prebiotic_catalog, match_prebiotic

    prebiotic_catalog.cache_clear()
    assert match_prebiotic(label).standard_name not in {"Partially Hydrolyzed Guar Gum", "Pomegranate Polyphenol Extract"}


def test_claims_are_bound_to_the_records_that_hold_them():
    registry = _registry()
    assert registry["STRAIN_REUTERI_ATCC6475"]["cfu_thresholds"]["evidence"]["effect_direction"] == "mixed"
    assert "38865129" in registry["STRAIN_REUTERI_ATCC6475"]["cfu_thresholds"]["evidence"]["additional_pmids"]
    assert registry["STRAIN_REUTERI_DSM17938"]["cfu_thresholds"]["secondary_indications"][0]["pmid"] == "31739457"
    assert registry["STRAIN_PARACASEI_8700"]["key_benefits"] == ["cardiometabolic markers (biomarker evidence)"]
    assert registry["STRAIN_LONGUM_1714"]["key_benefits"] == []
    assert "EMA approved" not in registry["STRAIN_NISSLE_1917"]["notable_studies"]
    assert registry["STRAIN_COAGULANS_IS2"]["cfu_thresholds"]["evidence"]["clinical_validation"]["score_yes_count"] == 3
