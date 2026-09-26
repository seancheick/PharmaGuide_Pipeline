"""Clinical credit follows source evidence, not wording or blend length."""
from copy import deepcopy

import pytest

import studied_formulas
from scoring_v4.modules.probiotic_evidence import score_evidence
from test_studied_formula_assessment import seed_label


def strain_product(*, dose=None, clinical_id="STRAIN_LGG", name="Lactobacillus rhamnosus GG"):
    row = {"name": name, "raw_source_path": "ingredientRows[0]", "quantity": dose or 0,
           "unit": "CFU" if dose else "NP"}
    return {"product_name": "Daily Probiotic", "form_factor_canonical": "capsule",
            "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1,
                              "servings_per_day_source": "label"},
            "activeIngredients": [row],
            "probiotic_data": {"probiotic_blends": [{"strains": [name],
                "raw_source_path": row["raw_source_path"], "cfu_data": {
                    "has_cfu": dose is not None,
                    "cfu_count": dose, "raw_source_path": row["raw_source_path"],
                    "evidence_scope": "row_level"}}], "clinical_strains": [{"strain": name,
                "clinical_id": clinical_id, "source_row_ref": row["raw_source_path"],
                "cfu_per_day": dose, "adequacy_tier": "good" if dose else None,
                "clinical_support_level": "high", "indication_primary": "digestive"}]}}


@pytest.mark.parametrize("phrase", ["Digestive support", "Immune support", "Gut health", ""])
def test_formula_core_evidence_is_invariant_to_marketing(phrase):
    p = seed_label()
    before = score_evidence(p)
    p["statements"] = [{"type": "Formulation re: Other", "notes": phrase}]
    after = score_evidence(p)
    assert before["score"] == after["score"]
    assert before["components"] == after["components"]
    assert "claim_alignment" in after["metadata"]
    assert studied_formulas.assess_studied_formula(p)["status"] == "assessed_studied_formula"


def test_many_undosed_strains_cannot_accumulate_full_evidence():
    p = strain_product()
    one = score_evidence(p)
    for index, (cid, name) in enumerate([
        ("STRAIN_RHAMNOSUS_HN001", "Lactobacillus rhamnosus HN001"),
        ("STRAIN_LONGUM_BB536", "Bifidobacterium longum BB536"),
        ("STRAIN_LACTIS_BB12", "Bifidobacterium lactis BB-12"),
    ], 1):
        other = strain_product(clinical_id=cid, name=name)
        other["activeIngredients"][0]["raw_source_path"] = f"ingredientRows[{index}]"
        other["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = f"ingredientRows[{index}]"
        p["activeIngredients"] += other["activeIngredients"]
        p["probiotic_data"]["clinical_strains"] += other["probiotic_data"]["clinical_strains"]
    assert score_evidence(p)["score"] == one["score"]
    assert score_evidence(p)["score"] < 20


def _pending_registry(monkeypatch, *ids):
    """Reset the named identities' contexts to pending so the test isolates the
    rubric from the live 2026-09-14 approvals (an approved context with no
    matching tested arm is 'not_applicable', a different status)."""
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    for entry in registry.values():  # combination contexts owned elsewhere also carry the strain
        for context in entry.get("study_contexts", []):
            if set(ids) & set(context.get("components", [])):
                context["review_status"] = "source_verified_pending_clinical_review"
                context.pop("clinical_review", None)
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    return registry


def test_industry_tiers_cannot_be_called_a_verified_clinical_dose(monkeypatch):
    _pending_registry(monkeypatch, "STRAIN_LGG")
    p = strain_product(dose=10_000_000_000)
    p["probiotic_data"]["clinical_strains"][0]["dose_basis"] = "clinical"  # stale/caller stamp
    assessment = studied_formulas.assess_probiotic_evidence(p)
    row = assessment["strain_assessments"][0]
    assert row["status"] == "strain_context_review_pending"
    assert row["dose_applicable"] is False


def test_native_dose_copy_distinguishes_potency_from_clinical_efficacy():
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.quality_score import _probiotic_dose_reason

    dose = score_dose(strain_product(dose=1e10))
    assert dose["metadata"]["reference_basis"] == "industry_potency_not_trial_efficacy"
    assert "not proof of clinical benefit" in _probiotic_dose_reason(dose, "fallback")


def test_species_research_is_not_presented_as_exact_strain_evidence(monkeypatch):
    from scoring_v4.quality_score import _pillar_evidence

    registry = _pending_registry(monkeypatch, "STRAIN_SACCHAROMYCES")
    registry["STRAIN_SACCHAROMYCES"]["cfu_thresholds"]["evidence"]["clinical_validation"] = {
        "q1_strain_explicit": "NO", "q3_human_clinical": "YES"}

    p = strain_product(dose=5e9, clinical_id="STRAIN_SACCHAROMYCES",
                       name="Saccharomyces boulardii")
    # A copied status must not upgrade the registry's species-general scope.
    p["probiotic_data"]["clinical_strains"][0]["research_match_status"] = "exact_strain"
    evidence = score_evidence(p)
    row = evidence["metadata"]["evidence_assessment"]["strain_assessments"][0]
    assert row["evidence_scope"] == "species_general"
    assert row["status"] == "strain_context_review_pending"
    assert row["dose_applicable"] is False
    assert evidence["metadata"]["native_clinical_strain_evidence_rows"][0]["evidence_scope"] == "species_general"
    cfg = {"evidence_subscale": {"archetype_reference": {"probiotic": 20}, "default_reference": 20}}
    # Its contexts await clinician review, so the assessment is open whatever
    # the species research earned: the copy says so and claims no strain evidence.
    assert evidence["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    copy = _pillar_evidence(evidence, 20, "probiotic", cfg)["reason"]
    assert "still open" in copy
    assert "Named strains" not in copy


def test_finished_species_research_copy_names_its_scope():
    from scoring_v4.quality_score import _pillar_evidence

    dim = {"score": 3.0, "metadata": {
        "evidence_result_state": "research_present_applicability_unestablished",
        "credit_owner": "strain",
        "evidence_assessment": {"strain_assessments": [{"research_accepted": True, "cfu_per_day": 5e9}]},
        "native_clinical_strain_evidence_rows": [{"evidence_scope": "species_general"}],
    }}
    cfg = {"evidence_subscale": {"archetype_reference": {"probiotic": 20}, "default_reference": 20}}
    copy = _pillar_evidence(dim, 20, "probiotic", cfg)["reason"]
    assert "species-level" in copy
    assert "exact studied strain" in copy
    assert "Named strains" not in copy


@pytest.mark.parametrize("field,value", [
    ("source_pmids", [None]), ("supported_outcomes", [""]),
    ("dosage_forms", [None]), ("target_population", {}),
])
def test_malformed_curated_scope_is_unreviewed(reviewed_dose, field, value):
    studied_formulas._clinical_strain_registry()["STRAIN_LGG"]["applicability"][field] = value
    assessment = studied_formulas.assess_probiotic_evidence(strain_product(dose=1e10))
    assert assessment["strain_assessments"][0]["status"] == "strain_dose_reference_unreviewed"


def test_unknown_dose_and_wrong_strain_are_distinct():
    unknown = studied_formulas.assess_probiotic_evidence(strain_product())
    wrong = studied_formulas.assess_probiotic_evidence(strain_product(name="Lactobacillus rhamnosus HN001"))
    assert unknown["strain_assessments"][0]["status"] == "strain_dose_unknown"
    assert wrong["strain_assessments"][0]["status"] == "strain_identity_mismatch"
    assert score_evidence(strain_product(name="Lactobacillus rhamnosus HN001"))["score"] == 0


@pytest.mark.parametrize("owners,accepted", [(0, False), (1, True), (2, False)])
def test_legacy_native_match_requires_one_actual_label_owner(owners, accepted):
    p = strain_product()
    p["probiotic_data"]["clinical_strains"][0].pop("source_row_ref")
    owner = p["activeIngredients"][0]
    p["activeIngredients"] = [{**owner, "raw_source_path": f"ingredientRows[{i}]"} for i in range(owners)]
    result = studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]
    assert result["research_accepted"] is accepted
    assert (score_evidence(p)["score"] > 0) is accepted


@pytest.fixture
def reviewed_dose(monkeypatch):
    # A historical single-range shape is deliberately no longer sufficient.
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    # Isolate this legacy-boundary fixture from newly pending real contexts —
    # both LGG-owned and combination contexts owned elsewhere that join LGG
    # (Wave 2 curation). The separate native-context suite proves they cannot
    # be bypassed.
    registry["STRAIN_LGG"].pop("study_contexts", None)
    for rid, row in registry.items():
        if row.get("study_contexts"):
            row["study_contexts"] = [c for c in row["study_contexts"]
                                     if "STRAIN_LGG" not in c.get("components", [])]
    registry["STRAIN_LGG"]["applicability"] = {
        "dose_unit": "CFU", "minimum_daily_dose": 1e9, "maximum_daily_dose": 2e10,
        "dosage_forms": ["capsule"], "target_population": "adult",
        "studied_population": "Synthetic adult test population",
        "supported_outcomes": ["digestive"], "source_pmids": ["26756877"],
    }
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)


@pytest.mark.parametrize("change,expected", [
    (None, "strain_dose_reference_unreviewed"), ("low", "strain_dose_reference_unreviewed"),
    ("high", "strain_dose_reference_unreviewed"), ("form", "strain_dose_reference_unreviewed"),
    ("unknown", "strain_dose_unknown"),
])
def test_legacy_single_range_never_proves_native_applicability(reviewed_dose, change, expected):
    p = strain_product(dose=1e10)
    for key, value in (("low", 1e6), ("high", 1e12), ("unknown", None)):
        if change == key:
            p["probiotic_data"]["probiotic_blends"][0]["cfu_data"]["cfu_count"] = value
    if change == "form": p["form_factor_canonical"] = "yogurt"
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["status"] == expected


def test_unknown_dose_does_not_receive_exact_dose_evidence_credit(reviewed_dose):
    known, unknown = score_evidence(strain_product(dose=1e10)), score_evidence(strain_product())
    assert known["score"] == unknown["score"]
    assert known["components"]["dose_applicability"] == unknown["components"]["dose_applicability"] == 0


def test_formula_dose_not_reduced_for_unknown_individual_allocations():
    from scoring_v4.modules.probiotic_dose import score_dose
    dose = score_dose(seed_label())
    assert dose["score"] == dose["max"]
    assert dose["metadata"]["per_strain_cfu_disclosed_count"] == 0
    assert "per_strain_cfu_disclosure" not in dose["components"]


def test_caller_dose_cannot_override_owner_measurement(reviewed_dose):
    from scoring_v4.modules.probiotic_dose import score_dose
    p = strain_product(dose=1e6)
    expected = score_dose(p)
    p["probiotic_data"]["clinical_strains"][0]["cfu_per_day"] = 1e10
    p["probiotic_data"]["clinical_strains"][0]["adequacy_tier"] = "excellent"
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["cfu_per_day"] == 1e6
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["dose_applicable"] is False
    assert score_dose(p)["score"] == expected["score"]
    assert score_dose(p)["metadata"]["cfu_adequacy_contributions"][0]["cfu_per_day"] == 1e6


def test_caller_stamp_alone_does_not_create_disclosed_strain_dose():
    from scoring_v4.modules.probiotic_dose import score_dose
    p = strain_product()
    p["probiotic_data"]["clinical_strains"][0]["cfu_per_day"] = 1e10
    p["probiotic_data"]["clinical_strains"][0]["adequacy_tier"] = "excellent"
    assert score_dose(p)["components"]["per_strain_cfu_disclosure"] == 0


def test_blend_total_cannot_be_borrowed_by_one_strain(reviewed_dose):
    p = strain_product(dose=1e10)
    p["probiotic_data"]["probiotic_blends"][0]["strains"].append("Different strain")
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["status"] == "strain_dose_unknown"


def test_generic_strain_entry_cannot_bypass_wrong_identity():
    from test_v4_probiotic_evidence_p23 import _match
    p = strain_product(name="Lactobacillus rhamnosus HN001")
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG")]}
    assert score_evidence(p)["score"] == 0


def test_evidence_metadata_is_json_serializable():
    import json
    json.dumps(score_evidence(seed_label()), allow_nan=False)


def test_registry_medium_support_is_not_lost():
    # 299v: medium support with a positive between-group result. (BB536 was the example
    # until its biomarker-only record was recorded as unresolved on 2026-09-22.)
    p = strain_product(clinical_id="STRAIN_PLANTARUM_299V", name="Lactobacillus plantarum 299v")
    assert score_evidence(p)["score"] == 9


def test_unfavorable_strain_does_not_hide_a_separate_supported_record():
    from test_v4_probiotic_evidence_p23 import _match
    p = strain_product()
    other = strain_product(clinical_id="STRAIN_PLANTARUM_299V", name="Lactobacillus plantarum 299v")
    other["activeIngredients"][0]["raw_source_path"] = "ingredientRows[1]"
    other["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[1]"
    p["activeIngredients"] += other["activeIngredients"]
    p["probiotic_data"]["clinical_strains"] += other["probiotic_data"]["clinical_strains"]
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG", effect_direction="negative")]}
    assert score_evidence(p)["score"] == 9


def test_evidence_copy_distinguishes_missing_applicability_from_poor_quality():
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config
    dim = score_evidence(strain_product())
    result = _pillar_evidence(dim, 20, "probiotic", config())
    assert "dose is not established for this label" in result["reason"]


def test_unfavorable_research_is_not_described_as_missing_research():
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config
    from test_v4_probiotic_evidence_p23 import _match

    p = strain_product()
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG", effect_direction="negative")]}
    dim = score_evidence(p)
    assert dim["score"] == 0
    assert dim["metadata"]["evidence_result_state"] == "evaluated_unfavorable"
    assert "unfavorable" in _pillar_evidence(dim, 20, "probiotic", config())["reason"]


def test_unrecognized_effect_is_not_a_negative_clinical_finding():
    from test_v4_probiotic_evidence_p23 import _match
    p = strain_product()
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG", effect_direction="unreviewed")]}
    assert score_evidence(p)["metadata"]["evidence_result_state"] != "evaluated_unfavorable"


def test_seed_companion_publication_does_not_upgrade_independent_efficacy():
    from clinical_applicability import reviewed_entries
    from studied_formulas import formula_clinical_match
    entry = reviewed_entries()["FORMULA_SEED_DS01"]
    assert {r["pmid"] for r in entry["references_structured"]} == {"41599868", "40944126", "41750436"}
    assert entry["study_type"] == "rct_single"
    assert entry["total_enrollment"] == 350
    assert entry["effect_direction"] == "positive_weak"
    assert entry["formula_contract"]["supported_outcomes"] == ["digestive"]
    match = formula_clinical_match(seed_label())
    assert "published_studies_count" not in match  # publications != independent replications
    assert "per-blend" in match["applicability_assessment"]["limitations"]


@pytest.mark.parametrize("scope,source,removed", [
    ("probiotic_strains_only", "ingredientRows[0]", True),
    ("mixed_or_unresolved", "ingredientRows[0]", False),
    ("probiotic_strains_only", "ingredientRows[9]", False),
])
def test_disclosure_opacity_consolidates_only_owned_pure_strain_blend(scope, source, removed):
    from scoring_v4.modules.probiotic_transparency import score_transparency
    from test_v4_probiotic_transparency_p25 import _probiotic
    names = ["Lactobacillus rhamnosus GG", "Bifidobacterium lactis BB-12"]
    p = _probiotic(strain_count=2, blends=[{"strains": names, "raw_source_path": source,
                   "cfu_data": {"has_cfu": True, "billion_count": 20}}])
    p["probiotic_data"]["strain_allocation_owner_refs"] = [source] if scope == "probiotic_strains_only" else []
    p["activeIngredients"] = [{"name": "Probiotic Complex", "raw_source_path": "ingredientRows[0]",
        "quantity": 100, "unit": "mg", "nestedIngredients": [{"name": n} for n in names]}]
    p["proprietary_blends"] = [{"name": "Probiotic Complex", "disclosure_level": "partial",
        "child_ingredients": [{"name": n} for n in names], "blend_total_mg": 100,
        "source_path": "activeIngredients[0]", "source_row_ref": "ingredientRows[0]", "hidden_count": 2}]
    p["proprietary_data"] = {"total_active_mg": 100, "total_active_ingredients": 2}
    result = score_transparency(p)
    assert (result["penalties"]["B5_proprietary_blend_opacity"] == 0) is removed
    assert result["components"]["per_strain_cfu_on_label"] == 0
    assert result["components"]["aggregate_cfu_disclosure_proxy"] == 4


def test_stale_positional_reference_cannot_consolidate_a_different_blend():
    from scoring_v4.modules.probiotic_transparency import _consolidate_strain_allocation_opacity
    evidence = [{"blend_name": "Prebiotic Blend", "source_path": "activeIngredients[0]",
                 "computed_blend_penalty_magnitude": 1, "computed_blend_penalty": -1}]
    pdata = {"strain_allocation_owner_refs": ["ingredientRows[0]"]}
    penalty, _ = _consolidate_strain_allocation_opacity(pdata, {"status": "unresolved"}, evidence)
    assert penalty == 1


# ── Evidence credit ownership (Codex audit 2026-09-16) ───────────────────────
# Probiotic strain credit is max(generic, native), and the generic side can
# include vitamins, botanicals or fiber. The Evidence module owns the question
# "who earned this credit" and emits it; the pillar copy reads that result and
# never re-infers ownership from ingredient names.

def _companion_generic(monkeypatch, *, with_companion: float, without_companion: float):
    from scoring_v4.modules import probiotic_evidence

    def fake_generic(product, accepted_matches=None):
        has_companion = any(m.get("id") == "INGR_VITAMIN_C" for m in accepted_matches or [])
        score = with_companion if has_companion else without_companion
        return {"score": score, "metadata": {}}

    monkeypatch.setattr(probiotic_evidence, "score_generic_evidence", fake_generic)


def _vitamin_c_match():
    from test_v4_probiotic_evidence_p23 import _match
    return _match(id="INGR_VITAMIN_C", ingredient="Vitamin C", standard_name="Vitamin C",
                  study_type="systematic_review_meta", evidence_level="ingredient-human")


def test_companion_only_credit_is_owned_by_companions(monkeypatch):
    _companion_generic(monkeypatch, with_companion=5.4, without_companion=0.0)
    p = strain_product(clinical_id="STRAIN_NOT_IN_REGISTRY", name="Lactobacillus sp. XYZ-1")
    p["evidence_data"] = {"clinical_matches": [_vitamin_c_match()]}
    md = score_evidence(p)["metadata"]
    assert md["credit_owner"] == "companion"
    assert md["strain_points"] == 0.0
    assert md["companion_points"] == md["final_points"] > 0


def test_capped_strain_credit_is_owned_by_strains_despite_a_tiny_companion(monkeypatch):
    """15 points of Lactobacillus research plus 0.1 of vitamin C is strain
    credit, not "credit from other ingredients"."""
    _companion_generic(monkeypatch, with_companion=15.1, without_companion=15.0)
    p = strain_product()
    p["evidence_data"] = {"clinical_matches": [_vitamin_c_match()]}
    md = score_evidence(p)["metadata"]
    assert md["credit_owner"] == "strain"
    assert md["companion_points"] == 0.0


def test_partial_companion_lift_is_mixed(monkeypatch):
    _companion_generic(monkeypatch, with_companion=5.4, without_companion=3.0)
    p = strain_product(clinical_id="STRAIN_NOT_IN_REGISTRY", name="Lactobacillus sp. XYZ-1")
    p["evidence_data"] = {"clinical_matches": [_vitamin_c_match()]}
    md = score_evidence(p)["metadata"]
    assert md["credit_owner"] == "mixed"
    assert md["strain_points"] == 3.0
    assert md["companion_points"] == pytest.approx(md["final_points"] - 3.0)


def test_studied_formula_does_not_hide_companion_credit(monkeypatch):
    """A studied-formula match describes the probiotic-owned portion; it must
    not claim ownership of additional Evidence points supplied by a companion
    ingredient."""
    _companion_generic(monkeypatch, with_companion=8.0, without_companion=6.0)
    p = seed_label()
    p["evidence_data"] = {"clinical_matches": [_vitamin_c_match()]}

    evidence = score_evidence(p)
    md = evidence["metadata"]
    assert md["studied_formula_assessment"]["status"] == "assessed_studied_formula"
    assert md["credit_owner"] == "mixed"
    assert md["strain_points"] == 6.0
    assert md["companion_points"] == 2.0

    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config
    reason = _pillar_evidence(evidence, 20, "probiotic", config())["reason"]
    assert "combines" in reason
    assert "complete formula" not in reason


@pytest.mark.parametrize("owner, expected, absent", [
    ("companion", "other ingredients", "Named strains"),
    ("mixed", "combines", "Named strains have reviewed research;"),
    ("strain", "Named strains", "other ingredients"),
])
def test_evidence_copy_reads_the_module_credit_owner(owner, expected, absent):
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config

    dim = {
        "score": 8.0,
        "metadata": {
            "evidence_result_state": "research_present_applicability_unestablished",
            "evidence_assessment": {"strain_assessments": [
                {"research_accepted": True, "dose_applicable": owner != "strain"},
            ]},
            "credit_owner": owner,
            "native_clinical_strain_evidence_rows": [{"evidence_scope": "strain_specific"}],
        },
    }
    if owner == "strain":
        dim["metadata"]["evidence_assessment"]["strain_assessments"][0]["dose_applicable"] = False
    reason = _pillar_evidence(dim, 20, "probiotic", config())["reason"]
    assert expected in reason
    assert absent not in reason


@pytest.mark.parametrize("dose_applicable, expected", [
    (True, "matches the disclosed dose"),
    (False, "is not established"),
])
def test_mixed_credit_copy_follows_strain_dose_applicability(dose_applicable, expected):
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config

    dim = {"score": 8.0, "metadata": {
        "evidence_result_state": "research_present_applicability_unestablished",
        "evidence_assessment": {"strain_assessments": [
            {"research_accepted": True, "dose_applicable": dose_applicable}]},
        "credit_owner": "mixed",
    }}
    assert expected in _pillar_evidence(dim, 20, "probiotic", config())["reason"]
