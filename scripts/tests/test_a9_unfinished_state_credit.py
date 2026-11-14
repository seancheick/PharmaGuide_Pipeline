"""A9: unfinished data never reads as a finished assessment.

Numbers stay where they are. These tests pin that the fields claiming a finished
review say otherwise when the release assessment is open or the safety screen
never read a captured panel. Written against main first, where each one fails.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

from build_final_db import build_decision_highlights, generate_share_metadata

FIXTURES = Path(__file__).parent / "fixtures"
# 1055 now has a finished soy review. The pending-review fixture explicitly
# reopens its source decision in memory; the raw label and retained credit stay real.
PARTIAL_LABEL = "a9_completion_1055_raw.json"
COMPLETE_LABEL = "form_association_12012_raw.json"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _raw(label):
    return json.loads((FIXTURES / label).read_text())


def _enrich(pipeline, label):
    normalizer, enricher = pipeline
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(_raw(label)))
    return enriched


def _score(pipeline, raw):
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = pipeline
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return build_scored_artifact(enriched)


@pytest.fixture
def partial_full_evidence(pipeline, monkeypatch):
    import clinical_applicability as ca
    from scoring_v4.scored_artifact import build_scored_artifact

    records = copy.deepcopy(ca.reviewed_entries())
    soy = records["INGR_SOY_ISOFLAVONES"]
    soy["scoring_eligible"] = False
    for context in soy["study_contexts"]:
        if context.get("scoring_eligible"):
            context["scoring_eligible"] = False
            context["review_status"] = "source_verified_pending_clinical_review"
    monkeypatch.setattr(ca, "reviewed_entries", lambda: records)
    enriched = _enrich(pipeline, PARTIAL_LABEL)
    return enriched, build_scored_artifact(enriched)


# --- Evidence: an open review cannot present itself as a finished one -------

def test_open_evidence_review_does_not_present_as_assessed(partial_full_evidence):
    _, scored = partial_full_evidence
    release = scored["assessment_readiness"]["release_assessment"]
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["quality_assessment_status"] == "partial"
    assert "evidence_assessment_incomplete" in release["blockers"]
    # The retained credit is left alone; only the claim that review ended moves.
    assert evidence["score"] == 15.0
    assert evidence["display_state"] == "not_yet_reviewed"
    assert "still open" in evidence["reason"]
    assert "Established nutritional authority" not in evidence["reason"]


def test_finished_evidence_review_stays_assessed(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    scored = build_scored_artifact(_enrich(pipeline, COMPLETE_LABEL))
    assert scored["quality_assessment_status"] == "complete"
    assert scored["quality_pillars_v4"]["evidence"]["display_state"] == "assessed"


def test_marking_evidence_open_leaves_the_retained_credit_receipt(partial_full_evidence):
    _, scored = partial_full_evidence
    evidence = scored["quality_pillars_v4"]["evidence"]
    entries = evidence["receipt"]["entries"]
    assert abs(sum(entry["points"] for entry in entries) - evidence["score"]) < 0.001
    assert evidence["evidence_result_state"] == "clinical_review_not_covered"


# --- Safety screen: an unread panel is not "no known concern" ---------------

@pytest.mark.parametrize("label, gap", [
    (COMPLETE_LABEL, "inactiveIngredients"),
])
def test_uncaptured_panel_is_not_a_clean_screen(pipeline, label, gap):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, label)
    enriched.pop(gap)
    scored = build_scored_artifact(enriched)
    assert f"capture_unavailable:{gap}" in scored["_v4_safety_gate"]["ingredient_assessment_errors"]
    assert scored["product_safety_status"] == "not_assessed"
    # A capture gap stays a fact, not a withheld score, and never reads finished.
    assert scored["quality_score_status"] == "scored"
    assert scored["quality_assessment_status"] == "partial"


def test_no_active_panel_is_not_a_clean_screen(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, COMPLETE_LABEL)
    enriched["activeIngredients"] = []
    scored = build_scored_artifact(enriched)
    assert "capture_unavailable:activeIngredients" in scored["_v4_safety_gate"]["ingredient_assessment_errors"]
    assert scored["product_safety_status"] == "not_assessed"
    assert scored["quality_assessment_status"] == "partial"


@pytest.mark.parametrize("verdict, expected", [
    ("BLOCKED", "blocked"), ("UNSAFE", "unsafe"), ("CAUTION", "caution"),
])
def test_a_capture_gap_never_softens_a_safety_finding(verdict, expected):
    from scoring_v4.scored_artifact import _product_safety_status

    gate = {"verdict": verdict, "ingredient_assessment_errors": ["capture_unavailable:inactiveIngredients"]}
    assert _product_safety_status(gate, was_assessed=True) == expected


# --- Quality never reads as safety ------------------------------------------

@pytest.mark.parametrize("score", [None, 0, 54.0, 97.0])
def test_safety_status_ignores_the_quality_number(score):
    from scoring_v4.scored_artifact import _product_safety_status

    gate = {"verdict": "CAUTION", "quality_score_v4_100": score, "ingredient_assessment_errors": []}
    assert _product_safety_status(gate, was_assessed=True) == "caution"


def test_finished_share_copy_does_not_claim_a_safety_analysis():
    meta = generate_share_metadata(
        {"product_name": "Test Multi", "brand_name": "Brand"},
        {"quality_score_status": "scored", "quality_assessment_status": "complete",
         "quality_score_v4_100": 96.0, "score_100_equivalent": 96.0, "grade": "Exceptional", "verdict": "SAFE"},
    )
    assert "96/100" in meta["share_title"]
    assert "safety" not in meta["share_description"].lower().replace("not a safety rating", "")


# --- The export's own copy, for the same state ------------------------------

def _partial_scored(score=96.0, evidence=20.0):
    return {
        "quality_score_status": "scored", "quality_assessment_status": "partial",
        "product_safety_status": "no_known_catalog_concern",
        "score_100_equivalent": score, "grade": "Exceptional", "quality_tier": "Exceptional",
        "quality_pillars_v4": {"evidence": {"score": evidence, "max": 20}},
    }


def test_partial_share_copy_publishes_no_number_tier_or_finished_claim():
    enriched = {"product_name": "Basic Prenatal", "brand_name": "Thorne",
                "compliance_data": {"vegan": True, "gluten_free": True},
                "formulation_detail": {"delivery_tier": "premium"}}
    share = generate_share_metadata(enriched, _partial_scored())
    assert "/100" not in share["share_title"]
    assert "⭐" not in share["share_title"]
    assert "exceptional" not in share["share_description"].lower()
    assert "Quality assessment is incomplete" in share["share_description"]
    assert "Clinically-backed ingredients" not in share["share_highlights"]
    assert "No harmful additives" not in share["share_highlights"]
    assert not any("Premium" in item for item in share["share_highlights"])
    # Facts about the label stay.
    assert "Vegan • Gluten-Free" in share["share_highlights"]


@pytest.mark.parametrize("score, evidence, banned", [
    (96.0, 20.0, "clinical evidence"),
    (80.0, 5.0, "Strong overall quality"),
])
def test_partial_decision_highlights_do_not_praise_a_finished_result(score, evidence, banned):
    highlights = build_decision_highlights({"product_name": "X"}, _partial_scored(score, evidence))
    assert banned not in highlights["positive"]
    assert "finished" in highlights["positive"]
    assert highlights["caution"] == "Quality assessment is incomplete."


def test_complete_decision_highlights_keep_their_praise():
    scored = {**_partial_scored(), "quality_assessment_status": "complete"}
    highlights = build_decision_highlights({"product_name": "X"}, scored)
    assert highlights["positive"] == "Backed by meaningful clinical evidence."


@pytest.mark.parametrize("banned", ["DMAA", "1,3-Dimethylamylamine", "Ephedra", "Sibutramine"])
def test_a_banned_name_blocks_a_label_nothing_else_on_it_could_map(pipeline, banned):
    # The screen reads names, so a label below the coverage floor is still screened.
    raw = _raw("form_association_12012_raw.json")
    template = raw["ingredientRows"][0]

    def row(name):
        clean = {key: value for key, value in template.items() if key != "forms"}
        return {**clean, "name": name, "ingredientGroup": name,
                "quantity": [{"quantity": 0, "unit": "NP", "operator": "=",
                              "servingSizeQuantity": 1, "servingSizeUnit": ""}]}

    raw["ingredientRows"] = [row("Zzyzx Proprietary Thing")]
    unmapped = _score(pipeline, raw)
    assert unmapped["score_unavailable_reason"] == "blocked_by_completeness_gate"

    raw["ingredientRows"] = [row("Zzyzx Proprietary Thing"), row(banned)]
    scored = _score(pipeline, raw)
    assert scored["product_safety_status"] == "blocked"
    assert scored["score_unavailable_reason"] == "blocked_by_safety_gate"
    assert scored["quality_score_v4_100"] is None


def test_an_open_review_drops_the_finished_review_record_count(pipeline):
    # pillar_explanations: only a finished review may report "0 records".
    evidence = _score(pipeline, _raw("a9_completion_322514_raw.json"))["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] == "not_yet_reviewed"
    assert evidence["score"] == 0
    facts = (evidence.get("explanation") or {}).get("facts") or []
    assert "matched_evidence_records" not in [fact["id"] for fact in facts]


def test_a_finished_review_that_earned_nothing_keeps_its_record_count(pipeline):
    evidence = _score(pipeline, _raw("a9_finished_authority_no_credit_216405_raw.json"))["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] == "assessed"
    assert evidence["score"] == 0
    assert "no Evidence points" in evidence["reason"]
    facts = (evidence.get("explanation") or {}).get("facts") or []
    assert "matched_evidence_records" in [fact["id"] for fact in facts]


def test_an_open_review_keeps_its_recorded_state_and_reads_pending(pipeline):
    scored = _score(pipeline, _raw("a9_open_review_applicability_182957_raw.json"))
    evidence = scored["quality_pillars_v4"]["evidence"]
    assert scored["assessment_readiness"]["release_assessment"]["blockers"] == [
        "evidence_assessment_incomplete"]
    assert scored["quality_assessment_status"] == "partial"
    assert evidence["evidence_result_state"] == "clinical_review_not_covered"
    assert evidence["display_state"] == "not_yet_reviewed"
    assert evidence["score"] == 0


# --- Transparency: a printed count per strain is not a hidden amount --------

def test_a_probiotic_printing_every_strains_count_is_not_called_hidden(pipeline):
    # 217182 prints 420, 420 and 160 million viable microorganisms per strain.
    transparency = _score(pipeline, _raw("a9_probiotic_every_strain_count_217182_raw.json"))[
        "quality_pillars_v4"]["transparency"]
    assert transparency["score"] == 15.0
    assert transparency["reason"] == (
        "The label prints a live-culture count for every strain; "
        "their individual weights in the blend are not listed.")
    facts = {fact["id"]: fact for fact in transparency["explanation"]["facts"]}
    assert facts["undisclosed_ingredient_amount_count"]["audience"] == "audit"


@pytest.mark.parametrize("disclosed", [0, 2])
def test_a_probiotic_missing_a_strain_count_keeps_the_hidden_amount(disclosed):
    from scoring_v4.quality_score import _pillar_from_dim

    transparency = _pillar_from_dim("transparency", {
        "score": 15.0, "max": 15.0, "penalties": {},
        "metadata": {
            "total_strain_count": 3, "per_strain_cfu_disclosed_count": disclosed,
            "flags": ["PROPRIETARY_BLEND_PRESENT"],
            "B5_blend_evidence": [{"children_without_amount_count": 3}],
        },
    }, 15.0, "module")
    assert transparency["reason"].startswith("Most amounts are disclosed")


@pytest.mark.parametrize("assessment", ["missing", None, "", "partial", "failed", "future"])
def test_share_metadata_requires_explicit_completed_assessment(assessment):
    scored = {"quality_score_v4_100": 80, "score_100_equivalent": 80,
              "quality_score_status": "scored", "quality_assessment_status": assessment,
              "grade": "Good", "quality_pillars_v4": {"evidence": {"score": 20}}}
    if assessment == "missing":
        scored.pop("quality_assessment_status")
    share = generate_share_metadata({"product_name": "Label", "brand_name": "Brand",
                                    "compliance_data": {"vegan": True}}, scored)
    assert "/100" not in share["share_title"]
    assert "good quality" not in share["share_description"].lower()
    assert "recorded safety warnings" in share["share_description"]
    assert "Vegan" in share["share_highlights"]
    assert "Clinically-backed ingredients" not in share["share_highlights"]
    assert "No harmful additives" not in share["share_highlights"]


@pytest.mark.parametrize("score_status", ["missing", None, "", "unknown", "not_scored", "suppressed_safety"])
def test_share_metadata_requires_scored_status(score_status):
    scored = {"quality_score_v4_100": 80, "score_100_equivalent": 80,
              "quality_score_status": score_status, "quality_assessment_status": "complete", "grade": "Good"}
    if score_status == "missing":
        scored.pop("quality_score_status")
    share = generate_share_metadata({"product_name": "Label"}, scored)
    assert "/100" not in share["share_title"]
    assert "good quality" not in share["share_description"].lower()
    assert "recorded safety warnings" in share["share_description"]


@pytest.mark.parametrize("score", [None, float("nan"), float("inf"), -float("inf"), -1, 101])
def test_share_metadata_rejects_invalid_canonical_numbers_even_with_valid_mirror(score):
    scored = {"quality_score_v4_100": score, "score_100_equivalent": 80,
              "quality_score_status": "scored", "quality_assessment_status": "complete", "grade": "Good"}
    share = generate_share_metadata({"product_name": "Label"}, scored)
    assert "/100" not in share["share_title"]
    assert "good quality" not in share["share_description"].lower()
    assert "recorded safety warnings" in share["share_description"]


@pytest.mark.parametrize("score, mirror", [(0, 99), (100, 1), (74.6, 99)])
def test_share_metadata_uses_canonical_score_including_valid_zero(score, mirror):
    scored = {"quality_score_v4_100": score, "score_100_equivalent": mirror,
              "quality_score_status": "scored", "quality_assessment_status": "complete", "grade": "Good"}
    share = generate_share_metadata({"product_name": "Label"}, scored)
    expected = 75 if score == 74.6 else score
    assert f" - {expected}/100" in share["share_title"]
    assert "good quality" in share["share_description"].lower()


@pytest.mark.parametrize("safety", ["blocked", "unsafe"])
def test_share_metadata_preserves_independent_block_with_stale_scored_number(safety):
    scored = {"quality_score_v4_100": 80, "score_100_equivalent": 80,
              "quality_score_status": "scored", "quality_assessment_status": "complete",
              "product_safety_status": safety, "grade": "Good"}
    share = generate_share_metadata({"product_name": "Label"}, scored)
    assert "/100" not in share["share_title"]
    assert "good quality" not in share["share_description"].lower()
    assert "Quality score withheld" in share["share_description"]
    assert "recorded safety warnings" in share["share_description"]


def test_share_metadata_never_repairs_missing_canonical_score_from_mirror():
    scored = {"score_100_equivalent": 80, "quality_score_status": "scored",
              "quality_assessment_status": "complete", "grade": "Good"}
    share = generate_share_metadata({"product_name": "Label"}, scored)
    assert "/100" not in share["share_title"]
    assert "good quality" not in share["share_description"].lower()
    assert "Quality score unavailable" in share["share_description"]


@pytest.mark.parametrize("score", [True, False])
def test_share_metadata_rejects_boolean_canonical_numbers(score):
    scored = {"quality_score_v4_100": score, "score_100_equivalent": 80,
              "quality_score_status": "scored", "quality_assessment_status": "complete", "grade": "Good"}
    share = generate_share_metadata({"product_name": "Label"}, scored)
    assert "/100" not in share["share_title"]
    assert "good quality" not in share["share_description"].lower()
    assert "Quality score unavailable" in share["share_description"]


@pytest.mark.parametrize("score", ["0", "100"])
def test_share_metadata_preserves_existing_numeric_string_contract(score):
    scored = {"quality_score_v4_100": score, "quality_score_status": "scored",
              "quality_assessment_status": "complete", "grade": "Good"}
    share = generate_share_metadata({"product_name": "Label"}, scored)
    assert f" - {score}/100" in share["share_title"]
