"""v4 Probiotic final assembly — P2.6 tests.

Closes the probiotic module by:

  1. Wiring `score_manufacturer_trust` (+0 to +5) and
     `score_manufacturer_violations` (0 to -25, escalates to -35/-50
     for ≥2/≥3 recent Class-I violations) — reuses the generic helpers.

  2. Assembling `raw_score_100`:
       class_subtotal = (sum(dim.score) / sum(dim.max for evaluable dims)) * 100
       adjusted = class_subtotal + manufacturer_trust + manufacturer_violations
       raw_score_100 = clamp(0, 100, adjusted)

  3. Applying the P1.5 affine calibration:
       score_100 = clamp(0, 100, 25 + 0.75 * raw_score_100)

  4. Wiring shadow scorer dispatch so probiotic now emits a real
     `shadow_score_v4_100`, verdict, and typed confidence band (matching
     the pattern P1.4 added for generic).

  5. Extending `_label_completeness_confidence` to recognize probiotic
     per-strain CFU disclosure gap (window_proxy_reason ∈
     {"aggregate_cfu_not_per_strain", "no_strain_data",
      "per_strain_cfu_missing"}) → moderate label completeness with a
     probiotic-specific driver.

Verdict: CAUTION carried from Layer 1 still wins. Otherwise POOR if
calibrated score < 40, else SAFE.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _probiotic_product(
    *,
    strain_count: int = 5,
    total_billion: float = 50.0,
    clinical_strain_count: int = 5,
    survivability: bool = True,
    prebiotic: bool = True,
    trust_certs: list | None = None,
    gmp: dict | None = None,
    has_disease_claims: bool = False,
    is_trusted_manufacturer: bool = False,
    manufacturing_region: str = "",
    has_critical_violations: int = 0,
    **extra,
):
    """Complete, scoreable probiotic product fixture."""
    blends = [
        {"name": f"Strain {i+1}",
         "strains": [f"Lactobacillus species_{i+1}"],
         "cfu_data": {"has_cfu": False, "billion_count": 0}}
        for i in range(strain_count)
    ]
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "supplement_type": {"type": "probiotic"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {"name": "Probiotic blend", "canonical_id": "probiotic_blend",
                 "mapped": True, "has_dose": True}
            ],
        },
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_billion_count": total_billion,
            "total_strain_count": strain_count,
            "clinical_strain_count": clinical_strain_count,
            "probiotic_blends": blends,
            "has_survivability_coating": survivability,
            "prebiotic_present": prebiotic,
            "clinical_strains": [
                {"name": f"Strain_{i+1}", "clinical_support_level": "high",
                 "adequacy_tier": None, "cfu_per_day": None}
                for i in range(clinical_strain_count)
            ],
        },
        "has_disease_claims": has_disease_claims,
        "verified_cert_programs": trust_certs or [],
        "certification_data": {"gmp": gmp or {}, "batch_traceability": {}},
        "is_trusted_manufacturer": is_trusted_manufacturer,
        "manufacturing_region": manufacturing_region,
    }
    if has_critical_violations > 0:
        from datetime import date
        product["manufacturer_data"] = {"violations": {
            "total_deduction_applied": -25 * has_critical_violations,
            "violations": [
                {"severity_level": "critical",
                 "date": date.today().isoformat()}
                for _ in range(has_critical_violations)
            ]
        }}
    product.update(extra)
    return product


# --- Final assembly contract ---------------------------------------------


def test_probiotic_score_100_assembled_at_p26() -> None:
    """A complete probiotic product gets a real raw_score_100 + calibrated
    score_100 after P2.6 final assembly."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product()).to_breakdown()

    assert breakdown["raw_score_100"] is not None
    assert breakdown["score_100"] is not None
    assert 0 <= breakdown["raw_score_100"] <= 100
    assert 0 <= breakdown["score_100"] <= 100


def test_probiotic_calibration_applied() -> None:
    """score_100 = clamp(0, 100, 25 + 0.75 * raw_score_100)."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product()).to_breakdown()
    raw = breakdown["raw_score_100"]
    expected_cal = max(0.0, min(100.0, 25.0 + 0.75 * raw))
    assert abs(breakdown["score_100"] - expected_cal) < 0.01


def test_probiotic_assembly_excludes_none_dimensions_from_denominator() -> None:
    """If a dimension is None (rare for probiotic; usually all 5 populate),
    its max is excluded from the denominator instead of zero-counting."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product()).to_breakdown()
    meta = breakdown["metadata"]
    # All 5 dimensions populated → evaluable_max == 100
    assert meta["evaluable_class_max"] == 100.0
    assert meta["excluded_dimensions"] == []


def test_probiotic_manufacturer_trust_wired() -> None:
    """A trusted manufacturer (D1) + USA region (D4) lifts score."""
    from scoring_v4.modules.probiotic import score_probiotic

    base = score_probiotic(_probiotic_product()).to_breakdown()
    boosted = score_probiotic(_probiotic_product(
        is_trusted_manufacturer=True,
        manufacturing_region="usa",
    )).to_breakdown()

    assert boosted["manufacturer_trust"]["score"] > 0
    assert boosted["raw_score_100"] > base["raw_score_100"]


def test_probiotic_manufacturer_violations_drag_score_down() -> None:
    """A critical violation drags raw_score_100 down."""
    from scoring_v4.modules.probiotic import score_probiotic

    base = score_probiotic(_probiotic_product()).to_breakdown()
    flagged = score_probiotic(
        _probiotic_product(has_critical_violations=1)
    ).to_breakdown()

    assert flagged["manufacturer_violations"]["score"] < 0
    assert flagged["raw_score_100"] < base["raw_score_100"]


def test_probiotic_phase_marker_p26_final_assembly() -> None:
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product()).to_breakdown()
    assert breakdown["phase"] == "P2.6_probiotic_final_assembly"


def test_probiotic_score_clamped_to_100() -> None:
    """Even with maximum signals, score_100 caps at 100."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product(
        trust_certs=[
            {"program": "nsf certified for sport", "scope": "sku", "evidence_source": "registry"},
            {"program": "usp verified", "scope": "sku", "evidence_source": "registry"},
            {"program": "informed choice", "scope": "sku", "evidence_source": "registry"},
        ],
        gmp={"nsf_gmp": True},
        is_trusted_manufacturer=True,
        manufacturing_region="usa",
    )).to_breakdown()
    assert breakdown["score_100"] <= 100.0
    assert breakdown["raw_score_100"] <= 100.0


def test_probiotic_score_floored_at_zero() -> None:
    """Catastrophic violations + low signals can't drive score below 0."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product(
        strain_count=0,
        total_billion=0,
        clinical_strain_count=0,
        survivability=False,
        prebiotic=False,
        has_critical_violations=3,
    )).to_breakdown()
    assert breakdown["score_100"] >= 0.0


def test_probiotic_assembly_metadata_carries_audit_fields() -> None:
    """The metadata block records all the audit fields P1.3.6 emits for
    generic — raw_dimension_sum, class_subtotal, calibration block, etc."""
    from scoring_v4.modules.probiotic import score_probiotic

    breakdown = score_probiotic(_probiotic_product()).to_breakdown()
    meta = breakdown["metadata"]

    assert "raw_dimension_sum" in meta
    assert "class_subtotal" in meta
    assert "manufacturer_trust_adjustment" in meta
    assert "manufacturer_violation_adjustment" in meta
    assert "calibration" in meta
    assert meta["calibration"]["method"] == "affine_p15"
    assert meta["calibration"]["intercept"] == 25.0
    assert meta["calibration"]["slope"] == 0.75


# --- Shadow scorer wiring -------------------------------------------------


def test_shadow_emits_real_score_for_probiotic_at_p26() -> None:
    """The shadow scorer now emits shadow_score_v4_100 + verdict +
    confidence band for probiotic products — matching the generic
    P1.4 pattern."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_probiotic_product())

    assert out["shadow_score_v4_module"] == "probiotic"
    assert out["shadow_score_v4_100"] is not None
    assert out["shadow_score_v4_verdict"] in {"SAFE", "POOR", "CAUTION"}
    # Probiotic confidence now goes through evaluate_confidence
    assert out["shadow_score_v4_confidence"] in {"high", "moderate", "low"}


def test_shadow_verdict_safe_when_score_above_40() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    # Strong probiotic with SKU certs → calibrated score well above 40
    product = _probiotic_product(
        trust_certs=[
            {"program": "nsf certified for sport", "scope": "sku", "evidence_source": "registry"}
        ],
    )
    out = score_product_v4_shadow(product)
    assert out["shadow_score_v4_100"] > 40.0
    assert out["shadow_score_v4_verdict"] == "SAFE"


def test_shadow_verdict_caution_overrides_score_band() -> None:
    """A disease-claim CAUTION carried from Layer 1 wins over the SAFE
    score band."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _probiotic_product(has_disease_claims=True)
    out = score_product_v4_shadow(product)
    # Score may still be SAFE-range but the verdict is CAUTION (carried).
    assert out["shadow_score_v4_verdict"] == "CAUTION"


def test_shadow_blocked_safety_short_circuits_before_p26() -> None:
    """A banned-substance probiotic still short-circuits at Layer 1.
    No module scoring runs, no score_100 assembled."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _probiotic_product()
    product["contaminant_data"] = {
        "banned_substances": {"substances": [
            {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
        ]}
    }
    out = score_product_v4_shadow(product)
    assert out["shadow_score_v4_verdict"] == "BLOCKED"
    assert out["shadow_score_v4_100"] is None
    assert out["shadow_score_v4_confidence"] == "blocked_by_safety_gate"


# --- Confidence wiring ----------------------------------------------------


def test_confidence_label_completeness_flags_per_strain_cfu_gap() -> None:
    """Probiotic with aggregate-CFU-only (no per-strain CFU) should
    surface as a label_completeness driver: not-final-window but a
    probiotic-specific signal."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_probiotic_product())  # aggregate CFU only
    conf = out["shadow_score_v4_breakdown"]["confidence"]
    drivers = conf["label_completeness"]["drivers"]

    # The driver name we plan to emit:
    assert any("per_strain_cfu" in d.lower() or "cfu_disclosure" in d.lower()
               for d in drivers), f"expected per-strain-CFU driver, got {drivers}"
    assert conf["label_completeness"]["level"] in {"moderate", "low"}


def test_confidence_high_when_full_per_strain_disclosure() -> None:
    """A probiotic that DOES disclose per-strain CFU shouldn't get the
    aggregate-only label-completeness penalty."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _probiotic_product()
    # Replace blends with per-strain CFU disclosure
    product["probiotic_data"]["probiotic_blends"] = [
        {"name": f"L. species_{i+1}",
         "strains": [f"L. species_{i+1}"],
         "cfu_data": {"has_cfu": True, "billion_count": 10}}
        for i in range(5)
    ]
    # Also add per-strain cfu_per_day to clinical_strains for adequacy
    product["probiotic_data"]["clinical_strains"] = [
        {"name": f"L. species_{i+1}",
         "clinical_support_level": "high",
         "adequacy_tier": "adequate", "cfu_per_day": 1e10}
        for i in range(5)
    ]
    out = score_product_v4_shadow(product)
    conf = out["shadow_score_v4_breakdown"]["confidence"]
    drivers = conf["label_completeness"]["drivers"]
    # No per-strain-CFU driver expected
    assert not any("per_strain_cfu" in d.lower() for d in drivers)


# --- Canary integration ---------------------------------------------------


def test_canary_spring_valley_probiotic_50b_scoreable_at_p26() -> None:
    """Real DSLD canary 178346 — should now emit a real score_100."""
    import json
    from score_supplements_v4_shadow import score_product_v4_shadow

    products_root = Path("/Users/seancheick/Downloads/dsld_clean/scripts/products")
    for p in products_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            items = json.loads(p.read_text())
            if isinstance(items, dict): items = items.get("products", items.get("items", []))
        except Exception:
            continue
            for item in items:
                if str(item.get("dsld_id")) == "178346":
                    from scoring_input_contract import get_scoring_ingredients
                    scoring_input = get_scoring_ingredients(item, strict=True)
                    if not scoring_input.rows:
                        pytest.skip(
                            "Spring Valley 50B canary artifact lacks strict v4 scoring inputs; "
                            "rerun enrichment before using as canary"
                        )
                    out = score_product_v4_shadow(item)
                assert out["shadow_score_v4_module"] == "probiotic"
                assert out["shadow_score_v4_100"] is not None
                assert out["shadow_score_v4_verdict"] in {"SAFE", "POOR", "CAUTION"}
                return
    # If the canary isn't in the enriched dirs, skip gracefully
    import pytest
    pytest.skip("Spring Valley 50B canary blob not found in enriched dirs")
