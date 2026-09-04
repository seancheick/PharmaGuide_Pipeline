"""Study contexts are source-bound assessments, not automatic efficacy credit."""
from copy import deepcopy

import pytest

import studied_formulas
from test_probiotic_applicability_rubric import strain_product


def context(**changes):
    row = {
        "context_id": "synthetic-context", "source_pmids": ["synthetic-source"],
        "identity_scope": "exact_strain", "components": ["STRAIN_LGG"],
        "population": {"age_group": "adult", "description": "Synthetic adult population"},
        "purpose": "treatment", "condition": "constipation",
        "dose": {"basis": "discrete_daily_arms", "unit": "CFU", "values": [1e9, 1e10],
                 "dosage_forms": ["capsule"], "duration_days": 28, "co_therapies": []},
        "outcomes": [{"name": "stool_frequency", "hierarchy": "primary",
                      "kind": "patient_important", "direction": "null"}],
        "trial_family": "synthetic-trial", "limitations": ["Synthetic test only"],
        "review_status": "source_verified_pending_clinical_review",
    }
    row.update(changes)
    return row


@pytest.fixture
def registry(monkeypatch):
    rows = deepcopy(studied_formulas._clinical_strain_registry())
    rows["STRAIN_LGG"]["study_contexts"] = [context()]
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: rows)
    return rows


def assessment(product):
    return studied_formulas.assess_probiotic_evidence(product)["strain_assessments"][0]


def test_context_uses_current_registry_not_a_caller_stamp(registry):
    p = strain_product(dose=1e9)
    p["probiotic_data"]["clinical_strains"][0]["study_contexts"] = [context(condition="ibs")]
    row = assessment(p)
    result = row["study_contexts"][0]
    assert result["condition"] == "constipation"
    assert result["dose_comparison"] == "matches_tested_daily_dose"
    assert result["outcomes"][0]["direction"] == "null"
    assert result["clinical_applicability"] == "not_established"
    assert row["dose_applicable"] is False


@pytest.mark.parametrize("dose,expected", [(1e9, "matches_tested_daily_dose"),
    (5e9, "outside_tested_daily_doses"), (1e10, "matches_tested_daily_dose"),
    (None, "label_dose_unknown")])
def test_discrete_arms_do_not_create_an_interpolated_window(registry, dose, expected):
    assert assessment(strain_product(dose=dose))["study_contexts"][0]["dose_comparison"] == expected


@pytest.mark.parametrize("basis", ["measured_viability", "single_challenge", "unresolved"])
def test_other_measurements_never_become_daily_dose_thresholds(registry, basis):
    registry["STRAIN_LGG"]["study_contexts"][0]["dose"]["basis"] = basis
    assert assessment(strain_product(dose=1e9))["study_contexts"][0]["dose_comparison"] == "study_daily_dose_unresolved"


def test_unknown_and_different_populations_are_distinct(registry):
    p = strain_product(dose=1e9)
    p["target_population"] = "infant"
    assert assessment(p)["study_contexts"][0]["population_comparison"] == "different_label_population"
    p.pop("target_population")
    assert assessment(p)["study_contexts"][0]["population_comparison"] == "label_population_unknown"


def test_combination_and_species_context_cannot_become_individual_efficacy(registry):
    c = registry["STRAIN_LGG"]["study_contexts"][0]
    c.update(identity_scope="combination", components=["STRAIN_LGG", "STRAIN_LACTIS_BI07"])
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    assert result["dose_comparison"] == "combination_not_individual_dose"
    assert result["clinical_applicability"] == "not_established"
    c.update(identity_scope="species_general", components=["STRAIN_LGG"])
    assert assessment(strain_product(dose=1e9))["study_contexts"][0]["dose_comparison"] == "species_not_exact_strain"


def test_context_never_borrows_blend_total(registry):
    p = strain_product(dose=1e9)
    p["probiotic_data"]["probiotic_blends"][0]["strains"].append("Another organism")
    assert assessment(p)["study_contexts"][0]["dose_comparison"] == "label_dose_unknown"


def test_marketing_cannot_prove_patient_condition_or_regimen(registry):
    p = strain_product(dose=1e9)
    before = assessment(p)["study_contexts"]
    p.update(product_name="Treat constipation in adults for 28 days", statements=["constipation"])
    assert assessment(p)["study_contexts"] == before
    assert before[0]["clinical_applicability"] == "not_established"


@pytest.mark.parametrize("field,value", [("source_pmids", []), ("outcomes", []),
    ("components", ["NONEXISTENT"]), ("review_status", "approved"), ("population", {}),
    ("purpose", "anything"), ("dose", {"basis": "discrete_daily_arms", "values": [True]})])
def test_invalid_context_is_explicit_and_cannot_crash_scoring(registry, field, value):
    registry["STRAIN_LGG"]["study_contexts"][0][field] = value
    row = assessment(strain_product(dose=1e9))
    assert row["study_contexts"][0]["status"] == "invalid_context"
    assert row["dose_applicable"] is False


def test_source_review_hold_does_not_hide_a_context_or_approve_it(registry):
    registry["STRAIN_LGG"]["cfu_thresholds"]["dr_pham_signoff"] = False
    row = assessment(strain_product(dose=1e9))
    assert row["research_accepted"] is False
    assert row["study_contexts"][0]["review_status"] == "source_verified_pending_clinical_review"
    assert row["dose_applicable"] is False


def test_context_requires_real_label_ownership(registry):
    p = strain_product(dose=1e9)
    p["activeIngredients"][0]["name"] = "Unrelated label row"
    row = assessment(p)
    assert row["study_contexts"][0]["dose_comparison"] == "identity_owner_unresolved"
    assert row["dose_applicable"] is False


def test_pending_context_cannot_be_bypassed_by_an_old_universal_range(registry):
    registry["STRAIN_LGG"]["applicability"] = {
        "minimum_daily_dose": 1e9, "maximum_daily_dose": 1e10, "dose_unit": "CFU",
        "source_pmids": ["synthetic-source"], "supported_outcomes": ["digestive"],
        "dosage_forms": ["capsule"], "target_population": "adult",
        "studied_population": "Synthetic adults",
    }
    assert assessment(strain_product(dose=1e9))["dose_applicable"] is False


def test_unknown_endpoint_hierarchy_is_not_invented(registry):
    registry["STRAIN_LGG"]["study_contexts"][0]["outcomes"][0]["hierarchy"] = "unresolved"
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    assert result["status"] == "source_context_recorded"
    assert result["outcomes"][0]["hierarchy"] == "unresolved"


def test_returned_context_cannot_mutate_canonical_research(registry):
    result = assessment(strain_product(dose=1e9))["study_contexts"][0]
    result["outcomes"][0]["direction"] = "positive"
    result["dose"]["values"].append(5e9)
    fresh = assessment(strain_product(dose=5e9))["study_contexts"][0]
    assert fresh["outcomes"][0]["direction"] == "null"
    assert fresh["dose_comparison"] == "outside_tested_daily_doses"


def test_combination_context_has_one_owner_but_matches_each_component(registry):
    c = registry["STRAIN_LGG"].pop("study_contexts")[0]
    c.update(identity_scope="combination", components=["STRAIN_LGG", "STRAIN_LACTIS_BI07"])
    registry["STRAIN_LACTIS_BI07"]["study_contexts"] = [c]
    result = assessment(strain_product(dose=1e9))["study_contexts"]
    assert len(result) == 1
    assert result[0]["dose_comparison"] == "combination_not_individual_dose"
    assert assessment(strain_product(dose=1e9))["dose_applicable"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True])
def test_nonpositive_and_nonfinite_study_dose_is_invalid(registry, value):
    registry["STRAIN_LGG"]["study_contexts"][0]["dose"]["values"] = [value]
    assert assessment(strain_product(dose=1e9))["study_contexts"][0]["status"] == "invalid_context"


def test_shared_guideline_has_one_study_family_across_native_contexts():
    registry = studied_formulas._clinical_strain_registry()
    contexts = [context for cid in ("STRAIN_LGG", "STRAIN_SACCHAROMYCES")
                for context in registry[cid]["study_contexts"]
                if "26756877" in context["source_pmids"]]
    assert len(contexts) == 2
    assert len({context["context_id"] for context in contexts}) == 2
    assert len({context["trial_family"] for context in contexts}) == 1


def test_priority_native_contexts_are_curated_without_new_approval():
    registry = studied_formulas._clinical_strain_registry()
    expected = {
        "STRAIN_LGG": {"26756877", "17229242"},
        "STRAIN_LACTIS_BB12": {"26382580"},
        "STRAIN_LACTIS_BI07": {"21436726", "36149331"},
        "STRAIN_LACTIS_HN019": {"39356506", "40320938"},
        "STRAIN_SACCHAROMYCES": {"26756877", "22472744", "41675330"},
        "STRAIN_ACIDOPHILUS_NCFM": {"28082816", "19651563"},
        "STRAIN_LACTIS_BL04": {"24268677", "28343401"},
        "STRAIN_PARACASEI_LPC37": {"33385020", "37662485"},
    }
    seen = set()
    for cid, pmids in expected.items():
        contexts = registry[cid].get("study_contexts", [])
        assert {p for c in contexts for p in c["source_pmids"]} == pmids
        for c in contexts:
            assert studied_formulas.valid_native_study_context(c, cid)
            assert all(p.isdigit() for p in c["source_pmids"])
            assert c["context_id"] not in seen
            seen.add(c["context_id"])
    assert sum(r.get("cfu_thresholds", {}).get("dr_pham_signoff") is True
               for r in registry.values()) == 40
    for cid in ("STRAIN_LACTIS_BI07", "STRAIN_LACTIS_BB12"):
        assert registry[cid]["cfu_thresholds"]["dr_pham_signoff"] is False
    for cid in ("STRAIN_ACIDOPHILUS_NCFM", "STRAIN_LACTIS_BL04"):
        assert "Best-available PubMed hit" not in registry[cid]["cfu_thresholds"]["notes"]


def test_real_study_doses_preserve_ambiguity_and_separate_arms():
    registry = studied_formulas._clinical_strain_registry()
    def study(cid, pmid):
        return next(c for c in registry[cid]["study_contexts"] if pmid in c["source_pmids"])
    assert study("STRAIN_LGG", "17229242")["dose"]["basis"] == "unresolved"
    assert study("STRAIN_LACTIS_BB12", "26382580")["dose"]["values"] == [1e9, 1e10]
    assert study("STRAIN_LACTIS_HN019", "39356506")["dose"]["basis"] == "measured_viability"
    assert study("STRAIN_LACTIS_BI07", "36149331")["dose"]["basis"] == "single_challenge"
    assert study("STRAIN_LACTIS_BI07", "21436726")["identity_scope"] == "combination"
    assert study("STRAIN_SACCHAROMYCES", "26756877")["identity_scope"] == "species_general"


def test_lpc37_primary_null_results_and_viability_are_not_positive_dose_arms():
    entry = studied_formulas._clinical_strain_registry()["STRAIN_PARACASEI_LPC37"]
    contexts = {c["source_pmids"][0]: c for c in entry.get("study_contexts", [])}
    assert set(contexts) == {"33385020", "37662485"}
    for pmid, values, days in (("33385020", [1.75e10, 1.68e10], 35),
                               ("37662485", [1.56e10, 1.35e10], 70)):
        context_row = contexts[pmid]
        assert context_row["dose"]["basis"] == "measured_viability"
        assert context_row["dose"]["values"] == values
        assert context_row["dose"]["duration_days"] == days
        assert context_row["review_status"] == "source_verified_pending_clinical_review"
        assert [o["direction"] for o in context_row["outcomes"]
                if o["hierarchy"] == "primary"] == ["null"]
    evidence = entry["cfu_thresholds"]["evidence"]
    assert evidence["pmid"] == "33385020"  # No approval borrowed by the new paper.
    assert evidence["effect_direction"] == "null"
    assert evidence["clinical_validation"]["q1_strain_explicit"] == "YES"
    assert evidence["clinical_validation"]["q4_dose_mentioned"] == "YES"
    assert entry["cfu_thresholds"]["dr_pham_signoff"] is True  # Historical record only.


def test_lpc37_sources_join_without_new_approval_or_interpolated_dose():
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = strain_product(clinical_id="STRAIN_PARACASEI_LPC37",
                             name="Lactobacillus paracasei Lpc-37", dose=1.56e10)
    result = assessment(product)
    assert set(result["source_pmids"]) == {"33385020", "37662485"}
    assert result["scoring_source_pmids"] == ["33385020"]
    assert result["dose_applicable"] is False
    assert {c["dose_comparison"] for c in result["study_contexts"]} == {"study_daily_dose_unresolved"}
    evidence = score_evidence(product)
    assert evidence["metadata"]["evidence_assessment"]["native_context_review"]["status"] == "pending_clinical_review"
    assert evidence["metadata"]["evidence_result_state"] == "evaluated_null"


@pytest.mark.parametrize("stale_field", ["indication_primary", "indication_secondary", "clinical_support_level"])
def test_native_indication_copy_uses_current_registry_not_old_artifact(stale_field):
    from scoring_v4.modules.probiotic_evidence import score_evidence

    product = strain_product(clinical_id="STRAIN_PARACASEI_LPC37",
                             name="Lactobacillus paracasei Lpc-37", dose=1.56e10)
    clinical = product["probiotic_data"]["clinical_strains"][0]
    clinical[stale_field] = "digestive immune support"
    before = deepcopy(product)
    evidence = score_evidence(product)
    categories = evidence["metadata"]["claim_alignment"]["strain_categories"]
    assert not {"digestive", "immune"}.intersection(categories)
    assert evidence["metadata"]["evidence_result_state"] == "evaluated_null"
    assert product == before


def test_source_verified_pending_research_is_not_called_no_human_evidence():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from scoring_v4.confidence import _evidence_confidence

    p = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM", name="Lactobacillus acidophilus NCFM", dose=1e9)
    evidence = score_evidence(p)
    assert evidence["score"] == 0  # No new approval or numeric credit.
    assert evidence["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    confidence, reasons = _evidence_confidence(p, {"dimensions": {"evidence": evidence}},
        evidence_assessment={"readiness": "complete"})
    assert confidence == "moderate"
    assert reasons == ["evidence_review_incomplete"]


@pytest.mark.parametrize("cid,name", [
    ("STRAIN_LGG", "Lactobacillus rhamnosus GG"),
    ("STRAIN_LACTIS_HN019", "Bifidobacterium lactis HN019"),
    ("STRAIN_SACCHAROMYCES", "Saccharomyces boulardii"),
])
def test_pending_review_is_independent_of_existing_positive_or_null_credit(cid, name):
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from scoring_v4.confidence import _evidence_confidence
    p = strain_product(clinical_id=cid, name=name, dose=1e9)
    evidence = score_evidence(p)
    assert evidence["score"] > 0
    assert evidence["metadata"]["evidence_assessment"]["native_context_review"]["status"] == "pending_clinical_review"
    assert _evidence_confidence(p, {"dimensions": {"evidence": evidence}},
        evidence_assessment={"readiness": "complete"}) == ("moderate", ["evidence_review_incomplete"])
    if cid == "STRAIN_LACTIS_HN019":
        assert evidence["metadata"]["evidence_result_state"] == "evaluated_null"


def test_research_summary_includes_new_sources_without_lending_them_approval():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    p = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM", name="Lactobacillus acidophilus NCFM")
    row = assessment(p)
    assert {"28082816", "19651563", "21436726"} <= set(row["source_pmids"])
    assert row["scoring_source_pmids"] == ["24717228"]
    evidence = score_evidence(p)
    assert evidence["score"] == 0
    assert evidence["metadata"]["uncredited_native_strain_evidence_rows"][0]["source_pmids"] == ["24717228"]


def test_legacy_native_range_cannot_become_a_second_applicability_engine(registry):
    registry["STRAIN_LGG"].pop("study_contexts")
    registry["STRAIN_LGG"]["applicability"] = {
        "dose_unit": "CFU", "minimum_daily_dose": 1e9, "maximum_daily_dose": 2e10,
        "dosage_forms": ["capsule"], "target_population": "adult",
        "studied_population": "Synthetic adults", "supported_outcomes": ["digestive"],
        "source_pmids": ["synthetic-source"]}
    row = assessment(strain_product(dose=1e9))
    assert row["dose_applicable"] is False
    assert row["status"] == "strain_dose_reference_unreviewed"


def test_exact_formula_confidence_does_not_inherit_individual_review_gaps():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from scoring_v4.confidence import _evidence_confidence
    from test_studied_formula_assessment import seed_label
    p = seed_label()
    evidence = score_evidence(p)
    assert evidence["metadata"]["studied_formula_assessment"]["status"] == "assessed_studied_formula"
    # Independent members may have an unfinished native review while the
    # complete formula already has its own source-owned assessment.
    evidence["metadata"]["evidence_assessment"]["native_context_review"] = {
        "status": "pending_clinical_review", "context_ids": ["synthetic-member-review"]}
    _, reasons = _evidence_confidence(p, {"dimensions": {"evidence": evidence}},
        evidence_assessment={"readiness": "complete"})
    assert "evidence_review_incomplete" not in reasons
