"""Exposure-only findings cannot alone unlock the primary Evidence floor (Sean, 2026-11-12).

Authority: scripts/audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md, Part C:
"A finding that demonstrates only exposure, target engagement, or an unvalidated
physiological response cannot, by itself, unlock the primary Evidence floor." Qualified
functional outcomes, accepted surrogates, the nutrition-authority floor, ordinary Evidence
points and completed review status are unchanged. No blanket exclusion of `purpose:
physiology` or `kind: surrogate`.

Owners: the reviewed outcome row carries `surrogate_class` (clinical_evidence_schema
validates it); clinical_applicability.outcomes_beyond_exposure decides which qualifying
outcomes show more than that; generic_evidence._primary_mass_floor consumes it.

Real DSLD labels (tests/fixtures/evidence_floor_*_raw.json, evidence_review_315089_raw.json)
with the values measured on main 648f27224 before this change.
"""
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import pytest

import clinical_applicability
from clinical_applicability import outcomes_beyond_exposure, qualifying_purpose_outcomes, reviewed_entries
from clinical_evidence_schema import SURROGATE_CLASSES, validate_ingredient_context

FIXTURES = Path(__file__).parent / "fixtures"

# Every reviewed context whose qualifying finding is classified, and the class of each
# classified outcome row. A context is classified when every qualifying outcome shows no
# more than the supplied compound or its stores (exposure), the material's direct
# biochemical action (target engagement), or a physiological change that is not an
# established clinical measure defining or monitoring the studied condition. Blood
# pressure, lipids, glycemia in diabetes or prediabetes, TSH, homocysteine in
# hyperhomocysteinemia and functional measures are not classified, and a context with any
# qualifying functional or accepted outcome stays unclassified.
CLASSIFIED = {
    ("INGR_CREATINE_ETHYL_ESTER", "creatine_ethyl_ester_19228401_muscle_content"): {"exposure"},
    ("INGR_REDUCED_GLUTATHIONE", "ingr_reduced_glutathione_24791752"): {
        "exposure", "unvalidated_physiological_response"},
    ("PRECLIN_BETAINE_HCL", "preclin_betaine_hcl_31485804_postprandial_ph"): {"target_engagement"},
    ("INGR_NATTOKINASE", "ingr_nattokinase_26109079"): {"target_engagement"},
    ("INGR_CALCIUM_CASEINATE", "calcium_caseinate_21045172_acute_mps"): {
        "unvalidated_physiological_response"},
    ("BRAND_TESNOR", "brand_tesnor_35129040"): {"unvalidated_physiological_response"},
    ("BRAND_PRIMAVIE_SHILAJIT", "brand_primavie_26395129_androgen_biomarkers"): {
        "unvalidated_physiological_response"},
    ("INGR_BILBERRY", "ingr_bilberry_32106548"): {"unvalidated_physiological_response"},
    ("BRAND_KANEKA_UBIQUINOL", "brand_kaneka_ubiquinol_32326664_draft"): {
        "unvalidated_physiological_response"},
    ("BRAND_CARNIPURE", "brand_carnipure_11788381_lclt_source_review"): {
        "unvalidated_physiological_response"},
    ("INGR_L_CARNOSINE", "l_carnosine_27040154_primary_glycemic"): {
        "unvalidated_physiological_response"},
    ("PRECLIN_NMN", "nmn_glucose_lipid_review_39531138"): {"exposure"},  # meta-analysis: no floor base
}

# Every other scoring-eligible context whose qualifying finding is surrogate-only, kept as an
# accepted clinical measure of its condition or a functional measure recorded as a surrogate.
# A review that makes a context surrogate-only (for example a mixed context losing its
# functional row) must classify it or add it here.
ACCEPTED = {
    ("BRAND_QUATREFOLIC", "quatrefolic_nonqualifying_merck_folate_rct_23698160"),  # homocysteine in hyperhomocysteinemia
    ("INGR_BACOPA", "ingr_bacopa_24252493_bounded_adult_extract_review"),  # cognitive task
    ("INGR_BERBERINE_HCL", "ingr_berberine_hcl_34956436_scoped_source"),  # HbA1c in type 2 diabetes
    ("INGR_CAFFEINE", "ingr_caffeine_33800853_scoped_source"),  # attention task
    ("INGR_CERAMIDES", "ingr_ceramides_38999848"),  # TEWL for a dry skin barrier (close call)
    ("INGR_CERAMIDES", "ingr_ceramides_35719159_ceramide_subgroup"),  # skin hydration
    ("INGR_CREATINE_MONOHYDRATE", "creatine_monohydrate_resistance_training_body_composition_39074168"),  # lean mass
    ("INGR_GARLIC", "garlic_hypertension_meta_32010325"),  # blood pressure
    ("INGR_GLYCINE", "ingr_glycine_22529837_sleep_restriction_source_scope"),  # psychomotor vigilance
    ("INGR_L_ARGININE", "ingr_l_arginine_34967840_blood_pressure"),  # blood pressure
    ("INGR_L_CARNOSINE", "l_carnosine_38172006_primary_glycemic"),  # OGTT glucose (close call)
    ("INGR_L_THEANINE", "ingr_l_theanine_40314930_scoped_source"),  # reaction time
    ("INGR_L_TYROSINE", "ingr_l_tyrosine_24433977"),  # response inhibition task
    ("INGR_L_TYROSINE", "ingr_l_tyrosine_25598314"),  # task switching
    ("INGR_L_TYROSINE", "ingr_l_tyrosine_36548401"),  # reaction times
    ("INGR_L_TYROSINE", "ingr_l_tyrosine_42275440"),  # choice performance
    ("INGR_MAGNESIUM_GENERIC", "ingr_magnesium_generic_41000008_scoped_synthesis"),  # blood pressure
    ("INGR_PANTETHINE", "ingr_pantethine_24600231"),  # LDL cholesterol
    ("INGR_PLANT_STEROLS", "ingr_plant_sterols_24144075_bounded_source_scope"),  # LDL cholesterol
    ("INGR_POTASSIUM", "ingr_potassium_40612568_scoped_source"),  # blood pressure
    ("INGR_PSYLLIUM_HUSK", "ingr_psyllium_30239559_lipid_marker_review"),  # LDL cholesterol
    ("INGR_QUERCETIN", "ingr_quercetin_27405810_scoped_source"),  # blood pressure
    ("INGR_SELENIUM", "ingr_selenium_38243784_scoped_source"),  # TSH in Hashimoto's (close call)
    ("INGR_TAURINE", "ingr_taurine_26781281_prehypertension_bp"),  # blood pressure
    ("PRECLIN_BERBERINE_GENERIC", "preclin_berberine_generic_34956436_scoped_source"),  # HbA1c in type 2 diabetes
}

ATTRIBUTION = ("Outcome surrogate_class values are agent classification (Claude, 2026-11-12) applying Sean's "
               "Evidence-floor rule")


def _context(record_id, context_id):
    return next(c for c in reviewed_entries()[record_id]["study_contexts"] if c["context_id"] == context_id)


# --- the outcome contract -----------------------------------------------------------

def test_surrogate_class_vocabulary_is_the_three_named_findings():
    assert SURROGATE_CLASSES == {"exposure", "target_engagement", "unvalidated_physiological_response"}


@pytest.mark.parametrize("value,kind,error", [
    ("exposure", "surrogate", None),
    ("biomarker", "surrogate", "outcome[0].surrogate_class_invalid"),
    ("exposure", "patient_important", "outcome[0].surrogate_class_requires_surrogate_kind"),
])
def test_schema_validates_surrogate_class(value, kind, error):
    context = deepcopy(_context("INGR_CREATINE_ETHYL_ESTER", "creatine_ethyl_ester_19228401_muscle_content"))
    context["outcomes"][0].update(surrogate_class=value, kind=kind)
    errors = validate_ingredient_context(context, require_complete_review=True)
    assert (error in errors) if error else not any("surrogate_class" in e for e in errors)


def test_every_classified_row_is_a_surrogate_in_a_valid_context():
    for (record_id, context_id), classes in CLASSIFIED.items():
        context = _context(record_id, context_id)
        rows = [row for row in context["outcomes"] if "surrogate_class" in row]
        assert rows, (record_id, context_id)
        assert {row["surrogate_class"] for row in rows} == classes
        assert all(row["kind"] == "surrogate" for row in rows)
        assert validate_ingredient_context(context, require_complete_review=True) == []


def test_only_the_reviewed_contexts_are_classified():
    """No blanket rule: accepted surrogates, functional measures and every other context
    stay unclassified."""
    classified = {(entry_id, context["context_id"])
                  for entry_id, entry in reviewed_entries().items()
                  for context in entry.get("study_contexts") or []
                  if any("surrogate_class" in row for row in context.get("outcomes") or [])}
    assert classified == set(CLASSIFIED)


def test_every_surrogate_only_finding_was_reviewed_under_the_rule():
    """The census: each scoring-eligible context whose qualifying outcomes are all
    surrogates is either classified or a reviewed accepted/functional measure."""
    surrogate_only = {(entry_id, context["context_id"])
                      for entry_id, entry in reviewed_entries().items()
                      for context in entry.get("study_contexts") or []
                      if context.get("scoring_eligible") is True
                      and (rows := qualifying_purpose_outcomes(context)[0])
                      and all(row.get("kind") == "surrogate" for row in rows)}
    assert not set(CLASSIFIED) & ACCEPTED
    assert surrogate_only == set(CLASSIFIED) | ACCEPTED


def test_classified_contexts_record_the_classification_as_agent_work():
    for record_id, context_id in CLASSIFIED:
        limitations = " ".join(_context(record_id, context_id)["limitations"])
        assert ATTRIBUTION in limitations and "DR_PHAM_ANSWERS_20261112.md Part C" in limitations
        assert "not part of this context's clinician review" in limitations


# --- the clinical-outcome owner -------------------------------------------------------

def test_exposure_only_context_has_no_outcome_beyond_exposure():
    context = _context("INGR_CREATINE_ETHYL_ESTER", "creatine_ethyl_ester_19228401_muscle_content")
    assert qualifying_purpose_outcomes(context)[0]          # it still qualifies ordinary Evidence
    assert outcomes_beyond_exposure(context) == []


@pytest.mark.parametrize("record_id,context_id", [
    ("INGR_POTASSIUM", "ingr_potassium_40612568_scoped_source"),             # accepted surrogate: BP
    ("INGR_PSYLLIUM_HUSK", "ingr_psyllium_30239559_lipid_marker_review"),    # accepted surrogate: LDL
    ("INGR_GLYCINE", "ingr_glycine_22529837_sleep_restriction_source_scope"),  # functional: PVT
    ("BRAND_TESNOR", "brand_tesnor_35928723_draft"),                         # patient-important AMS
    ("BRAND_CARNIPURE", "brand_carnipure_20045157_lclt_source_review"),      # patient-important soreness
    # Close calls kept as accepted: each is a clinical measure of the studied condition.
    ("INGR_SELENIUM", "ingr_selenium_38243784_scoped_source"),               # TSH in Hashimoto's
    ("INGR_L_CARNOSINE", "l_carnosine_38172006_primary_glycemic"),           # OGTT glucose
    ("INGR_CERAMIDES", "ingr_ceramides_38999848"),                           # TEWL, skin barrier
])
def test_accepted_and_functional_findings_remain_beyond_exposure(record_id, context_id):
    context = _context(record_id, context_id)
    assert outcomes_beyond_exposure(context) == qualifying_purpose_outcomes(context)[0] != []


# --- the Evidence owner: mixed research and no borrowing ------------------------------

def _scoped_match(record_id, context_ids, study_type="rct_single"):
    return {"id": record_id, "standard_name": "Test Ingredient", "study_type": study_type,
            "evidence_level": "ingredient-human", "effect_direction": "positive_strong",
            "applicability_assessment": {"status": "applicable", "population_applicability": {
                "state": "eligible", "context_ids": list(context_ids)}}}


def _record_with(contexts):
    return {"id": "TEST_RECORD", "study_contexts": contexts}


def _ctx(context_id, outcome):
    return {"context_id": context_id, "scoring_eligible": True, "evidence_role": "direct_rct",
            "outcomes": [{"name": context_id, "hierarchy": "primary", "direction": "positive",
                          "outcome_role": "direct_between_group_effect", **outcome}]}


EXPOSURE = {"kind": "surrogate", "surrogate_class": "exposure"}
FUNCTIONAL = {"kind": "patient_important"}


@pytest.mark.parametrize("contexts,qualified,study_type,expected", [
    ([_ctx("a", EXPOSURE)], ["a"], "rct_single", None),                     # exposure alone: no floor
    ([_ctx("a", EXPOSURE), _ctx("b", FUNCTIONAL)], ["a", "b"], "rct_single", "rct_single"),  # mixed: functional qualifies
    ([_ctx("a", EXPOSURE), _ctx("b", FUNCTIONAL)], ["a"], "rct_single", None),  # no borrowing from a non-applicable context
    ([_ctx("a", {"kind": "surrogate"})], ["a"], "rct_single", "rct_single"),  # unclassified surrogate: no blanket exclusion
    ([], [], "rct_single", "rct_single"),                                   # no reviewed context: rule cannot apply
    # An exposure-only trial cannot strengthen the floor either: two families, one beyond exposure.
    ([_ctx("a", EXPOSURE), _ctx("b", FUNCTIONAL)], ["a", "b"], "rct_multiple", "rct_single"),
    ([_ctx("a", FUNCTIONAL), _ctx("b", FUNCTIONAL)], ["a", "b"], "rct_multiple", "rct_multiple"),
    # The record's own design is kept when no exposure-only trial supplied the second family.
    ([_ctx("b", FUNCTIONAL)], ["b"], "rct_multiple", "rct_multiple"),
    ([_ctx("a", EXPOSURE), {**_ctx("b", FUNCTIONAL), "evidence_role": "meta_analysis"}], ["a", "b"],
     "rct_multiple", "rct_multiple"),
    ([_ctx("a", EXPOSURE), _ctx("b", FUNCTIONAL)], ["b", 7], "rct_single", "rct_single"),  # non-string ids ignored
])
def test_floor_study_type_reads_only_the_applicable_contexts(monkeypatch, contexts, qualified, study_type, expected):
    from scoring_v4.modules import generic_evidence as ge
    monkeypatch.setattr(clinical_applicability, "reviewed_entries", lambda: {"TEST_RECORD": _record_with(contexts)})
    assert ge._floor_study_type(_scoped_match("TEST_RECORD", qualified, study_type)) == expected


# --- the production seam on real labels ---------------------------------------------

@lru_cache(maxsize=1)
def _pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


@lru_cache(maxsize=None)
def _scored(fixture):
    from scoring_v4.scored_artifact import build_scored_artifact
    normalizer, enricher = _pipeline()
    raw = json.loads((FIXTURES / fixture).read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return build_scored_artifact(enriched)


def _evidence(fixture):
    artifact = _scored(fixture)
    pillar = artifact["quality_pillars_v4"]["evidence"]
    receipt = {row["id"]: row["points"] for row in pillar["receipt"]["entries"]}
    metadata = artifact["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"]
    return artifact, pillar, receipt, metadata


# fixture, restricted floor canonical, ordinary pipeline points measured before the change
RESTRICTED = [
    ("evidence_floor_223084_raw.json", "creatine ethyl ester", 2.4),   # muscle creatine content
    ("evidence_floor_312552_raw.json", "reduced l glutathione", 1.92),  # blood glutathione
    ("evidence_floor_312864_raw.json", "betaine hcl", 3.4),             # gastric pH
    ("evidence_floor_277963_raw.json", "nattokinase", 1.44),            # fibrinolysis markers
    ("evidence_floor_19483_raw.json", "calcium caseinate", 7.48),       # acute muscle protein synthesis
    ("evidence_floor_330411_raw.json", "bilberry", 4.0),                # HFC-1 ciliary accommodation marker
]


@pytest.mark.parametrize("fixture,canonical,ordinary", RESTRICTED)
def test_exposure_only_finding_no_longer_anchors_the_floor(fixture, canonical, ordinary):
    artifact, pillar, receipt, metadata = _evidence(fixture)
    assert metadata.get("primary_evidence_floor_canonical") != canonical
    # Ordinary Evidence credit and the completed review are unchanged.
    assert receipt["clinical_evidence_pipeline"] == ordinary
    assert artifact["quality_assessment_status"] == "complete"
    assert pillar["evidence_result_state"] == "evaluated_applicable"


@pytest.mark.parametrize("fixture,canonical,floor", [
    # Potassium is also an essential nutrient, so its established role (full, 18,
    # since 2026-11-13) is now the decisive floor above the accepted surrogate's 14.
    ("evidence_floor_330065_raw.json", "potassium", 18.0),   # accepted surrogate: blood pressure
    ("evidence_review_315089_raw.json", "tesnor", 9.35),     # mixed: patient-important AMS context
])
def test_accepted_or_functional_findings_keep_their_floor(fixture, canonical, floor):
    _, _, _, metadata = _evidence(fixture)
    assert metadata["primary_evidence_floor_canonical"] == canonical
    assert metadata["primary_evidence_floor"] == floor
    assert metadata["primary_evidence_floor_decisive"] is True
