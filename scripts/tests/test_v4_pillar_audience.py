"""Pillar dropdowns show one sentence of reason and at most one key fact.

Sean, 2026-10-20: users see the one-sentence reason and one key fact (amount
vs reference, the upper-limit result, or the honest disclosure gap). Every
other fact stays in the data as ``audience: "audit"`` for the dashboard and
audits. Consumer text names ingredients by display name and carries no point
numbers, policy paragraphs or arithmetic.
"""

from __future__ import annotations

import re
import pytest

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4 import quality_score as qs  # noqa: E402
from scoring_v4.pillar_explanations import (  # noqa: E402
    PILLAR_EXPLANATION_SCHEMA_VERSION,
    attach_pillar_explanations,
)

_SENTENCE_BREAK = re.compile(r"[.!?]\s+[A-Z]")
_CANONICAL_ID = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")
_POINTS = re.compile(r"\(\s*[\d.]+\s*points?\s*\)|\d+(\.\d+)?/\d+|\bpoints?\b")


def _one_sentence(text: str) -> bool:
    return bool(text) and not _SENTENCE_BREAK.search(text.strip())


def _consumer(pillar):
    return [f for f in (pillar.get("explanation") or {}).get("facts") or [] if f.get("audience") == "consumer"]


def _assert_consumer_contract(pillar):
    facts = (pillar.get("explanation") or {}).get("facts") or []
    assert all(f.get("audience") in {"consumer", "audit"} for f in facts), facts
    consumer = _consumer(pillar)
    assert len(consumer) <= 1, consumer
    for fact in consumer:
        text = f"{fact['label']} {fact['value_display']}"
        assert not _CANONICAL_ID.search(text), text
        assert not _POINTS.search(text), text
        assert "policy" not in text.lower(), text


def _dose_cfg():
    return {"pillars": {"dose": {"weight": 20, "assembler": "dose"}}}


def _ul_capped_vitamin_c():
    row = {"nutrient": "Vitamin C", "canonical_id": "vitamin_c", "unit": "mg", "rda_ai": 90, "ul": 2000,
           "pct_rda": 1111.1, "pct_ul": 150.0, "per_day_min": 1000.0, "per_day_max": 3000.0}
    metadata = {
        "method": "source_qualified_contribution_and_completed_neutral",
        "assessment_basis": "directed_daily_use",
        "daily_use": {"minimum_servings": 1.0, "maximum_servings": 3.0, "defaulted": False},
        "dose_participation_basis": "declared_purpose_equal_weight",
        "reference_assessments": [row],
        "dose_contributions": [{"ingredient": "vitamin_c", "assessment": "dri_reference", "credit_raw": 22.0,
                                "amount_at_minimum": 1000.0, "amount_at_maximum": 3000.0, "amount_unit": "mg",
                                "amount_per_serving": 1000.0, "reference_value": 90.0, "pct_of_reference": 1111.1}],
        "B7_safety_evaluation": {"dose_ceiling": {
            "kind": "established_upper_limit", "nutrient": "Vitamin C", "ul": 2000.0, "ul_unit": "mg",
            "ul_population": "general adult", "pct_ul": 150.0, "pct_ul_at_minimum": 50.0,
            "minimum_exceeds": False, "cap_public": 0.0, "partial_ceiling_public": 10.0, "zero_at_pct": 150.0}},
    }
    dim = {"score": 22.0, "metadata": metadata}
    return dim, {"dimensions": {"dose": dim}}


def _assembled_dose(dim, module_bd, module="generic"):
    pillar = qs._pillar_dose(dim, 20, "generic_single_molecule", qs._config())
    pillars = attach_pillar_explanations({"dose": pillar}, module_bd, _dose_cfg(), module)
    return pillars["dose"]


def test_ul_cap_reason_is_one_sentence_and_policy_moves_to_audit():
    dim, module_bd = _ul_capped_vitamin_c()
    pillar = _assembled_dose(dim, module_bd)
    assert pillar["score"] == 0.0
    assert pillar["reason"] == ("The higher directed daily amounts of Vitamin C exceed its established upper "
                                "limit, so Dose credit is withheld.")
    assert _one_sentence(pillar["reason"])
    facts = {f["id"]: f for f in pillar["explanation"]["facts"]}
    assert "not a medical toxicity grade" in facts["dose_safety_ceiling"]["value_display"]
    assert facts["dose_safety_ceiling"]["audience"] == "audit"
    assert pillar["explanation"]["schema_version"] == PILLAR_EXPLANATION_SCHEMA_VERSION == 2


def test_ul_cap_consumer_fact_is_the_upper_limit_result():
    dim, module_bd = _ul_capped_vitamin_c()
    pillar = _assembled_dose(dim, module_bd)
    _assert_consumer_contract(pillar)
    assert _consumer(pillar) == [{
        "id": "dose_upper_limit_result", "label": "Upper limit", "audience": "consumer",
        "value_display": "1,000 mg per serving; directions: 1–3 servings a day. Up to 3,000 mg a day: 150% of the 2,000 mg Vitamin C upper limit (general adult)"}]


def test_audit_contributions_use_display_name_not_canonical_id():
    dim, module_bd = _ul_capped_vitamin_c()
    facts = {f["id"]: f for f in _assembled_dose(dim, module_bd)["explanation"]["facts"]}
    text = facts["dose_contributions"]["value_display"]
    assert text.startswith("Vitamin C: RDA/AI 90 mg"), text
    assert "vitamin_c" not in text
    # The receipt keeps the identity key for parity and reconciliation.
    receipt = _assembled_dose(dim, module_bd)["explanation"]["dose_receipt"]
    assert receipt["contributions"][0]["ingredient"] == "vitamin_c"
    assert receipt["reconciles"] is True


def test_single_assessed_amount_is_shown_against_its_reference():
    dim, module_bd = _ul_capped_vitamin_c()
    dim["metadata"].pop("B7_safety_evaluation")
    dim["metadata"]["reference_assessments"][0]["per_day_max"] = 1000.0
    dim["metadata"]["daily_use"]["maximum_servings"] = 1.0
    dim["metadata"]["dose_contributions"][0]["amount_at_maximum"] = 1000.0
    pillar = _assembled_dose(dim, module_bd)
    _assert_consumer_contract(pillar)
    assert [f["value_display"] for f in _consumer(pillar)] == ["1,000 mg Vitamin C a day; RDA/AI 90 mg"]


def test_hidden_per_strain_amounts_are_the_honest_gap_and_guarantee_moves_to_audit():
    metadata = {
        "cfu_adequacy_basis": "aggregate_cfu_disclosed_only",
        "cfu_guarantee": {"type": "unknown"},
        "daily_use": {"minimum_servings": 1.0, "maximum_servings": 1.0, "defaulted": False},
        "cfu_adequacy_contributions": [
            {"strain": "Lacticaseibacillus rhamnosus GR-1", "state": "neutral_amount_not_disclosed",
             "points": 3.8, "cfu_per_day": None},
            {"strain": "Limosilactobacillus reuteri RC-14", "state": "neutral_amount_not_disclosed",
             "points": 3.8, "cfu_per_day": None},
        ],
    }
    dim = {"score": 11.4, "metadata": metadata}
    pillar = qs._pillar_dose(dim, 20, "probiotic", qs._config())
    assert _one_sentence(pillar["reason"]), pillar["reason"]
    assert "guaranteed through expiration" not in pillar["reason"]
    pillars = attach_pillar_explanations({"dose": pillar}, {"dimensions": {"dose": dim}}, _dose_cfg(), "probiotic")
    _assert_consumer_contract(pillars["dose"])
    facts = {f["id"]: f for f in pillars["dose"]["explanation"]["facts"]}
    assert facts["cfu_guarantee"] == {
        "id": "cfu_guarantee", "label": "Potency guarantee", "audience": "audit",
        "value_display": "Whether the count is guaranteed through expiration is not stated."}
    assert [f["value_display"] for f in _consumer(pillars["dose"])] == ["Per-strain amounts are not listed"]


def test_every_fact_is_audit_unless_chosen():
    pillars = {"evidence": {"score": 0.0, "max": 20, "reason": "r.", "display_state": "assessed"},
               "transparency": {"score": 12.0, "max": 15, "reason": "r."}}
    module_bd = {"dimensions": {"evidence": {"metadata": {"matched_entries": 0}},
                                "transparency": {"metadata": {"B5_blend_evidence": [
                                    {"children_without_amount_count": 0}]}}}}
    cfg = {"pillars": {"evidence": {"assembler": "evidence"}, "transparency": {"source_dim": "transparency"}}}
    out = attach_pillar_explanations(pillars, module_bd, cfg, "generic")
    assert [f["id"] for f in _consumer(out["evidence"])] == ["matched_evidence_records"]
    # Zero hidden amounts is no disclosure gap, so nothing is shown.
    assert _consumer(out["transparency"]) == []
    assert {f["audience"] for f in out["transparency"]["explanation"]["facts"]} == {"audit"}


def test_reattaching_does_not_repeat_facts():
    dim, module_bd = _ul_capped_vitamin_c()
    pillar = _assembled_dose(dim, module_bd)
    count = len(pillar["explanation"]["facts"])
    again = attach_pillar_explanations({"dose": pillar}, module_bd, _dose_cfg(), "generic")["dose"]
    assert len(again["explanation"]["facts"]) == count


def test_botanical_formulation_reason_is_one_sentence_with_same_credits():
    metadata = {"botanical_profile_applied": True, "botanical_formulation": {}}
    profile = qs._PROFILE_COPY["botanical_formulation"]
    (identity_key, _), credited, missing = profile
    detail = {identity_key: 1.0, credited[0][0]: 1.0}
    for key, _ in missing[:1]:
        detail[key] = 0.0
    metadata["botanical_formulation"] = detail
    reason = qs._profile_formulation_reason(metadata)
    assert _one_sentence(reason), reason
    assert reason.startswith("The recognized botanical identity receives neutral credit; credited: ")


def test_verification_fail_open_reason_has_no_point_numbers():
    reason = qs._pillar_verification({}, 15, qs._config())
    assert reason["reason"].startswith("Independent testing or certification: unconfirmed.")
    assert not _POINTS.search(reason["reason"]), reason["reason"]
    facts = {f["id"]: f for f in reason["explanation"]["facts"]}
    assert facts["verification_neutral_baseline"]["audience"] == "audit"
    assert "points need verified evidence" in facts["verification_neutral_baseline"]["value_display"]


def test_zero_evidence_copy_is_one_sentence():
    for text in qs._EVIDENCE_ZERO_REASON.values():
        assert _one_sentence(text), text


def _receipt_with(**changes):
    dim, module_bd = _ul_capped_vitamin_c()
    return _assembled_dose(dim, module_bd)["explanation"]["dose_receipt"] | changes


def test_policy_target_is_never_shown_as_a_consumer_reference():
    # 20% of the Daily Value is scoring policy, not an intake recommendation.
    from scoring_v4.pillar_explanations import _dose_consumer_fact
    receipt = _receipt_with(upper_reference=None, contributions=[{
        "ingredient": "magnesium", "assessment": "contribution_policy_target",
        "reference": "PharmaGuide contribution target (20% of the FDA Daily Value)",
        "reference_kind": "pharmaguide_policy", "amount_at_minimum": 120.0, "amount_at_maximum": 120.0,
        "amount_unit": "mg", "reference_value": 84.0}])
    assert _dose_consumer_fact(receipt) is None


def test_at_least_exposure_is_never_shown_as_up_to():
    from scoring_v4.pillar_explanations import _dose_consumer_fact
    receipt = _receipt_with(upper_reference={
        "kind": "caffeine_daily_total", "nutrient": "Caffeine", "amount_mg_day": 450.0,
        "exceeds_above_mg_day": 400.0, "quantity_operator": ">=", "cap_public": 0.0})
    assert _dose_consumer_fact(receipt)["value_display"] == (
        "At least 450 mg of caffeine a day; reference 400 mg a day for most adults")
    fixed = receipt | {"daily_use": {"minimum_servings": 2.0, "maximum_servings": 2.0, "defaulted": False},
                       "upper_reference": receipt["upper_reference"] | {"quantity_operator": "="}}
    assert _dose_consumer_fact(fixed)["value_display"].startswith("450 mg of caffeine a day")


def test_defaulted_frequency_is_named_on_the_amount_fact():
    from scoring_v4.pillar_explanations import _dose_consumer_fact
    receipt = _receipt_with(upper_reference=None,
                            daily_use={"minimum_servings": 1.0, "maximum_servings": 1.0, "defaulted": True},
                            contributions=[{"ingredient": "vitamin_c", "assessment": "dri_reference",
                                            "reference": "RDA/AI", "amount_at_minimum": 500.0,
                                            "amount_at_maximum": 500.0, "amount_unit": "mg",
                                            "reference_value": 90.0}])
    assert _dose_consumer_fact(receipt)["value_display"] == "500 mg Vitamin C at one serving a day; RDA/AI 90 mg"


def test_a_triggered_limit_never_reads_as_exactly_the_limit():
    from scoring_v4.pillar_explanations import _dose_consumer_fact
    receipt = _receipt_with()
    receipt["upper_reference"] = receipt["upper_reference"] | {"pct_ul": 100.49}
    assert "100.5% of the 2,000 mg Vitamin C upper limit" in _dose_consumer_fact(receipt)["value_display"]


def test_builder_fact_blocks_are_versioned_without_an_attach():
    # Suppressed-safety pillars are built but never attached.
    block = qs._pillar_verification({}, 15, qs._config())["explanation"]
    assert block["schema_version"] == PILLAR_EXPLANATION_SCHEMA_VERSION
    assert {f["audience"] for f in block["facts"]} == {"audit"}


def test_consumer_cap_reason_keeps_the_hazard_without_score_arithmetic():
    dim, _ = _ul_capped_vitamin_c()
    for cap in (0.0, 10.0):
        dim["metadata"]["B7_safety_evaluation"]["dose_ceiling"]["cap_public"] = cap
        reason = qs._over_limit_dose_reason(dim)
        assert "exceed" in reason
        assert "upper limit" in reason
        assert not re.search(r"\b(?:0|10|150)\b", reason), reason
        assert _one_sentence(reason)


def test_tiny_upper_limit_exceedance_is_still_visible():
    from scoring_v4.pillar_explanations import _dose_consumer_fact
    receipt = _receipt_with()
    receipt["upper_reference"] = receipt["upper_reference"] | {"pct_ul": 100.01}
    value = _dose_consumer_fact(receipt)["value_display"]
    assert "100.0%" not in value
    assert ">100%" in value


def test_upper_limit_rounding_boundaries_never_hide_exceedance():
    from scoring_v4.pillar_explanations import _percent
    for value in (100.00001, 100.01, 100.05, 100.049999, 100.49, 100.5):
        text = _percent(value)
        assert text == ">100" or float(text) > 100, (value, text)


@pytest.mark.parametrize("basis,scope", [("supplemental_only", "from supplements"),
                                         ("total_intake", "from all sources"),
                                         ("synthetic_only", "synthetic forms")])
def test_upper_limit_fact_explains_serving_range_and_reference_scope(basis, scope):
    dim, module_bd = _ul_capped_vitamin_c()
    dim["metadata"]["reference_assessments"][0]["reference"] = {"ul_basis": basis}
    text = _consumer(_assembled_dose(dim, module_bd))[0]["value_display"]
    assert "1,000 mg per serving" in text
    assert "1–3 servings a day" in text
    assert "3,000 mg" in text
    assert scope in text
    assert "capsule" not in text  # No unit-count inference from serving counts.
