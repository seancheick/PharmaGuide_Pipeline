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
    pytest.param("evidence_truth_252423_raw.json", "generic", id="generic"),
    pytest.param("evidence_truth_253729_raw.json", "fiber_digestive", id="fiber"),
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


def test_coq10_credit_is_independent_of_the_advertised_purpose(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    label = "evidence_truth_60601_raw.json"
    scores = [build_scored_artifact(product)["quality_pillars_v4"]["evidence"]["score"]
              for product in (_enrich(pipeline, label), _with_claims(pipeline, label))]
    assert scores[0] == scores[1] > 0


def _closed_record(monkeypatch, canonical, decision):
    """The review closes goldenseal on #366; this tree's data doesn't hold that record yet."""
    import evidence_resolver

    records = dict(evidence_resolver._load_literature_evidence())
    records[canonical] = {**records[canonical], "applicability_status": "no_qualifying_human_evidence",
                          "effect_direction": None, "qualifying_human_studies": [],
                          "applicability_decision": decision,
                          "verification_provenance": {**records[canonical]["verification_provenance"],
                                                      "verified_by": "Agent review of PubMed abstracts"}}
    monkeypatch.setattr(evidence_resolver, "_load_literature_evidence", lambda: records)


@pytest.mark.parametrize("decision, expected", [
    # Sean's ruling names this state: the decision names the human studies it read.
    ("Finished review with no qualifying study for these labels. PMID 17495878 is a drug interaction study.", True),
    # An older record: related research, often a mixture or another route.
    ("Bounded PubMed source-content review: related research inspected (PMID 15798997). A four-herb mixture.", False),
    ("Reproducible literature search identified zero qualifying trials for standalone goldenseal.", False),
])
def test_a_no_qualifying_closure_says_so_when_it_names_human_studies(pipeline, monkeypatch, decision, expected):
    """252471 Goldenseal, whose only required row closes through its literature record."""
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "evidence_truth_252471_raw.json")
    _closed_record(monkeypatch, "goldenseal", decision)
    scored = build_scored_artifact(enriched)
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["quality_assessment_status"] == "complete"
    assert evidence["score"] == 0
    assert evidence["reason"].startswith(DID_NOT_QUALIFY) is expected
    assert evidence["reason"].startswith("We reviewed the research but found no qualifying") is not expected


def test_a_closure_answers_for_a_label_whose_only_row_is_the_projection(pipeline, monkeypatch):
    """251619 Kudzu Root: its one required row is the projection, and that record closed."""
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "evidence_truth_251619_raw.json")
    _closed_record(monkeypatch, "puerarin", "Finished review with no qualifying study for these labels. PMID 22578529.")
    evidence = build_scored_artifact(enriched)["quality_pillars_v4"]["evidence"]
    assert evidence["score"] == 0
    assert evidence["reason"].startswith(DID_NOT_QUALIFY)


@pytest.mark.parametrize("rows, required, expected", [
    # 183349: coconut water is another required row, and no study answers for it.
    ([("l_glutamine", "reproducible_search_found_no_qualifying_human_studies"),
      ("coconut_water", "whole_food_matrix_not_efficacy_relevant")], {"l_glutamine", "coconut_water"}, False),
    # 259595: the closed row isn't what the probiotic label's Evidence reads.
    ([("bacillus_subtilis", "no_reviewed_evidence_assessment"),
      ("l_glutamine", "reproducible_search_found_no_qualifying_human_studies")], {"bacillus_subtilis"}, False),
])
def test_a_closure_answers_only_for_its_own_required_row(monkeypatch, rows, required, expected):
    from assessment_readiness import evidence_studies_did_not_qualify

    _closed_record(monkeypatch, "l_glutamine", "Finished review with no qualifying study for these labels. PMID 30108163.")
    readiness = {"evidence": {"ingredient_assessments": [
        {"canonical_id": canonical, "name": canonical, "reason_code": reason} for canonical, reason in rows]}}
    assert evidence_studies_did_not_qualify({}, readiness, required) is expected


def test_every_listed_no_qualifying_closure_reads_seans_sentence():
    """The rule matches the decision's opening words, so the review's whole list is pinned to it.

    The list arrives with #366, which lands after this; until then there is nothing to read.
    """
    from assessment_readiness import evidence_studies_did_not_qualify
    from evidence_resolver import resolve_evidence_for_row
    from scoring_v4.quality_score import _EVIDENCE_ZERO_REASON, mark_evidence_studies_did_not_qualify

    corrections = FIXTURES.parent.parent / "audits" / "evidence_backed_970_20261104" / "literature_corrections.json"
    listed = json.loads(corrections.read_text()) if corrections.exists() else {}
    no_qualifying = sorted(c for c, fix in listed.items() if fix.get("result") == "no_qualifying_human_evidence")
    for canonical in no_qualifying:
        row = {"canonical_id": canonical, "name": canonical, "raw_source_text": canonical,
               "source_label_name": canonical, "raw_source_path": "activeIngredients[0]",
               "source_section": "activeIngredients"}
        reason = resolve_evidence_for_row(row, {"activeIngredients": [row], "ingredients_scorable": [row]}).reason_code
        readiness = {"evidence": {"ingredient_assessments": [{**row, "reason_code": reason}]}}
        assert evidence_studies_did_not_qualify({}, readiness, {canonical}), canonical
    pillar = {"score": 0, "reason": _EVIDENCE_ZERO_REASON["no_qualifying_human_evidence"]}
    assert mark_evidence_studies_did_not_qualify(pillar)["reason"] == DID_NOT_QUALIFY


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


def test_a_finished_review_with_no_stated_direction_stays_complete(pipeline):
    """239062: ginkgo's record states no direction and says a declared extract finishes at no credit."""
    from assessment_readiness import evidence_review_open
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, "evidence_truth_239062_raw.json"))
    assert scored["quality_assessment_status"] == "complete"
    assert not evidence_review_open(scored["assessment_readiness"]["release_assessment"])
    assert scored["quality_pillars_v4"]["evidence"]["score"] == 0


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
    from scoring_v4.scored_artifact import build_scored_artifact

    label = "evidence_truth_231852_raw.json"
    enriched = _enrich(pipeline, label)
    assert "BRAND_KANEKA_UBIQUINOL" in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]
    score = build_scored_artifact(enriched)["quality_pillars_v4"]["evidence"]["score"]
    plain = build_scored_artifact(_with_claims(pipeline, label))["quality_pillars_v4"]["evidence"]["score"]
    assert score == plain > 0


def test_an_alternate_name_only_reaches_a_brand_record(pipeline):
    """"DGL" beside D-Glucuronolactone is a different substance from licorice DGL."""
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / "evidence_truth_231852_raw.json").read_text())
    raw["ingredientRows"][0].update(name="D-Glucuronolactone", alternateNames=["DGL"])
    enriched = enricher.enrich_product(normalizer.normalize_product(raw))[0]
    evidence = enriched["evidence_data"]
    assert "PRECLIN_DGL" not in [m["id"] for m in evidence["clinical_matches"] + evidence["rejected_clinical_matches"]]


def test_a_brand_claim_exclusion_is_separate_from_ingredient_credit(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "evidence_truth_17550_raw.json")
    match = next(m for m in enriched["evidence_data"]["clinical_matches"] if m["id"] == "BRAND_KANEKA_UBIQUINOL")
    assert match["applicability_assessment"]["claim_alignment"]["state"] == "unrelated"
    assert build_scored_artifact(enriched)["quality_pillars_v4"]["evidence"]["score"] > 0


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


@pytest.mark.parametrize("claim", [
    "For sleep support and help with jet lag",
    "Helps with jet lag without caffeine, and promotes sleep",
])
def test_one_sentence_combining_sleep_and_jet_lag_keeps_the_sleep_evidence(pipeline, claim):
    enriched = _with_claims(pipeline, "evidence_truth_17393_raw.json", claim)
    assert MELATONIN in [m["id"] for m in enriched["evidence_data"]["clinical_matches"]]


@pytest.mark.parametrize("claim", ["Helps with jet lag", "Jet lag relief", "For travelers with jetlag", "Helps with jet lag without promoting sleep"])
def test_jet_lag_claim_does_not_change_sleep_evidence(pipeline, claim):
    from scoring_v4.scored_artifact import build_scored_artifact

    label = "evidence_truth_17393_raw.json"
    enriched = _with_claims(pipeline, label, claim)
    match = next(m for m in enriched["evidence_data"]["clinical_matches"] if m["id"] == MELATONIN)
    assert match["applicability_assessment"]["claim_alignment"]["state"] == "unrelated"
    score = build_scored_artifact(enriched)["quality_pillars_v4"]["evidence"]["score"]
    plain = build_scored_artifact(_with_claims(pipeline, label))["quality_pillars_v4"]["evidence"]["score"]
    assert score == plain > 0


def test_shift_work_copy_cannot_lift_melatonin_delivery_exclusion(pipeline):
    enriched = _enrich(pipeline, "evidence_truth_178273_raw.json")
    assert _melatonin_rejection(enriched) == "clinical_delivery_mismatch"


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


def test_product_level_quercetin_credit_is_independent_of_claims(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    label = "evidence_truth_328840_raw.json"
    scores = [build_scored_artifact(product)["quality_pillars_v4"]["evidence"]["score"]
              for product in (_enrich(pipeline, label), _with_claims(pipeline, label))]
    assert scores[0] == scores[1] > 0
