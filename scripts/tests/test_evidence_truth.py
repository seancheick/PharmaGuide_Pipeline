"""Missing research, unfinished processing or bad matching never reads as a scientific zero.

A completed zero and an unresolved review stay distinct on every route, and neither
earns credit here (Sean, November 3, 2026). Every label here is a real DSLD label.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
NOT_ESTABLISHED = "has not established a match"
DID_NOT_QUALIFY = (
    "Human research exists for this ingredient, but the reviewed studies do not qualify for Evidence "
    "credit for the preparation or purpose assessed in this product. This does not mean the "
    "ingredient has never been studied."
)


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _enrich(pipeline, label):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / label).read_text())
    return enricher.enrich_product(normalizer.normalize_product(raw))[0]


# Open review, Evidence 0: read "not established" before this, across the routes that had it.
@pytest.mark.parametrize("label, module", [
    pytest.param("evidence_truth_231852_raw.json", "generic", id="generic_ubiquinol_contexts_missing"),
    pytest.param("evidence_truth_252423_raw.json", "generic", id="generic"),
    pytest.param("evidence_truth_253729_raw.json", "fiber_digestive", id="fiber"),
    pytest.param("evidence_truth_295065_raw.json", "sports", id="sports"),
    pytest.param("evidence_truth_18174_raw.json", "probiotic", id="probiotic"),
])
def test_an_open_review_reads_as_open(pipeline, label, module):
    from assessment_readiness import evidence_review_open
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, label))
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["_v4_module_breakdown"]["module"] == module
    assert scored["quality_assessment_status"] == "partial"
    assert evidence_review_open(scored["assessment_readiness"]["release_assessment"])
    assert evidence["score"] == 0
    assert evidence["evidence_result_state"] in {
        "applicability_unestablished", "research_present_applicability_unestablished"}
    assert evidence["display_state"] == "not_yet_reviewed"
    assert "review pending" in evidence["reason"]
    assert NOT_ESTABLISHED not in evidence["reason"]


def test_a_finished_rejection_of_human_studies_says_they_did_not_qualify(pipeline):
    """Sean's sentence, November 4. 60601's CoQ10 trials cover a purpose this label doesn't claim."""
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, "evidence_truth_60601_raw.json"))
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["quality_assessment_status"] == "complete"
    assert evidence["score"] == 0
    assert evidence["display_state"] == "applicability_unestablished"
    assert evidence["reason"].startswith(DID_NOT_QUALIFY)
    assert NOT_ESTABLISHED not in evidence["reason"]


@pytest.mark.parametrize("label", [
    "evidence_truth_252353_raw.json",  # A reference-only record: human research isn't established.
])
def test_the_did_not_qualify_sentence_stays_off_every_other_cause(pipeline, label):
    from scoring_v4.scored_artifact import build_scored_artifact

    evidence = build_scored_artifact(_enrich(pipeline, label))["quality_pillars_v4"]["evidence"]
    assert evidence["score"] == 0
    assert NOT_ESTABLISHED in evidence["reason"]
    assert DID_NOT_QUALIFY not in evidence["reason"]


def test_reviewed_research_without_a_scoring_path_remains_pending(pipeline):
    """76837 has reviewed positive literature, but the scorer cannot award it yet."""
    from assessment_readiness import evidence_review_open
    from build_final_db import build_detail_blob
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "evidence_truth_76837_raw.json")
    scored = build_scored_artifact(enriched)
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["quality_assessment_status"] == "partial"
    assert evidence_review_open(scored["assessment_readiness"]["release_assessment"])
    assert evidence["score"] == 0  # No new clinical credit or magnitude policy.
    assert evidence["display_state"] == "not_yet_reviewed"
    assert "review pending" in evidence["reason"]
    assert NOT_ESTABLISHED not in evidence["reason"]
    assert DID_NOT_QUALIFY not in evidence["reason"]
    blob = build_detail_blob(enriched, scored)
    assert blob["quality_assessment_status"] == "partial"
    assert blob["quality_pillars_v4"]["evidence"] == evidence
    assert blob["product_safety_status"] == scored["product_safety_status"]


def test_an_open_review_never_says_the_studies_did_not_qualify(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    evidence = build_scored_artifact(_enrich(pipeline, "evidence_truth_231852_raw.json"))["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] == "not_yet_reviewed"
    assert DID_NOT_QUALIFY not in evidence["reason"]


def test_a_rejected_record_without_human_studies_does_not_say_human_research_exists():
    from assessment_readiness import evidence_studies_did_not_qualify

    def readiness(reason):
        return {"evidence": {"ingredient_assessments": [
            {"canonical_id": "glucosamine", "name": "Glucosamine", "reason_code": reason}]}}

    def product(record):
        return {"evidence_data": {"rejected_clinical_matches": [
            {"id": record, "ingredient": "Glucosamine", "reason_code": "clinical_form_mismatch"}]}}

    required = {"glucosamine"}
    assert evidence_studies_did_not_qualify(product("INGR_COQ10"), readiness("clinical_form_mismatch"), required)
    assert not evidence_studies_did_not_qualify(product("INGR_GLUCOSAMINE_SULFATE"), readiness("clinical_form_mismatch"), required)
    assert not evidence_studies_did_not_qualify(product("INGR_COQ10"), readiness("reference_only_clinical_record"), required)
    assert not evidence_studies_did_not_qualify(product("INGR_COQ10"), readiness("clinical_form_mismatch"), set())


def test_a_brand_printed_as_an_alternate_name_reaches_its_record(pipeline):
    """231852 prints Ubiquinol (Kaneka Ubiquinol). The record is read, and the signed
    scope still decides: the label's only claim is unrelated, so it earns nothing."""
    enriched = _enrich(pipeline, "evidence_truth_231852_raw.json")
    rejected = {m["id"]: m["reason_code"] for m in enriched["evidence_data"]["rejected_clinical_matches"]}
    assert rejected["BRAND_KANEKA_UBIQUINOL"] == "label_purpose_evidence_mismatch"
    assert "BRAND_KANEKA_UBIQUINOL" not in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]


def test_an_alternate_name_only_reaches_a_brand_record(pipeline):
    """"DGL" beside D-Glucuronolactone is a different substance from licorice DGL."""
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / "evidence_truth_231852_raw.json").read_text())
    raw["ingredientRows"][0].update(name="D-Glucuronolactone", alternateNames=["DGL"])
    enriched = enricher.enrich_product(normalizer.normalize_product(raw))[0]
    evidence = enriched["evidence_data"]
    assert "PRECLIN_DGL" not in [m["id"] for m in evidence["clinical_matches"] + evidence["rejected_clinical_matches"]]


def test_a_brand_reached_by_its_alternate_name_still_meets_its_exclusions(pipeline):
    """17550 prints Kaneka QH and a "Promotes: Energy Production" bullet. Kaneka's signed
    scope excludes energy, so reaching the record doesn't earn its credit."""
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "evidence_truth_17550_raw.json")
    rejected = {m["id"]: m["reason_code"] for m in enriched["evidence_data"]["rejected_clinical_matches"]}
    assert rejected["BRAND_KANEKA_UBIQUINOL"] == "label_purpose_evidence_mismatch"
    scored = build_scored_artifact(enriched)
    assert scored["quality_pillars_v4"]["evidence"]["score"] == 0
    assert scored["quality_assessment_status"] == "partial"


MELATONIN = "INGR_MELATONIN"


def _melatonin_rejection(enriched):
    return {m["id"]: m["reason_code"] for m in enriched["evidence_data"]["rejected_clinical_matches"]}.get(MELATONIN)


def _with_claims(pipeline, label, *claims):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / label).read_text())
    raw["statements"] = [{"type": "Formulation re: Other", "notes": claim} for claim in claims]
    return enricher.enrich_product(normalizer.normalize_product(raw))[0]


def test_a_jet_lag_mention_beside_a_sleep_claim_keeps_the_sleep_evidence(pipeline):
    """Sean's decision, 2026-11-04. 17393 claims sleep and names people with jet lag."""
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "evidence_truth_17393_raw.json")
    assert MELATONIN in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]
    assert build_scored_artifact(enriched)["quality_pillars_v4"]["evidence"]["score"] > 0


def test_one_sentence_combining_sleep_and_jet_lag_keeps_the_sleep_evidence(pipeline):
    enriched = _with_claims(pipeline, "evidence_truth_17393_raw.json", "For sleep support and help with jet lag")
    assert MELATONIN in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]


@pytest.mark.parametrize("claim", ["Helps with jet lag", "Jet lag relief", "For travelers with jetlag"])
def test_a_jet_lag_claim_alone_earns_nothing_from_the_sleep_evidence(pipeline, claim):
    """The record has no reviewed jet-lag context, so this claim has no evidence to meet."""
    enriched = _with_claims(pipeline, "evidence_truth_17393_raw.json", claim)
    assert MELATONIN not in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]
    assert _melatonin_rejection(enriched) == "label_purpose_evidence_mismatch"


def test_the_decision_covers_jet_lag_and_no_other_signed_melatonin_term(pipeline):
    """178273 claims sleep and names jet lag or shift work; shift work still excludes."""
    enriched = _enrich(pipeline, "evidence_truth_178273_raw.json")
    assert MELATONIN not in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]
    assert _melatonin_rejection(enriched) == "label_purpose_evidence_mismatch"


def test_a_jet_lag_mention_does_not_lift_a_preparation_the_review_excludes(pipeline):
    """246281 claims both, in a gummy. The signed dosage forms still decide."""
    enriched = _enrich(pipeline, "evidence_truth_246281_raw.json")
    assert MELATONIN not in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]
    assert _melatonin_rejection(enriched) == "clinical_delivery_mismatch"


def test_only_melatonin_carries_the_decision():
    from clinical_applicability import reviewed_entries

    carrying = [key for key, record in reviewed_entries().items()
                if (record.get("applicability") or {}).get("excluded_claim_terms_when_alone")]
    assert carrying == [MELATONIN]
    assert reviewed_entries()[MELATONIN]["applicability"]["excluded_claim_terms_when_alone"] == ["jet lag", "jetlag"]


def _projection_case(*rows):
    return {"evidence": {"ingredient_assessments": [
        {"canonical_id": name.lower(), "name": name, "reason_code": reason} for name, reason in rows]}}


PROJECTION = "module_scoped_product_projection"


@pytest.mark.parametrize("rows, rejected, required, expected", [
    ([("Quercetin", PROJECTION)], ["Quercetin"], {"quercetin"}, True),  # 328840: the only row is the projection.
    ([("Nattokinase", "clinical_form_mismatch"), ("Nattokinase", PROJECTION)], ["Nattokinase"], {"nattokinase"}, True),  # 24619's shape.
    ([("Garlic", "clinical_form_mismatch"), ("Cayenne", PROJECTION)], ["Garlic"], {"garlic", "cayenne"}, False),  # 251530: Cayenne has no rejection.
    ([("Quercetin", PROJECTION)], [], {"quercetin"}, False),  # No rejection at all.
    ([("Nattokinase", "literature_reviewed_human_clinical_evidence"), ("Nattokinase", PROJECTION)], ["Nattokinase"], {"nattokinase"}, False),  # The other row is another cause.
])
def test_a_rejection_counts_whichever_row_holds_it(rows, rejected, required, expected):
    from assessment_readiness import evidence_studies_did_not_qualify
    product = {"evidence_data": {"rejected_clinical_matches": [
        {"id": "INGR_COQ10", "ingredient": name, "reason_code": "label_purpose_evidence_mismatch"} for name in rejected]}}
    assert evidence_studies_did_not_qualify(product, _projection_case(*rows), required) is expected


def test_a_label_whose_only_row_is_the_projection_reads_the_rejection(pipeline):
    """328840: its one required row is the projection, and INGR_QUERCETIN was rejected for its purpose."""
    from scoring_v4.scored_artifact import build_scored_artifact

    evidence = build_scored_artifact(_enrich(pipeline, "evidence_truth_328840_raw.json"))["quality_pillars_v4"]["evidence"]
    assert evidence["reason"].startswith(DID_NOT_QUALIFY)
