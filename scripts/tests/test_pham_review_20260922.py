"""Dr Pham's 2026-09-22 clinical review of the probiotic sign-off sheet.

Every PMID she cited was content-verified against live PubMed (and the
open-access full text where the abstract was silent) before it was applied:
scripts/audits/closure_20260921/PHAM_REVIEW_20260922.json.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from probiotic_measurements import (
    derived_context_evidence,
    effective_strain_evidence,
    identity_review_accepted,
    strain_literature_review_concluded,
)
from studied_formulas import _clinical_strain_registry, valid_native_study_context

ROOT = Path(__file__).resolve().parents[2]
LA5, BB12, BI07 = "STRAIN_ACIDOPHILUS_LA5", "STRAIN_LACTIS_BB12", "STRAIN_LACTIS_BI07"
LC01 = "UNREGISTERED:Lacticaseibacillus casei LC-01"


def _registry() -> dict:
    return {e["id"]: e for e in json.loads(
        (ROOT / "scripts/data/clinically_relevant_strains.json").read_text())["clinically_relevant_strains"]}


def _combination(**changes) -> dict:
    base = next(c for c in _clinical_strain_registry()[LA5]["study_contexts"]
                if c["context_id"] == "la5_bb12_aad_incidence_24772726")
    context = deepcopy(base)
    context.update(changes)
    return context


# --- the one code change: a frozen record may name an unregistered component ---

def test_a_declared_unregistered_component_keeps_a_combination_record_valid():
    context = _combination(components=[LA5, BB12, LC01],
                           component_registration_status="unregistered_components_present")
    assert valid_native_study_context(context, LA5)
    assert valid_native_study_context(context, BB12)


def test_an_undeclared_unknown_component_fails_closed():
    context = _combination(components=[LA5, BB12, LC01])  # still "fully_registered"
    assert not valid_native_study_context(context, LA5)


def test_a_declaration_cannot_hide_a_fully_registered_formula():
    context = _combination(component_registration_status="unregistered_components_present")
    assert not valid_native_study_context(context, LA5)


def test_a_legacy_context_cannot_declare_its_way_past_the_registry():
    context = _combination(components=[LA5, BB12, LC01],
                           component_registration_status="unregistered_components_present")
    context.pop("context_schema_version")
    assert not valid_native_study_context(context, LA5)


# --- the registry after her decisions ---

CONFIRMED = {
    "STRAIN_LGG", "STRAIN_SACCHAROMYCES", "STRAIN_CASEI_SHIROTA", "STRAIN_COAGULANS_MTCC5856",
    "STRAIN_REUTERI_DSM17938", "STRAIN_K12", "STRAIN_LACTIS_HN019", "STRAIN_PLANTARUM_299V",
    "STRAIN_INFANTIS_35624", "STRAIN_LONGUM_BB536", "STRAIN_RHAMNOSUS_HN001", "STRAIN_RHAMNOSUS_SP1",
}
REPLACED = {  # strain -> (withdrawn PMID, direct human replacement)
    "STRAIN_COAGULANS_SNZ1969": ("36372047", "34119240"),
    "STRAIN_M18": ("32250565", "23449874"),
    "STRAIN_COAGULANS_GBI30": ("29196920", "33110439"),
    "STRAIN_REUTERI_ATCC6475": ("36261538", "29926979"),
    "STRAIN_CRISPATUS_CTV05": ("35659905", "32402161"),
}
WITHDRAWN = {  # strain -> the combination (or ex vivo) record she withdrew
    "STRAIN_PLANTARUM_HEAL9": "31734734", "STRAIN_RHAMNOSUS_GR1": "12628548",
    "STRAIN_FERMENTUM_RC14": "12628548", "STRAIN_HELVETICUS_R0052": "20974015",
    "STRAIN_LONGUM_R0175": "20974015", LA5: "34405373",
}


def _signed_by_pham(entry) -> bool:
    thresholds = entry["cfu_thresholds"]
    return (thresholds.get("dr_pham_signoff") is True
            and str(thresholds.get("dr_pham_signoff_verified_by", "")).startswith("Dr Pham (2026-09-22"))


def test_no_signoff_in_her_name_rests_on_an_agent_check_alone():
    for sid, entry in _registry().items():
        thresholds = entry.get("cfu_thresholds") or {}
        if thresholds.get("dr_pham_signoff") is True:
            assert thresholds.get("dr_pham_signoff_verified_by") != "agent:claude-code", sid


@pytest.mark.parametrize("sid", [BI07, BB12])
def test_restored_signoffs_are_owned_by_the_reviewed_human_contexts(sid):
    entry = _registry()[sid]
    assert _signed_by_pham(entry)
    assert entry["cfu_thresholds"]["evidence"] is None, "the suspended summary is retired"
    assert identity_review_accepted(entry)
    assert effective_strain_evidence(entry) == derived_context_evidence(entry)


def test_reviewed_is_not_effective_for_bi07_and_bb12():
    registry = _registry()
    # Bi-07: the only exact-strain primary outcome is breath hydrogen, a surrogate.
    assert derived_context_evidence(registry[BI07])["effect_direction"] == "unresolved"
    # BB-12: both prespecified primary outcomes of the 1,248-adult RCT were null; its
    # strain-level direction became mixed when the Codex audit added two positive
    # infant-colic RCTs (test_codex_audit_response_20260922).
    adult = next(c for c in registry[BB12]["study_contexts"] if c["context_id"] == "bb12_low_stool_frequency_26382580")
    assert {o["direction"] for o in adult["outcomes"] if o["hierarchy"] == "primary"} == {"null"}


def test_held_la5_bb12_trials_are_approved_as_literal_combination_records():
    contexts = {c["context_id"]: c for c in _registry()[LA5]["study_contexts"]}
    for cid in ("la5_bb12_lc01_yogurt_aad_30439760", "la5_bb12_primal_preterm_mdro_39102225"):
        context = contexts[cid]
        assert context["review_status"] == "clinician_approved"
        assert context["clinical_review"]["reviewer"].startswith("Dr Pham")
        assert context["component_registration_status"] == "unregistered_components_present"
        assert context["identity_scope"] == "combination"
        assert any(c.startswith("UNREGISTERED:") for c in context["components"])
        assert valid_native_study_context(context, LA5) and valid_native_study_context(context, BB12)


@pytest.mark.parametrize("sid", sorted(CONFIRMED))
def test_confirmed_signoffs_name_her(sid):
    assert _signed_by_pham(_registry()[sid])


@pytest.mark.parametrize("sid", ["STRAIN_CASEI_SHIROTA", "STRAIN_INFANTIS_35624", "STRAIN_LACTIS_HN019"])
def test_null_evidence_she_confirmed_earns_no_efficacy_credit(sid):
    assert _registry()[sid]["cfu_thresholds"]["evidence"]["effect_direction"] == "null"


@pytest.mark.parametrize("sid", ["STRAIN_LGG", "STRAIN_SACCHAROMYCES", "STRAIN_PLANTARUM_299V",
                                 "STRAIN_RHAMNOSUS_HN001"])
def test_moderate_certainty_is_not_recorded_as_strong(sid):
    assert _registry()[sid]["cfu_thresholds"]["evidence"]["evidence_strength"] == "medium"


@pytest.mark.parametrize("sid", sorted(REPLACED))
def test_weak_citations_are_replaced_by_direct_human_trials(sid):
    old, new = REPLACED[sid]
    evidence = _registry()[sid]["cfu_thresholds"]["evidence"]
    assert _signed_by_pham(_registry()[sid])
    assert evidence["pmid"] == new
    assert evidence["previous_citation"]["pmid"] == old
    assert evidence["clinical_validation"]["q3_human_clinical"] == "YES"


@pytest.mark.parametrize("sid", sorted(WITHDRAWN))
def test_withdrawn_citations_end_as_reviewed_no_single_strain_evidence(sid):
    entry = _registry()[sid]
    thresholds = entry["cfu_thresholds"]
    assert thresholds["dr_pham_signoff"] is False
    assert thresholds["dr_pham_signoff_verified_by"].startswith("Dr Pham (2026-09-22")
    assert thresholds["evidence"] is None
    assert entry["literature_review"]["reviewer"].startswith("Dr Pham")
    assert WITHDRAWN[sid] in entry["literature_review"]["pmids_screened"]
    if sid == "STRAIN_PLANTARUM_HEAL9":
        # Reopened by the Codex audit: a single-strain HEAL9 RCT exists. The withdrawal stands.
        assert entry["literature_review"]["withdrawn_citation"]["pmid"] == WITHDRAWN[sid]
        return
    assert strain_literature_review_concluded(entry)
    assert not identity_review_accepted(entry)
    assert entry["evidence_level"] == "none" and entry["key_benefits"] == []


@pytest.mark.parametrize("pmid,members", [
    ("31734734", {"STRAIN_PLANTARUM_HEAL9", "STRAIN_PARACASEI_8700"}),
    ("12628548", {"STRAIN_RHAMNOSUS_GR1", "STRAIN_FERMENTUM_RC14"}),
    ("20974015", {"STRAIN_HELVETICUS_R0052", "STRAIN_LONGUM_R0175"}),
])
def test_withdrawn_combination_trials_live_on_as_combination_records(pmid, members):
    registry = _registry()
    records = [c for entry in registry.values() for c in entry.get("study_contexts") or []
               if pmid in c["source_pmids"]]
    assert records and all(c["identity_scope"] == "combination" and set(c["components"]) == members
                            for c in records)
    for member in members:
        assert all(valid_native_study_context(c, member) for c in records)


# --- the class of bug behind Shirota and 35624: a missing direction read as positive ---

DIRECTIONS = {"positive_strong", "positive_weak", "mixed", "null", "negative", "unresolved"}


def test_every_strain_evidence_summary_states_its_direction():
    missing = [sid for sid, entry in _registry().items()
               if (entry.get("cfu_thresholds") or {}).get("evidence")
               and entry["cfu_thresholds"]["evidence"].get("effect_direction") not in DIRECTIONS]
    assert missing == []


def test_a_summary_without_a_direction_earns_no_evidence_credit(monkeypatch):
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from test_probiotic_applicability_rubric import strain_product

    registry = deepcopy(_clinical_strain_registry())
    assert score_evidence(strain_product())["metadata"]["native_clinical_strain_evidence_score"] > 0
    registry["STRAIN_LGG"]["cfu_thresholds"]["evidence"].pop("effect_direction")
    import studied_formulas
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    result = score_evidence(strain_product())
    assert result["metadata"]["native_clinical_strain_evidence_score"] == 0
    assert result["metadata"]["native_clinical_strain_evidence_rows"][0]["effect_multiplier"] == 0.0


def test_an_approved_context_outcome_without_a_direction_never_credits():
    entry = deepcopy(_registry()["STRAIN_REUTERI_ATCC6475"])
    context = deepcopy(next(c for c in _registry()["STRAIN_INFANTIS_M63"]["study_contexts"]
                            if c["context_id"].startswith("m63_")))
    context.update(components=["STRAIN_REUTERI_ATCC6475"], context_id="synthetic_no_direction",
                   outcomes=[{"name": "bone_loss", "hierarchy": "primary", "kind": "patient_important"}])
    entry["study_contexts"] = [context]
    # The frozen contract rejects the record, so it can never own evidence.
    assert not valid_native_study_context(context, "STRAIN_REUTERI_ATCC6475")
    assert derived_context_evidence(entry) is None


def test_nissle_is_affirmative_active_comparator_evidence_without_superiority_credit():
    evidence = _registry()["STRAIN_NISSLE_1917"]["cfu_thresholds"]["evidence"]
    assert evidence["clinical_validation"]["q3_human_clinical"] == "YES"
    assert evidence["type"] == "strain_specific_active_comparator_rct"
    assert evidence["evidence_strength"] == "medium"
    assert evidence["effect_direction"] == "unresolved"  # neither null nor placebo-superiority
    assert "equivalence" in evidence["effect_direction_basis"]
    assert _registry()["STRAIN_NISSLE_1917"]["key_benefits"] == ["ulcerative colitis remission"]


def test_mislabelled_source_types_follow_the_live_record():
    registry = _registry()
    assert registry["STRAIN_CASEI_431"]["cfu_thresholds"]["evidence"]["type"] == "strain_specific_rct"
    assert registry["STRAIN_CASEI_431"]["cfu_thresholds"]["evidence"]["effect_direction"] == "null"
    for sid in ("STRAIN_ACIDOPHILUS_DDS1", "STRAIN_LACTIS_UABla12"):
        evidence = registry[sid]["cfu_thresholds"]["evidence"]
        assert evidence["clinical_validation"]["q1_strain_explicit"] == "YES"  # separate single-strain arms
        assert evidence["effect_direction"] == "positive_strong"


def test_animal_only_benefits_are_not_human_claims():
    entry = _registry()["STRAIN_REUTERI_ATCC6475"]
    assert entry["key_benefits"] == ["bone health"]
    # mixed since the Codex audit added the 2024 null trial (38865129)
    assert entry["cfu_thresholds"]["evidence"]["effect_direction"] == "mixed"
    assert entry["cfu_thresholds"]["evidence"]["previous_citation"]["pmid"] == "36261538"


@pytest.mark.parametrize("sid", sorted(WITHDRAWN))
def test_a_withdrawn_citation_keeps_an_auditable_disposition(sid):
    withdrawn = _registry()[sid]["literature_review"]["withdrawn_citation"]
    assert withdrawn["pmid"] == WITHDRAWN[sid]
    assert withdrawn["withdrawn_by"].startswith("Dr Pham") and withdrawn["reason"]
