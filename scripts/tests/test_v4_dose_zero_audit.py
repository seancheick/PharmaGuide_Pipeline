"""Dose-zero audit policy for v4 scoring.

The scorer should not get a blanket dose floor. This audit separates honest
zero-dose outcomes from review candidates where a meaningful disclosed dose was
missed by a route-specific scorer.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _product(*, ingredients=None, rda_ul_data=None, evidence=None) -> dict:
    rows = list(ingredients or [])
    return {
        "product_name": "Audit Product",
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
            "total_active": len(rows),
        },
        "product_scoring_evidence": list(evidence or []),
        "rda_ul_data": rda_ul_data or {},
    }


def _ingredient(**overrides) -> dict:
    row = {
        "name": "Alpha Lipoic Acid",
        "canonical_id": "alpha_lipoic_acid",
        "mapped": True,
        "quantity": 300,
        "unit": "mg",
        "bio_score": 10,
    }
    row.update(overrides)
    return row


def test_audit_flags_meaningful_disclosed_dose_that_scores_zero() -> None:
    from api_audit.audit_v4_dose_zero import classify_dose_zero

    finding = classify_dose_zero(
        _product(ingredients=[_ingredient()]),
        route="generic",
        dose_payload={"score": 0.0, "metadata": {"window_proxy_reason": "no_rda_reference_data"}},
    )

    assert finding is not None
    assert finding["classification"] == "bug_candidate"
    assert finding["reason"] == "meaningful_disclosed_dose_scored_zero"


def test_audit_accepts_trace_omega_zero() -> None:
    from api_audit.audit_v4_dose_zero import classify_dose_zero

    finding = classify_dose_zero(
        _product(ingredients=[_ingredient(canonical_id="epa_dha", quantity=50, unit="mg")]),
        route="omega",
        dose_payload={"score": 0.0, "metadata": {"per_day_mid_mg": 50.0}},
    )

    assert finding is not None
    assert finding["classification"] == "valid_zero"
    assert finding["reason"] == "trace_omega_dose_below_threshold"


def test_audit_accepts_opaque_no_dose_zero() -> None:
    from api_audit.audit_v4_dose_zero import classify_dose_zero

    finding = classify_dose_zero(
        _product(ingredients=[_ingredient(quantity=None, unit=None)]),
        route="generic",
        dose_payload={"score": 0.0, "metadata": {}},
    )

    assert finding is not None
    assert finding["classification"] == "valid_zero"
    assert finding["reason"] == "no_meaningful_disclosed_dose"


def test_audit_accepts_unsafe_overdose_zero() -> None:
    from api_audit.audit_v4_dose_zero import classify_dose_zero

    product = _product(
        ingredients=[_ingredient()],
        rda_ul_data={"safety_flags": [{"nutrient": "Vitamin A", "pct_ul": 220}]},
    )

    finding = classify_dose_zero(
        product,
        route="generic",
        dose_payload={"score": 0.0, "metadata": {}},
    )

    assert finding is not None
    assert finding["classification"] == "valid_zero"
    assert finding["reason"] == "unsafe_overdose_zero"


def test_audit_accepts_probiotic_zero_when_only_non_probiotic_mass_is_disclosed() -> None:
    from api_audit.audit_v4_dose_zero import classify_dose_zero

    product = _product(
        ingredients=[_ingredient(name="Prebiotic Fiber", canonical_id="prebiotics", quantity=500, unit="mg")],
    )
    product["probiotic_data"] = {
        "is_probiotic": True,
        "total_strain_count": 2,
        "has_cfu": False,
        "total_cfu": 0,
        "total_billion_count": 0,
        "probiotic_blends": [],
        "clinical_strains": [],
    }

    finding = classify_dose_zero(
        product,
        route="probiotic",
        dose_payload={"score": 0.0, "metadata": {"aggregate_cfu_proxy": {"reason": "aggregate_cfu_missing"}}},
    )

    assert finding is not None
    assert finding["classification"] == "valid_zero"
    assert finding["reason"] == "no_meaningful_probiotic_dose"


def test_audit_flags_probiotic_zero_when_total_cfu_is_disclosed() -> None:
    from api_audit.audit_v4_dose_zero import classify_dose_zero

    product = _product()
    product["probiotic_data"] = {
        "is_probiotic": True,
        "total_strain_count": 4,
        "has_cfu": True,
        "total_cfu": 1_000_000_000,
        "total_billion_count": 1.0,
        "probiotic_blends": [],
        "clinical_strains": [],
    }

    finding = classify_dose_zero(
        product,
        route="probiotic",
        dose_payload={"score": 0.0, "metadata": {"aggregate_cfu_proxy": {"reason": "no_clinical_strains_for_proxy"}}},
    )

    assert finding is not None
    assert finding["classification"] == "bug_candidate"
    assert finding["reason"] == "meaningful_disclosed_dose_scored_zero"
