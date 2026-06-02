"""V4 Phase 3 — role-aware completeness.

The soft-policy score caps (low-confidence omega breakdown; percent-DV-only
dose) must fire ONLY when the relevant ingredient is a cap-eligible role
(primary / claim_prominent). An adjunct ingredient's data gap must suppress its
credit (keep the soft_missing tag) but must NOT cap or CAUTION the product.

Spec: docs/superpowers/specs/2026-05-31-v4-role-aware-completeness-design.md

8-row treatment table coverage:
  Row 1 primary probiotic missing CFU -> cap/CAUTION  (locked in test_v4_completeness_gate.py)
  Row 2 adjunct probiotic missing CFU -> no cap        (here: soft policy never caps the tag)
  Row 3 primary omega missing EPA/DHA -> NOT_SCORED    (locked in test_v4_completeness_gate.py)
  Row 4 adjunct omega -> no product cap                (here: THE FIX)
  Row 5 primary sports missing dose -> cap/CAUTION      (locked in test_v4_completeness_gate.py)
  Row 6 adjunct sports missing dose -> no cap           (here: soft policy never caps the tag)
  Row 7 primary botanical missing dose -> CAUTION       (locked: botanical_anchor_only, until Phase 6)
  Row 8 adjunct botanical missing dose -> no cap        (anchor-only requires whole-product anchor)
"""
from __future__ import annotations

import pytest

from scoring_input_contract import classify_ingredient_roles  # noqa: E402
from scoring_v4.gate_completeness import (  # noqa: E402
    evaluate_completeness_gate,
    _soft_policy_from_scoring_evidence,
)


def _omega_aggregate_evidence(confidence: str = "low") -> dict:
    return {
        "evidence_type": "omega_epa_dha_aggregate",
        "dose_class": "therapeutic_mass",
        "dose_value": 100.0,
        "dose_unit": "mg",
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "source": "compatibility_derived",
        "evidence_origin": "compatibility_derived",
        "raw_source_path": "x.0",
        "evidence_scope": "row_level",
        "linked_rows": ["x.0"],
        "confidence": confidence,
        "reason": "test",
        "scoring_parent_id": "epa_dha",
        "canonical_id": "epa_dha",
        "evidence_canonical_id": "epa_dha",
        "canonical_source_db": "compat",
        "clean_identity_id": "fish_oil",
        "name": "EPA/DHA aggregate",
    }


def _multi_with_adjunct_omega() -> dict:
    return {
        "product_name": "Daily Multivitamin",
        "primary_type": "multivitamin",
        "product_scoring_evidence": [_omega_aggregate_evidence("low")],
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "vitamin_c_ascorbic_acid", "name": "Vitamin C",
                 "quantity": 90, "unit": "mg"},
            ]
        },
    }


def _evidence_row(evidence_type: str, canonical_id: str, confidence: str = "low") -> dict:
    return {
        "canonical_id": canonical_id,
        "name": canonical_id,
        "evidence_type": evidence_type,
        "confidence": confidence,
        "scoring_input_kind": "product_level_evidence",
        "quantity": 100,
        "unit": "mg",
    }


# --- Row 4: adjunct omega is not capped (the fix) ---------------------------

def test_adjunct_omega_in_multi_is_not_capped():
    product = _multi_with_adjunct_omega()
    # Sanity: the omega aggregate is an adjunct (major) in a multi, not primary.
    roles = {r["canonical_id"]: r["role"]
             for r in classify_ingredient_roles(product, module="multi_or_prenatal")}
    assert roles["epa_dha"] != "primary"

    res = evaluate_completeness_gate(product, "multi_or_prenatal")
    assert res.score_cap is None            # was 65.0 (bug)
    assert res.verdict_ceiling is None      # adjunct never forces CAUTION
    # Credit is still suppressed (audit tag retained), just not product-capped.
    assert "low_confidence_omega_breakdown" in res.soft_missing


def test_primary_omega_low_confidence_is_soft_debt_not_capped():
    # Same evidence, but routed as omega -> epa_dha is the primary driver.
    product = _multi_with_adjunct_omega()
    roles = {r["canonical_id"]: r["role"]
             for r in classify_ingredient_roles(product, module="omega")}
    assert roles["epa_dha"] == "primary"

    res = evaluate_completeness_gate(product, "omega")
    assert res.score_cap is None
    assert res.verdict_ceiling is None
    assert "low_confidence_omega_breakdown" in res.soft_missing


@pytest.mark.parametrize("module", ["multi_or_prenatal", "generic", "sports", "probiotic"])
def test_adjunct_omega_never_caps_in_non_omega_modules(module):
    product = _multi_with_adjunct_omega()
    res = evaluate_completeness_gate(product, module)
    assert res.score_cap is None
    assert res.verdict_ceiling is None


# --- Soft-policy unit gating ------------------------------------------------

def test_soft_policy_omega_evidence_never_caps():
    rows = [
        {"canonical_id": "vitamin_c_ascorbic_acid", "name": "Vitamin C",
         "quantity": 90, "unit": "mg", "scoring_input_kind": "normal"},
        _evidence_row("omega_epa_dha_aggregate", "epa_dha", "low"),
    ]
    soft, cap, ceiling = _soft_policy_from_scoring_evidence(
        rows, "multi_or_prenatal", cap_eligible_canonicals=set())
    assert cap is None
    assert "low_confidence_omega_breakdown" in soft

    soft2, cap2, _ = _soft_policy_from_scoring_evidence(
        rows, "omega", cap_eligible_canonicals={"epa_dha"})
    assert cap2 is None
    assert "low_confidence_omega_breakdown" in soft2


def test_soft_policy_percent_dv_evidence_never_caps():
    rows = [_evidence_row("percent_dv_dose", "turmeric", "medium")]
    rows[0]["dose_class"] = "percent_dv_only"

    _, cap_adjunct, _ = _soft_policy_from_scoring_evidence(
        rows, "generic", cap_eligible_canonicals=set())
    assert cap_adjunct is None

    soft, cap_primary, _ = _soft_policy_from_scoring_evidence(
        rows, "generic", cap_eligible_canonicals={"turmeric"})
    assert cap_primary is None
    assert "percent_dv_only_dose_evidence" in soft


# --- Rows 2 & 6: adjunct probiotic / sports tags never product-cap ----------

def test_soft_policy_probiotic_cfu_evidence_never_caps():
    # Row 2: an adjunct probiotic (CFU evidence) only suppresses credit.
    rows = [_evidence_row("probiotic_cfu", "lactobacillus_acidophilus", "low")]
    soft, cap, ceiling = _soft_policy_from_scoring_evidence(
        rows, "multi_or_prenatal", cap_eligible_canonicals=set())
    assert cap is None
    assert ceiling is None


def test_soft_policy_sports_primary_dose_evidence_never_caps():
    # Row 6: an adjunct sports active (dose evidence) only suppresses credit.
    rows = [_evidence_row("sports_primary_dose", "creatine_monohydrate", "low")]
    soft, cap, ceiling = _soft_policy_from_scoring_evidence(
        rows, "generic", cap_eligible_canonicals=set())
    assert cap is None
    assert ceiling is None


def test_empty_canonical_does_not_bridge_cap_eligibility():
    # IN-01 hardening: an empty-string canonical must never count as a
    # cap-eligible match, even if "" somehow lands in the set.
    rows = [_evidence_row("omega_epa_dha_aggregate", "", "low")]
    _, cap, _ = _soft_policy_from_scoring_evidence(
        rows, "omega", cap_eligible_canonicals={""})
    assert cap is None
