"""Dose V4.1 §2.3: a genuinely hidden amount and a completed no-reference
conclusion take the shared 11.4/20 neutral; Transparency keeps the
missing-disclosure consequence. A pipeline-lost amount keeps its strict hold."""
import json
import logging
from pathlib import Path

from test_v4_generic_dose_p132a import _ingredient, _product
from scoring_v4.scored_artifact import build_scored_artifact

FIXTURES = Path(__file__).parent / "fixtures"


def _ravage():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / "blend_2219_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


def test_named_sports_actives_with_hidden_amounts_take_the_neutral():
    artifact = build_scored_artifact(_ravage())
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 11.4
    assert "hidden" in dose["reason"] and "neutral" in dose["reason"]
    # Transparency still carries the blend-opacity consequence.
    transparency = artifact["_v4_module_breakdown"]["dimensions"]["transparency"]
    assert transparency["penalties"].get("B5_proprietary_blend_opacity", 0) < 0


def _two_purposes(hidden_quantity=None):
    magnesium = _ingredient(quantity=84)
    ashwagandha = _ingredient(name="Ashwagandha", canonical_id="ashwagandha", quantity=hidden_quantity,
                              unit="mg" if hidden_quantity else "")
    p = _product(ingredients=[magnesium, ashwagandha], adequacy_results=[{
        "nutrient": "Magnesium", "canonical_id": "magnesium", "unit": "mg", "rda_ai": 400, "ul": 350,
        "ul_status": "established", "pct_rda": 21.0, "pct_ul": 24.0, "scoring_eligible": True,
        "ul_gate_eligible": True}], safety_flags=[])
    p["product_name"] = "Magnesium + Ashwagandha"
    p["serving_basis"] = {"min_servings_per_day": 1, "max_servings_per_day": 1, "servings_per_day_source": "directions"}
    return p


def test_a_declared_purpose_with_a_hidden_amount_is_a_neutral_vote_not_skipped():
    artifact = build_scored_artifact(_two_purposes())
    dim = artifact["_v4_module_breakdown"]["dimensions"]["dose"]
    assert "ashwagandha" in dim["metadata"]["hidden_amount_purpose_ingredients"]
    # (magnesium 20 + hidden neutral 11.4) / 2 on the public scale.
    assert artifact["quality_pillars_v4"]["dose"]["score"] == 15.7


def test_a_pipeline_lost_amount_keeps_its_strict_hold():
    product = _two_purposes(hidden_quantity=300)
    product["ingredient_quality_data"]["ingredients_scorable"][1]["quantity_operator"] = "ambiguous"
    artifact = build_scored_artifact(product)
    # No neutral fallback: the unreadable amount keeps the product out of scoring.
    assert artifact["quality_score_status"] == "not_scored"
    assert artifact["score_unavailable_reason"] == "blocked_by_completeness_gate"
    assert artifact["quality_pillars_v4"] is None
