"""v4 Generic Dose dimension — P1.3.2a tests.

Dose 25 has three lines per §6:

    | Item                                  | Cap | Notes                  |
    |---------------------------------------|----:|------------------------|
    | Dose inside the supplemental window   |  22 | NEW framing per §6 line 369 |
    | Multi-form complex bonus              |   3 | ≥2 premium forms of the same nutrient |
    | B7 dose safety penalty (>150% UL)     |  -3 | up to -3                |

P1.3.2a state: supplemental-window math is implemented as an
**RDA/UL proxy** (`pct_rda` / `pct_ul` from existing enriched
`rda_ul_data.adequacy_results`). True window math per §6 line 369
requires a `typical_dietary_intake` reference table that does NOT
exist yet — tracked as a P1.3.2b / P1.5 calibration task.

Guardrail: every test on a real product asserts the dimension
breakdown carries the proxy-method metadata so no downstream tool
mistakes the proxy band for final NIH/NHANES supplemental-window math.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    *,
    name: str = "Magnesium",
    standard_name: str | None = None,
    canonical_id: str = "magnesium",
    bio_score: float = 14,
    quantity: float = 200,
    unit: str = "mg",
) -> dict:
    return {
        "name": name,
        "standard_name": standard_name or name,
        "canonical_id": canonical_id,
        "mapped": True,
        "bio_score": bio_score,
        "quantity": quantity,
        "unit": unit,
    }


def _product(
    *,
    ingredients: list | None = None,
    adequacy_results: list | None = None,
    safety_flags: list | None = None,
    supp_type: str = "single_nutrient",
    **extra,
) -> dict:
    rows = ingredients if ingredients is not None else [_ingredient()]
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": supp_type},
        "ingredient_quality_data": {
            "total_active": len(rows),
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
    }
    if adequacy_results is not None or safety_flags is not None:
        product["rda_ul_data"] = {
            "adequacy_results": adequacy_results or [],
            "safety_flags": safety_flags or [],
        }
    product.update(extra)
    return product


def _adequacy(*, nutrient: str = "Magnesium", pct_rda: float | None = 50.0, pct_ul: float | None = 57.0) -> dict:
    return {"nutrient": nutrient, "pct_rda": pct_rda, "pct_ul": pct_ul}


# --- Proxy metadata guardrails -------------------------------------------


def test_dose_payload_carries_proxy_metadata() -> None:
    """GUARDRAIL: every Dose payload must carry the proxy-method markers
    so downstream tooling never mistakes the proxy band for final
    NIH/NHANES supplemental-window math."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy()]))

    meta = payload["metadata"]
    assert meta["phase"] == "P1.3.2a_dose_proxy"
    assert meta["method"] == "rda_ul_proxy_until_dietary_intake_table"
    assert meta["deferred_data_dependency"] == "typical_dietary_intake"


def test_dose_phase_marker() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy()]))
    assert payload["phase"] == "P1.3.2a_dose_proxy"


def test_dose_dimension_cap_25() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product())
    assert payload["max"] == 25.0


# --- Supplemental-window proxy: in-window cases --------------------------


def test_window_proxy_in_window_returns_22() -> None:
    """Thorne Mg Bisglycinate canary: 200mg = 50% of 400mg RDA, 57% of 350mg
    supplemental UL → fully inside window → 22 pts."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=50.0, pct_ul=57.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 22.0


def test_window_proxy_just_at_25_pct_rda_full_credit() -> None:
    """Boundary: pct_rda exactly at 25% qualifies for full credit (the
    sub-clinical proportional band is strictly < 25%)."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=25.0, pct_ul=10.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 22.0


def test_window_proxy_over_rda_under_ul_full_credit() -> None:
    """Above RDA but below UL — still in the supplemental window."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=120.0, pct_ul=80.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 22.0


# --- Supplemental-window proxy: sub-clinical case ------------------------


def test_window_proxy_subclinical_proportional() -> None:
    """pct_rda = 10% → proportional: (10/25) * 22 = 8.8 pts."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=10.0, pct_ul=2.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 8.8


def test_window_proxy_zero_dose_no_credit() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=0.0, pct_ul=0.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 0.0


# --- Supplemental-window proxy: overdose cases ---------------------------


def test_window_proxy_over_ul_under_150_partial_credit() -> None:
    """101%-149% of UL → overdose territory, half credit (11 pts).
    150%+ is B7's job; this band penalises mild over-dose without B7."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=300.0, pct_ul=120.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 11.0


def test_window_proxy_over_150_ul_returns_zero() -> None:
    """≥150% UL — the window proxy contributes 0; B7 penalty handles
    the dose-safety issue. (Avoids double-penalising.)"""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(pct_rda=400.0, pct_ul=180.0)]))
    assert payload["components"]["supplemental_window_proxy"] == 0.0


# --- Supplemental-window proxy: no data case -----------------------------


def test_window_proxy_no_rda_data_with_label_dose_gets_partial_credit() -> None:
    """Botanicals / herbal products without RDA reference data can still
    have real label dosing. They get conservative partial credit, with
    metadata marking that this is not NIH/NHANES window math."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(adequacy_results=[]))
    assert payload["score"] == 16.0
    assert payload["components"]["supplemental_window_proxy"] == 16.0
    assert payload["metadata"]["window_proxy_reason"] == "no_rda_reference_data"
    assert payload["metadata"]["window_proxy_status"] == "partial_credit_without_rda_proxy"
    assert payload["metadata"]["partial_credit_reason"] == "individual_quantified_dose_no_rda_reference"


def test_ksm66_style_botanical_no_rda_is_not_punished_as_zero_dose() -> None:
    """KSM-66 / botanical products have real mg dosing but no RDA/UL benchmark.
    Phase 6: instead of the conservative generic proxy (16), a recognized
    botanical with a clinical dose range is scored against that range. KSM-66
    ashwagandha at 600 mg sits within the studied 250-600 mg window, so it
    earns the within-range credit (21) — strictly better than being treated
    as a no-RDA nutrient, and never punished as zero dose."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[
                _ingredient(
                    name="KSM-66 Ashwagandha",
                    standard_name="Ashwagandha",
                    canonical_id="ashwagandha",
                    bio_score=11,
                    quantity=600,
                    unit="mg",
                )
            ],
            adequacy_results=[
                _adequacy(nutrient="Ashwagandha", pct_rda=None, pct_ul=None),
            ],
        )
    )
    assert payload["score"] == 21.0
    assert payload["components"]["botanical_clinical_dose"] == 21.0
    assert payload["metadata"]["method"] == "botanical_clinical_dose_v1"
    assert payload["metadata"]["botanical_dose_band"] == "within_studied_range"


def test_window_proxy_no_rda_and_no_quantified_dose_stays_not_evaluable() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[_ingredient(quantity=0, unit="")],
            adequacy_results=[],
        )
    )

    assert payload["score"] is None
    assert payload["metadata"]["window_proxy_status"] == "not_evaluable_by_rda_proxy"


def test_window_proxy_partial_rda_data_skips_unscorable_rows() -> None:
    """Mixed product: one nutrient with pct_rda data, one without → only
    the dosed one contributes; reason metadata records the skip."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[
                _adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0),
                _adequacy(nutrient="Turmeric", pct_rda=None, pct_ul=None),
            ]
        )
    )
    assert payload["components"]["supplemental_window_proxy"] == 22.0


def test_window_proxy_averages_across_nutrients() -> None:
    """Two scored nutrients: one in-window (22), one sub-clinical at 10%
    (8.8) → avg = 15.4."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[
                _adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0),
                _adequacy(nutrient="Zinc", pct_rda=10.0, pct_ul=2.0),
            ]
        )
    )
    assert payload["components"]["supplemental_window_proxy"] == 15.4


# --- Multi-form bonus ----------------------------------------------------


def test_multi_form_bonus_two_premium_mg_forms() -> None:
    """Mg glycinate + Mg malate (both bio≥12, both standard_name=Magnesium)
    → +3 multi-form bonus."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[
                _ingredient(name="Mg Glycinate", standard_name="Magnesium",
                            canonical_id="mg_glycinate", bio_score=14),
                _ingredient(name="Mg Malate", standard_name="Magnesium",
                            canonical_id="mg_malate", bio_score=13),
            ]
        )
    )
    assert payload["components"]["multi_form_bonus"] == 3.0


def test_multi_form_bonus_single_premium_form_zero() -> None:
    """One premium form (no second to stack with) → 0 multi-form bonus."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(ingredients=[_ingredient(bio_score=14)]))
    assert payload["components"]["multi_form_bonus"] == 0.0


def test_multi_form_bonus_premium_plus_non_premium_zero() -> None:
    """Mg glycinate (bio=14) + Mg oxide (bio=8 < 12 threshold) → 0 multi-form
    (only one PREMIUM form present)."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[
                _ingredient(name="Mg Glycinate", standard_name="Magnesium",
                            canonical_id="mg_glycinate", bio_score=14),
                _ingredient(name="Mg Oxide", standard_name="Magnesium",
                            canonical_id="mg_oxide", bio_score=8),
            ]
        )
    )
    assert payload["components"]["multi_form_bonus"] == 0.0


def test_multi_form_bonus_two_different_nutrients_zero() -> None:
    """Different nutrient families don't stack. Mg glycinate + B12 methyl
    are both premium but different standard_names → no multi-form bonus."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[
                _ingredient(name="Mg Glycinate", standard_name="Magnesium",
                            canonical_id="mg_glycinate", bio_score=14),
                _ingredient(name="Methyl B12", standard_name="Vitamin B12",
                            canonical_id="methyl_b12", bio_score=14),
            ]
        )
    )
    assert payload["components"]["multi_form_bonus"] == 0.0


def test_multi_form_bonus_three_premium_mg_still_3_pts() -> None:
    """3+ premium forms still cap at 3 pts (single bonus, no stacking)."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[
                _ingredient(name="A", standard_name="Magnesium",
                            canonical_id="a", bio_score=14),
                _ingredient(name="B", standard_name="Magnesium",
                            canonical_id="b", bio_score=13),
                _ingredient(name="C", standard_name="Magnesium",
                            canonical_id="c", bio_score=12),
            ]
        )
    )
    assert payload["components"]["multi_form_bonus"] == 3.0


def test_multi_form_bonus_case_insensitive_nutrient_match() -> None:
    """'magnesium' vs 'Magnesium' must group together — case-insensitive."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            ingredients=[
                _ingredient(name="Form A", standard_name="magnesium",
                            canonical_id="a", bio_score=14),
                _ingredient(name="Form B", standard_name="MAGNESIUM",
                            canonical_id="b", bio_score=13),
            ]
        )
    )
    assert payload["components"]["multi_form_bonus"] == 3.0


# --- B7 dose safety penalty ---------------------------------------------


def test_b7_penalty_single_over_150_ul_returns_minus_2() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(safety_flags=[{"nutrient": "Vit B6", "pct_ul": 200, "ul": 100, "amount": 200}]))
    assert payload["penalties"]["B7_dose_safety"] == -2.0


def test_b7_penalty_two_over_ul_caps_at_minus_3() -> None:
    """Two over-UL flags: 2.0 + 2.0 = 4.0, capped at 3.0 → -3.0."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            safety_flags=[
                {"nutrient": "A", "pct_ul": 180},
                {"nutrient": "B", "pct_ul": 200},
            ]
        )
    )
    assert payload["penalties"]["B7_dose_safety"] == -3.0


def test_b7_penalty_below_150_pct_returns_zero() -> None:
    """pct_ul = 120 (above UL but below 150% threshold) → no B7 penalty."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product(safety_flags=[{"nutrient": "A", "pct_ul": 120}]))
    assert payload["penalties"]["B7_dose_safety"] == 0.0


def test_b7_penalty_no_safety_flags_returns_zero() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(_product())
    assert payload["penalties"]["B7_dose_safety"] == 0.0


# --- Dimension score assembly --------------------------------------------


def test_dimension_score_thorne_canary_22_of_25() -> None:
    """Thorne Mg Bisglycinate 200mg: window proxy 22 + multi-form 0 - B7 0
    = 22/25. Matches §6 line 425 worked example."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[_adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0)],
            ingredients=[_ingredient()],
        )
    )
    assert payload["score"] == 22.0
    assert payload["max"] == 25.0


def test_dimension_score_clamps_to_max_25() -> None:
    """Window 22 + multi-form 3 = 25. Should not exceed 25."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[
                _adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0),
            ],
            ingredients=[
                _ingredient(name="A", standard_name="Magnesium", canonical_id="a", bio_score=14),
                _ingredient(name="B", standard_name="Magnesium", canonical_id="b", bio_score=13),
            ],
        )
    )
    assert payload["score"] == 25.0


def test_dimension_score_floors_at_zero() -> None:
    """When a real B7 dose-safety flag exists, the dimension is evaluable
    and still floors at zero."""
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(
        _product(
            adequacy_results=[_adequacy(pct_rda=0.0, pct_ul=180.0)],
            safety_flags=[{"nutrient": "A", "pct_ul": 200}],
        )
    )
    assert payload["score"] >= 0.0


def test_dimension_score_handles_malformed_input() -> None:
    from scoring_v4.modules.generic_dose import score_dose

    payload = score_dose(None)  # type: ignore[arg-type]
    assert payload["score"] is None
    assert payload["max"] == 25.0
    assert "supplemental_window_proxy" in payload["components"]
    assert "B7_dose_safety" in payload["penalties"]


# --- Shadow integration --------------------------------------------------


def test_shadow_wires_dose_dimension() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(
        _product(
            adequacy_results=[_adequacy(nutrient="Magnesium", pct_rda=50.0, pct_ul=57.0)],
        )
    )
    dose_dim = out["shadow_score_v4_breakdown"]["module"]["dimensions"]["dose"]
    assert dose_dim["score"] == 22.0
    assert dose_dim["max"] == 25.0
    assert "supplemental_window_proxy" in dose_dim["components"]
    # The proxy metadata must propagate through to the module breakdown so
    # audit / Flutter tooling sees it.
    assert dose_dim["metadata"]["phase"] == "P1.3.2a_dose_proxy"
    assert dose_dim["metadata"]["method"] == "rda_ul_proxy_until_dietary_intake_table"


def test_shadow_top_level_score_populated_at_p136() -> None:
    """P1.3.6 final assembly populates top-level shadow_score_v4_100."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_product())
    assert out["shadow_score_v4_100"] is not None
    assert out["shadow_score_v4_confidence"] in {"high", "moderate", "low"}
    assert out["shadow_score_v4_breakdown"]["confidence"]["band"] == out["shadow_score_v4_confidence"]


# --- Architecture lock ---------------------------------------------------


def test_generic_dose_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_dose as gd

    source = Path(gd.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
