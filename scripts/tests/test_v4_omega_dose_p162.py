"""v4 Omega Dose dimension — P1.6.2 tests.

Locks the Dose sub-component math:

    epa_dha_band     /20  EFSA/FDA/AHA-grounded thresholds:
                          4000+ → 20  (prescription)
                          2000+ → 17.5 (EFSA TG claim)
                          1000+ → 16   (AHA CVD)
                          500+  → 10   (FDA QHC)
                          250+  → 5    (EFSA AI)
                          <250  → 0
    ratio_sanity     /5   EPA:DHA in 1:3..3:1 → +5
                          Outside range → 0
                          Pure-EPA or pure-DHA → 0 (exempt, not penalized)

Per Sean 'do not invent fields': only canonical_id ∈ {epa, dha, epa_dha}
rows with valid mg/g/mcg units contribute. Fish-oil parent mass is NOT
counted as EPA+DHA. Daily-servings comes from servingSizes[0]; defaults
to 1/day when missing (safe baseline).

Per §13 architecture lock — no v3 imports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _omega_product(
    *,
    epa: float | None = 600,
    dha: float | None = 300,
    epa_unit: str = "mg",
    dha_unit: str = "mg",
    combined: float | None = None,
    combined_unit: str = "mg",
    daily_servings: tuple[float, float] = (1.0, 1.0),
    extra_ingredients: list | None = None,
) -> dict:
    """Build a minimal omega product for Dose tests."""
    ingredients = []
    if epa is not None:
        ingredients.append({"name": "EPA", "canonical_id": "epa",
                            "quantity": epa, "unit": epa_unit, "mapped": True})
    if dha is not None:
        ingredients.append({"name": "DHA", "canonical_id": "dha",
                            "quantity": dha, "unit": dha_unit, "mapped": True})
    if combined is not None:
        ingredients.append({"name": "EPA+DHA", "canonical_id": "epa_dha",
                            "quantity": combined, "unit": combined_unit, "mapped": True})
    if extra_ingredients:
        ingredients.extend(extra_ingredients)

    return {
        "status": "active",
        "form_factor": "softgel",
        "product_name": "Test Omega",
        "supplement_taxonomy": {"primary_type": "omega_3"},
        "supplement_type": {"type": "specialty"},
        "servingSizes": [{
            "minDailyServings": daily_servings[0],
            "maxDailyServings": daily_servings[1],
        }],
        "ingredient_quality_data": {"ingredients_scorable": ingredients},
    }


# --- Component contract --------------------------------------------------


def test_returns_normalized_payload_shape() -> None:
    from scoring_v4.modules.omega_dose import score_dose

    payload = score_dose(_omega_product())
    for key in ("score", "max", "components", "penalties", "metadata"):
        assert key in payload
    assert payload["max"] == 25.0
    assert payload["metadata"]["phase"] == "P1.6.2_omega_dose"


def test_empty_product_scores_zero_with_reason() -> None:
    from scoring_v4.modules.omega_dose import score_dose

    payload = score_dose({})
    assert payload["score"] == 0.0
    assert payload["metadata"]["reason"] == "no_disclosed_epa_dha"


def test_none_input_scores_zero_safely() -> None:
    from scoring_v4.modules.omega_dose import score_dose

    payload = score_dose(None)
    assert payload["score"] == 0.0


# --- EPA+DHA band lookup ------------------------------------------------


def test_band_prescription_dose() -> None:
    """4000+ mg/day EPA+DHA → prescription_dose band (20) + flag.
    Real-world threshold: AHA/ACC for hypertriglyceridemia."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=2500, dha=2000)  # 4500 mg/day
    payload = score_dose(product)
    assert payload["components"]["epa_dha_band"] == 20.0
    assert payload["metadata"]["epa_dha_band_label"] == "prescription_dose"
    assert payload["metadata"]["epa_dha_band_flag"] == "PRESCRIPTION_DOSE_OMEGA3"


def test_band_high_clinical() -> None:
    """2000-4000 mg/day → high_clinical band = FULL dose credit (20).

    Calibration 2026-06-05 (purpose-fit omega lane): 2000 mg EPA+DHA/day is a
    genuine high-clinical consumer dose (AHA secondary-prevention ~1000 mg;
    2-4 g is the hypertriglyceridemia range). Full dose credit is reached here,
    NOT gated behind the prescription-level 4000 mg band. Bands below 2000 are
    unchanged — no low-dose fish-oil inflation."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=1500, dha=900)  # 2400 mg/day
    payload = score_dose(product)
    assert payload["components"]["epa_dha_band"] == 20.0
    assert payload["metadata"]["epa_dha_band_label"] == "high_clinical"


def test_no_extra_band_credit_above_2000() -> None:
    """Policy lock: >2000 mg/day earns NO extra band credit over the 2000 mg
    full-credit dose — prescription-level intake is special-use, not "better".
    A 2400 mg and a 4500 mg product both cap the band at 20; the only
    difference is the 4500 mg product carries the PRESCRIPTION_DOSE_OMEGA3
    context flag."""
    from scoring_v4.modules.omega_dose import score_dose

    high_clinical = score_dose(_omega_product(epa=1500, dha=900))   # 2400 mg/day
    prescription = score_dose(_omega_product(epa=2500, dha=2000))   # 4500 mg/day
    assert high_clinical["components"]["epa_dha_band"] == 20.0
    assert prescription["components"]["epa_dha_band"] == 20.0
    assert high_clinical["metadata"]["epa_dha_band_flag"] is None
    assert prescription["metadata"]["epa_dha_band_flag"] == "PRESCRIPTION_DOSE_OMEGA3"


def test_band_aha_cvd() -> None:
    """1000-2000 mg/day → aha_cvd band (16). AHA CVD recommendation."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=700, dha=400)  # 1100 mg/day
    payload = score_dose(product)
    assert payload["components"]["epa_dha_band"] == 16.0
    assert payload["metadata"]["epa_dha_band_label"] == "aha_cvd"


def test_band_general_health() -> None:
    """500-1000 mg/day → general_health band (10). FDA QHC threshold."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=400, dha=300)  # 700 mg/day
    payload = score_dose(product)
    assert payload["components"]["epa_dha_band"] == 10.0
    assert payload["metadata"]["epa_dha_band_label"] == "general_health"


def test_band_efsa_ai_zone() -> None:
    """250-500 mg/day → efsa_ai_zone (5). EFSA AI for general population."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=200, dha=100)  # 300 mg/day
    payload = score_dose(product)
    assert payload["components"]["epa_dha_band"] == 5.0
    assert payload["metadata"]["epa_dha_band_label"] == "efsa_ai_zone"


def test_band_below_efsa_ai() -> None:
    """<250 mg/day → below_efsa_ai (0). No band credit."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=100, dha=50)  # 150 mg/day
    payload = score_dose(product)
    assert "epa_dha_band" not in payload["components"]
    assert payload["metadata"]["epa_dha_band_label"] == "below_efsa_ai"


# --- Ratio sanity -------------------------------------------------------


def test_ratio_sanity_in_range_awards_full_credit() -> None:
    """EPA:DHA = 2:1 (within 1:3..3:1) → +5."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=600, dha=300)  # ratio 2.0
    payload = score_dose(product)
    assert payload["components"]["ratio_sanity"] == 5.0
    assert payload["metadata"]["ratio_sanity"]["status"] == "in_range"
    assert payload["metadata"]["ratio_sanity"]["epa_dha_ratio"] == 2.0


def test_ratio_sanity_at_low_boundary_in_range() -> None:
    """EPA:DHA = 1:3 (boundary) → in_range (inclusive)."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=100, dha=300)  # ratio 0.333
    payload = score_dose(product)
    assert payload["components"]["ratio_sanity"] == 5.0


def test_ratio_sanity_at_high_boundary_in_range() -> None:
    """EPA:DHA = 3:1 (boundary) → in_range."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=900, dha=300)  # ratio 3.0
    payload = score_dose(product)
    assert payload["components"]["ratio_sanity"] == 5.0


def test_ratio_sanity_out_of_range_zero() -> None:
    """EPA:DHA = 19:1 (extreme imbalance) → 0 ratio credit."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=1900, dha=100)  # ratio 19
    payload = score_dose(product)
    assert "ratio_sanity" not in payload["components"]
    assert payload["metadata"]["ratio_sanity"]["status"] == "out_of_range"


def test_ratio_sanity_pure_epa_exempt() -> None:
    """Pure-EPA (no DHA) is exempt from ratio sanity. Score 0 for ratio,
    not penalized — band still scores normally."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=1000, dha=None)
    payload = score_dose(product)
    assert "ratio_sanity" not in payload["components"]
    assert payload["metadata"]["ratio_sanity"]["status"] == "exempt_one_component_zero"
    # Band still works on EPA alone.
    assert payload["components"]["epa_dha_band"] == 16.0  # 1000 mg → aha_cvd


def test_ratio_sanity_pure_dha_exempt() -> None:
    """Pure-DHA (algal) — exempt from ratio sanity."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=None, dha=300)
    payload = score_dose(product)
    assert "ratio_sanity" not in payload["components"]
    assert payload["metadata"]["ratio_sanity"]["status"] == "exempt_one_component_zero"


# --- Unit conversion ----------------------------------------------------


def test_unit_grams_converts_to_mg() -> None:
    """A product labeling EPA in grams must convert correctly."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=1.2, epa_unit="g", dha=0.3, dha_unit="g")
    payload = score_dose(product)
    # 1.5 g = 1500 mg → aha_cvd band
    assert payload["metadata"]["per_day_mid_mg"] == 1500.0
    assert payload["metadata"]["epa_dha_band_label"] == "aha_cvd"


def test_unit_mcg_converts_to_mg() -> None:
    """Labels in mcg (rare for EPA but possible) convert correctly."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=600000, epa_unit="mcg", dha=300000, dha_unit="mcg")
    payload = score_dose(product)
    # 900000 mcg = 900 mg → general_health
    assert payload["metadata"]["per_day_mid_mg"] == 900.0


def test_unit_unspecified_filtered_out() -> None:
    """Rows with 'unspecified' unit (the enricher's duplicate-with-0-qty
    pattern, e.g. Nordic) MUST be filtered out — they have 0 quantity
    anyway, but defensively don't count them even with a fake quantity."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(
        epa=650, epa_unit="mg",
        dha=450, dha_unit="mg",
        extra_ingredients=[
            # Mimics the Nordic duplicate "unspecified" row
            {"name": "Eicosapentaenoic Acid", "canonical_id": "epa",
             "quantity": 0.0, "unit": "unspecified"},
            {"name": "Docosahexaenoic Acid", "canonical_id": "dha",
             "quantity": 0.0, "unit": "unspecified"},
        ],
    )
    payload = score_dose(product)
    # Total stays 1100 mg, not inflated.
    assert payload["metadata"]["per_day_mid_mg"] == 1100.0


def test_fish_oil_parent_mass_does_not_count_as_epa_dha() -> None:
    """A 1250 mg fish_oil parent row must NOT contribute to EPA+DHA total.
    Per §9: '3000 mg fish oil is not the same as 3000 mg EPA+DHA'."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(
        epa=690, dha=310,
        extra_ingredients=[
            {"name": "Fish Oil Concentrate", "canonical_id": "fish_oil",
             "quantity": 1250, "unit": "mg"},
        ],
    )
    payload = score_dose(product)
    # Total is EPA+DHA only (1000 mg), not 1000 + 1250 = 2250.
    assert payload["metadata"]["per_day_mid_mg"] == 1000.0
    assert payload["metadata"]["epa_dha_band_label"] == "aha_cvd"


# --- Servings per day ---------------------------------------------------


def test_servings_per_day_multiplies_correctly() -> None:
    """2 servings/day × 500 mg EPA+DHA per serving = 1000 mg/day."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=300, dha=200, daily_servings=(2.0, 2.0))
    payload = score_dose(product)
    assert payload["metadata"]["per_day_mid_mg"] == 1000.0
    assert payload["metadata"]["epa_dha_band_label"] == "aha_cvd"


def test_variable_servings_uses_midpoint() -> None:
    """Label '1-2 softgels daily' → midpoint = 1.5 servings → mid dose."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=400, dha=300, daily_servings=(1.0, 2.0))
    payload = score_dose(product)
    # 700 mg/serving × midpoint 1.5 = 1050 mg/day → aha_cvd
    assert payload["metadata"]["per_day_min_mg"] == 700.0
    assert payload["metadata"]["per_day_mid_mg"] == 1050.0
    assert payload["metadata"]["per_day_max_mg"] == 1400.0


def test_missing_servings_defaults_to_one() -> None:
    """A product without servings info defaults to 1 serving/day —
    safe baseline avoiding multi-serving inflation."""
    from scoring_v4.modules.omega_dose import score_dose

    product = {
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "quantity": 300, "unit": "mg"},
        ]},
        # No servingSizes
    }
    payload = score_dose(product)
    assert payload["metadata"]["servings_defaulted"] is True
    assert payload["metadata"]["per_day_mid_mg"] == 800.0


# --- Combined EPA+DHA canonical (rare) ----------------------------------


def test_epa_dha_combined_canonical_used_when_separates_missing() -> None:
    """When a label discloses only 'EPA+DHA: 1000 mg' (canonical=epa_dha)
    and no separate EPA/DHA rows, use the combined value."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=None, dha=None, combined=1000)
    payload = score_dose(product)
    assert payload["metadata"]["epa_dha_combined_mg_per_serving"] == 1000.0
    assert payload["metadata"]["per_day_mid_mg"] == 1000.0
    assert payload["metadata"]["epa_dha_band_label"] == "aha_cvd"


def test_epa_dha_combined_does_not_double_count_with_separates() -> None:
    """If both 'EPA: 500', 'DHA: 200', AND 'EPA+DHA: 700' are disclosed,
    do NOT additively count them as 1400. Take max(separates, combined)."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=500, dha=200, combined=700)
    payload = score_dose(product)
    # max(500+200, 700) = 700, not 1400.
    assert payload["metadata"]["per_day_mid_mg"] == 700.0


# --- Score ceiling -----------------------------------------------------


def test_max_dose_score_is_25_at_prescription_band_with_in_range_ratio() -> None:
    """Max Dose: prescription_dose (20) + ratio_sanity (5) = 25."""
    from scoring_v4.modules.omega_dose import score_dose

    product = _omega_product(epa=2500, dha=2000)  # 4500 mg/day, ratio 1.25
    payload = score_dose(product)
    assert payload["score"] == 25.0


def test_dose_cap_25() -> None:
    from scoring_v4.modules.omega_dose import score_dose, CAP_DOSE

    assert CAP_DOSE == 25.0


# --- Real canary integration ---------------------------------------------


_CANARY_DOSE_IDS = {"327776", "326270", "288740", "273630", "239592", "182968"}
_canary_cache = None


def _load_canaries(ids):
    """Load ALL Dose canary IDs in one catalog scan on first call.
    Same pattern as test_v4_omega_canary_diversity_p161 — avoids re-scanning
    per parametrize iteration (~6GB catalog × N tests would be brutal)."""
    global _canary_cache
    if _canary_cache is not None:
        return {did: _canary_cache[did] for did in ids if did in _canary_cache}
    enriched_root = SCRIPTS_ROOT / "products"
    if not enriched_root.exists():
        _canary_cache = {}
        pytest.skip("no enriched products dir in this checkout")
    # Load ALL canary IDs, not just the request set, so subsequent
    # parametrize cases hit the cache.
    target = _CANARY_DOSE_IDS
    found = {}
    for path in enriched_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else (data.get("products") or data.get("items") or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            did = str(item.get("dsld_id") or item.get("id") or "")
            if did in target:
                found[did] = item
        if len(found) == len(target):
            break
    _canary_cache = found
    return {did: _canary_cache[did] for did in ids if did in _canary_cache}


@pytest.mark.parametrize("dsld_id,expected_score,expected_band", [
    ("327776", 21.0, "aha_cvd"),    # Sports Research: EPA 690 + DHA 310 = 1000 mg
    ("326270", 21.0, "aha_cvd"),    # Sports Research alt SKU: same EPA/DHA
    ("288740", 21.0, "aha_cvd"),    # Nordic Ultimate Omega + CoQ10: 1100 mg
    ("273630", 21.0, "aha_cvd"),    # Garden of Life Advanced Omega: 1160 mg
    ("239592", 5.0, "below_efsa_ai"),  # CVS Krill 350: only 74 mg/day
    ("182968", 5.0, "below_efsa_ai"),  # Pure Encap Krill-Plex: only 240 mg/day
])
def test_canary_dose_scores(dsld_id, expected_score, expected_band):
    """Real-catalog dose scoring lock — protects against silent regressions
    on the 6 anchor canaries from P1.6.1."""
    from scoring_v4.modules.omega_dose import score_dose

    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"canary {dsld_id} not in enriched catalog")

    payload = score_dose(canaries[dsld_id])
    assert payload["score"] == expected_score, (
        f"canary {dsld_id} Dose score {payload['score']} != {expected_score}"
    )
    assert payload["metadata"]["epa_dha_band_label"] == expected_band


# --- Orchestrator roll-forward ------------------------------------------


def test_omega_orchestrator_phase_rolls_forward_to_p162() -> None:
    """After P1.6.2 lands, module-level phase marker advances."""
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega({
        "product_name": "Fish Oil",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "quantity": 300, "unit": "mg"},
        ]},
    }).to_breakdown()
    assert breakdown["phase"].startswith("P1.6.")


def test_omega_dose_dimension_score_populated_in_breakdown() -> None:
    """After P1.6.2 lands, the dose dimension in score_omega's breakdown
    carries a numeric score. evidence/trust/transparency stay None until
    their slices ship."""
    from scoring_v4.modules.omega import score_omega

    product = {
        "product_name": "Fish Oil",
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "quantity": 300, "unit": "mg"},
        ]},
    }
    breakdown = score_omega(product).to_breakdown()
    assert breakdown["dimensions"]["dose"]["score"] is not None
    assert breakdown["dimensions"]["dose"]["score"] > 0


# --- Architecture lock --------------------------------------------------


def test_omega_dose_does_not_import_v3_scorer() -> None:
    """§13 architecture lock — AST-based check."""
    import ast
    import scoring_v4.modules.omega_dose as od

    tree = ast.parse(Path(od.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith("score_supplements"), (
                f"v4→v3 import: from {module_name}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("score_supplements"), (
                    f"v4→v3 import: import {alias.name}"
                )


# --- Config-as-truth ----------------------------------------------------


def test_dose_weights_match_rubric_config() -> None:
    """Code reads bands from omega_rubric.json — config is the source
    of truth. Test confirms loader sees the right values."""
    from scoring_v4.modules.omega_dose import _load_rubric

    rubric = _load_rubric()
    bands = rubric["dose"]["epa_dha_bands"]

    # Thresholds in descending order
    thresholds = [b["min_mg_day"] for b in bands]
    assert thresholds == [4000, 2000, 1000, 500, 250, 0]

    # Scores at boundaries
    assert bands[0]["score"] == 20  # prescription
    assert bands[2]["score"] == 16  # aha_cvd
    assert bands[-1]["score"] == 0  # below_efsa_ai

    # Ratio sanity
    rs = rubric["dose"]["ratio_sanity"]
    assert rs["score"] == 5
    assert rs["min_ratio"] == pytest.approx(0.333, abs=0.001)
    assert rs["max_ratio"] == 3.0
    assert rs["exempt_when_one_zero"] is True
