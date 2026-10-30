"""v4 cross-module canary diversity for completed scoring modules.

Omega has its own P1.6 canary file. This file covers the completed
generic and probiotic modules against real enriched catalog rows so we
catch class-specific regressions that synthetic unit fixtures miss:

- generic mid / low score bands
- generic non-evaluable Dose rescaling
- generic high Trust and zero Trust cases
- sports high score band
- probiotic high / mid / low score bands
- probiotic per-strain CFU disclosed vs aggregate-CFU-only capped proxy dose
- probiotic Trust positive vs Trust zero
- prenatal probiotic routing stays probiotic, not multi_or_prenatal

Tests scan the enriched catalog once and cache the selected rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from test_probiotic_identity_completeness import _disclosure_points


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# NOTE: Phase 4 (Trust→Verification Bonus) lowered verified-product scores as
# the 15-pt trust dimension became a ≤8 additive bonus and the hidden 85→100
# renormalization was removed. These ranges are the Phase-4 interim values and
# will be revisited when Phase 9 recalibrates the final scale.
GENERIC_CANARIES = {
    # Recent cert override / high verification path (Phase 4: 79 → 74.5).
    # Phase 7 (_mass_mg Gram(s) fix): Meriva curcumin is dosed "1 Gram(s)" =
    # 1000 mg; previously mis-read as 1 mg (below-range dose), now correctly
    # within the studied range -> dose 21, score 69-71 -> 78.2. A premium
    # clinically-studied branded extract scoring closer to its merit.
    "328825": {
        "label": "Thorne Curcumin Phytosome 1000 mg",
        # Native module rubric, not the final six-pillar export. The label's
        # 1 g complex and two daily servings mean 2,000 mg/day. Meriva/phytosome
        # is already the form; independent-delivery policy removes the duplicate 3.
        # V4.1 Step 4: the profile keeps only the neutral identity (7.2); the
        # printed amount is a Transparency fact. Since d2d4128c9 there is no
        # studied curcumin window, so Dose is the shared neutral (11.97 raw).
        # a78f78bf9 (Oct 28, Dr Pham's signed held-source rulings): the Meriva
        # record's sources are held, so Evidence 14 -> 0 and 59.2 -> 45.2
        # (re-pinned 2026-10-30 from a frozen raw replay at each commit).
        "score_range": (45.2, 45.2),
        "traits": {
            "trust_high": True,
            "dimension_scores": {
                # d2d4128c9 (Oct 18) restates Dose on the shared reference: 12.0 -> 11.97.
                "formulation": 7.2, "dose": 11.97,
                "evidence": 0.0, "transparency": 10.0,
            },
            # d2d4128c9: curcumin_from_turmeric is a completed no-benchmark
            # assessment (DOSE_V41_REFERENCE_DECISIONS: Meriva/BCM95/Longvida and
            # native curcumin are not interchangeable; no cited 500-1000 mg window).
            "botanical_dose": {"benchmark": "absent"},
            "botanical_dose_band": "disclosed_no_reference",
        },
    },
    # Disclosed but unbenchmarked purpose: gets limited-assessability fallback,
    # but weak formulation/evidence keeps the product in the low generic band.
    # Replaced vitafusion Fiber Gummies after the dedicated fiber module made
    # that product correctly route to fiber_digestive.
    "251998": {
        "label": "Nature's Way DHEA-25 mg",
        # V4.1 Step 4: the unbenchmarked purpose takes the shared 11.4-public
        # neutral (12.54 raw on reference 22, was 16), and formula checks own
        # the additive findings Formulation used to charge.
        "score_range": (44.7, 44.7),
        "traits": {"dose_partial_no_rda": True, "trust_positive": True},
    },
    # False-positive guard from omega routing: liposomal delivery/lecithin
    # stays generic even though fatty-acid-like carrier signals exist.
    "184661": {
        "label": "Pure Encapsulations Liposomal Glutathione",
        # Phase 4: 65 → 63. Phase 8: Setria glutathione (mass-primary) evidenced,
        # but positive_weak effect -> floor 14*0.85=11.9 -> 64.8.
        # Re-baseline 2026-07-19: committed generic calibration drift (~+1.3).
        # Mass-bearing sole active, so the pending mass-less evidence-floor change
        # is inert here.
        # d2d4128c9 (Oct 18, approved source-qualified reference policy): no
        # source-qualified glutathione reference, so Dose takes the neutral
        # (22 -> 12.54): 54.7 -> 45.3. cf5ec623f (Oct 28): its held Setria
        # relationship earns no Evidence (9.35 -> 0): 45.3 -> 35.9.
        "score_range": (35.9, 35.9),
        "traits": {},
    },
}


SPORTS_CANARIES = {
    # High sports scorer after the P1.7 sports module split.
    "325587": {
        "label": "Transparent Labs Creatine HMB",
        # BioPerine remains A4=3, not also A3=3. The approved HMB parent
        # ceiling changes A1 10.9821→11.25; native79.25 rounds to79.2.
        # V4.1 Step 4: the +1 stack-support presence credit is retired.
        # Dose V4.1: creatine and HMB are both named co-primaries and average
        # (creatine 20, HMB below its 3 g band 16 -> Dose 18).
        # d2d4128c9 (Oct 18, source-qualified references): creatine 20 and HMB
        # 10 average to Dose 15: 76.2 -> 73.2. 37d74d5b1 (Oct 28): the
        # near-perfect Evidence floor needs a replicated reviewed body (18 -> 14): 69.2.
        "score_range": (69.2, 69.2),
        "traits": {"trust_positive": True,
                   "dimension_scores": {"formulation": 14.25, "dose": 15.0},
                   "form_components": {"A1_bio_score": 11.25, "A3_delivery_system": 0.0,
                                       "A4_absorption_enhancer": 3.0}},
    },
}


PROBIOTIC_CANARIES = {
    # Sep-08 reviewed re-lock: direct module scores, not the final six-pillar
    # export totals. Contextual evidence is not strain-dose applicability.
    "306247": {
        "label": "Thorne FloraSport 20B",
        # DE111/HN019 reviewed native outcomes do not establish benefit here;
        # the other two source identities lack exact registered strain codes.
        # V4.1 Step 4: canonical Formulation (unrated strains, neutral 9) and
        # Dose as measured adequacy only (per-strain disclosure is Transparency's).
        # Dose V4.1: the four strains average; the two without a strain
        # benchmark take the neutral (5.0 -> 6.78).
        # d2d4128c9 (Oct 18): no general strain benchmark is a completed
        # assessment, so every strain takes the neutral (6.78 -> 8.55): 45.8 -> 47.5.
        "score_range": (47.5, 47.5),
        "traits": {"trust_positive": True,
                   "dimension_scores": {"formulation": 9.0, "dose": 8.55, "evidence": 0.0, "transparency": 15.0},
                   "identity_counts": (2, 4), "evidence_state": "evaluated_null"},
    },
    # Low end of current probiotic score distribution.
    "201158": {
        "label": "OLLY Kids Quick Melt Probiotic Sticks",
        # V4.1 Step 4: its total CFU is a recorded label limit. Dose V4.1: the
        # hidden per-strain amounts take the neutral (Dose 0 -> 8.55 raw).
        "score_range": (52.6, 52.6),
        "traits": {"trust_positive": True},
    },
    # Aggregate-CFU-only canary: the total is recorded as a label limit with no
    # Dose credit (V4.1 Step 4), never an invented per-strain allocation.
    "178346": {
        "label": "Spring Valley Advanced Strength Probiotic 50B",
        # Ten species and no owned strain doses. Formulation is the shared
        # unrated neutral (9); the old disclosure-based Formulation and the
        # 2-point aggregate floor are retired, so the module total rises.
        # Dose V4.1: the hidden per-strain amounts take the neutral (0 -> 8.55).
        "score_range": (33.5, 33.5),
        "traits": {
            "aggregate_cfu_proxy": True,
            "no_independent_delivery": True,
            "trust_zero": True,
            "dose_score": 8.55,
            "aggregate_proxy_detail": {
                "total_strain_count": 10,
                "cfu_guarantee_reason": "cfu_guarantee_not_disclosed",
            },
        },
    },
    # Per-strain CFU disclosed path; Dose > 0 with no Trust credit.
    "286725": {
        "label": "vitafusion Probiotic 5B",
        # V4.1 Step 4: measured adequacy (5) stays; per-strain disclosure moves
        # to Transparency and Formulation is the unrated neutral.
        # Dose V4.1: strains without a benchmark join the average at the
        # neutral (5.0 -> 6.78). d2d4128c9 (Oct 18): with no general strain
        # benchmark every strain takes the neutral (6.78 -> 8.55): 36.3 -> 38.0.
        "score_range": (38.0, 38.0),
        "traits": {"dose_positive": True, "trust_zero": True, "no_independent_delivery": True},
    },
    # Per-strain CFU + positive Trust path.
    "184730": {
        "label": "Pure Encapsulations Probiotic 123",
        # Alternative serving headers retain one source-owned pure blend.
        # Its 2.25B total is disclosed; individual strain quantities are not.
        # The CFU disclosure component owns that limitation, without a second B5.
        # V4.1 (Oct 15, 2026): its reviewed research does not apply to this
        # product, so the former 10 certainty points are gated to 0.
        # Dose V4.1 (plan section 2.3/3.2): its three strains' amounts are hidden,
        # so each takes the shared neutral (8.55 raw = 11.4 public) instead of
        # 0; Transparency keeps the disclosure consequence. Formulation is the
        # unrated neutral.
        "score_range": (38.8, 38.8),
        "traits": {"dose_positive": True, "trust_positive": True,
                   "dimension_scores": {"formulation": 9.0, "dose": 8.55, "evidence": 0.0, "transparency": 11.0},
                   "identity_counts": (3, 3),
                   "evidence_state": "research_present_applicability_unestablished"},
    },
    # Prenatal name must stay probiotic because supplement_type wins.
    "76803": {
        "label": "GNC Probiotic Solutions Prenatal 20B",
        # LGG has contextual evidence, but undisclosed per-strain CFU cannot
        # establish its studied dose. V4.1 Step 4: the total is a recorded label
        # limit with no Dose credit (the named-strain floor is retired).
        # V4.1 (Oct 15, 2026): LGG certainty without applicability no longer
        # earns its 6.67 Evidence points.
        # Dose V4.1: the hidden per-strain amounts take the neutral (0 -> 8.55).
        "score_range": (37.6, 37.6),
        "traits": {
            "prenatal_name_routes_probiotic": True,
            "trust_positive": True,
            "dose_score": 8.55,
            "aggregate_proxy_detail": {
                "total_strain_count": 2,
                # The label reads "Guaranteed potency through expiration date"
                # (read correctly since the 2026-09-16 guarantee fix).
                "cfu_guarantee_reason": "cfu_guaranteed_through_expiration",
            },
        },
    },
    "PG_SUB_35E0BD3374BF494B80FEABE87FC559E7": {
        "label": "Seed DS-01 Daily Synbiotic",
        # V4.1 Step 4: Formulation is canonical strain form quality (unrated
        # strains keep the neutral 9; a rated co-ingredient no longer supplies
        # it) without the former studied-formula identity/potency credits.
        "score_range": (68.6, 68.6),
        "traits": {"studied_formula_afu": True, "dose_score": 25.0},
    },
}


ALL_CANARY_IDS = set(GENERIC_CANARIES) | set(SPORTS_CANARIES) | set(PROBIOTIC_CANARIES)
_CANARY_CACHE: dict[str, dict] | None = None


def _load_canaries() -> dict[str, dict]:
    global _CANARY_CACHE
    if _CANARY_CACHE is not None:
        return _CANARY_CACHE

    enriched_root = SCRIPTS_ROOT / "products"
    if not enriched_root.exists():
        _CANARY_CACHE = {}
        pytest.skip("no enriched products directory in this checkout")

    found: dict[str, dict] = {}
    for path in enriched_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("products") or data.get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            dsld_id = str(item.get("dsld_id") or item.get("id") or "")
            if dsld_id in ALL_CANARY_IDS:
                found[dsld_id] = item
        if len(found) == len(ALL_CANARY_IDS):
            break

    _CANARY_CACHE = found
    return found


def _dimension_score(breakdown: dict, dimension: str):
    return breakdown["dimensions"][dimension]["score"]


def _verification_strength(breakdown: dict) -> float:
    """Verification on the 0-15 trust scale regardless of module generation.
    Phase-4 modules emit a verification_bonus (0-8, rescaled back to 0-15 here);
    not-yet-migrated modules still emit the legacy 0-15 trust dimension."""
    bonus = breakdown.get("verification_bonus")
    if bonus:
        return float(bonus.get("score") or 0.0) * 15.0 / 8.0
    trust = breakdown.get("dimensions", {}).get("trust", {})
    return float(trust.get("score") or 0.0)


def _require_strict_v4_contract(product: dict, label: str) -> None:
    from scoring_input_contract import get_scoring_ingredients

    scoring_input = get_scoring_ingredients(product, strict=True)
    if not scoring_input.rows:
        pytest.skip(
            f"{label} enriched artifact lacks strict v4 scoring inputs "
            f"({scoring_input.zero_scorable_reason}); rerun enrichment before using as canary"
        )


@pytest.mark.parametrize("dsld_id,expected", list(GENERIC_CANARIES.items()))
def test_generic_real_catalog_canary_score_and_traits(dsld_id: str, expected: dict) -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.generic import score_generic
    from scoring_v4.router import class_for_product

    product = _load_canaries().get(dsld_id)
    if not product:
        pytest.skip(f"generic canary {dsld_id} not found: {expected['label']}")
    _require_strict_v4_contract(product, expected["label"])

    assert class_for_product(product) == "generic"
    gate = evaluate_completeness_gate(product, "generic")
    assert gate.is_live_eligible, gate.missing_fields

    breakdown = score_generic(product).to_breakdown()
    score = breakdown["score_100"]
    lo, hi = expected["score_range"]
    assert lo <= score <= hi, (expected["label"], score, breakdown)

    traits = expected["traits"]
    for dimension, points in traits.get("dimension_scores", {}).items():
        assert _dimension_score(breakdown, dimension) == pytest.approx(points)
    if "botanical_dose" in traits:
        dose_metadata = breakdown["dimensions"]["dose"]["metadata"]
        assert dose_metadata["botanical_dose"] == traits["botanical_dose"]
        assert dose_metadata["botanical_dose_band"] == traits["botanical_dose_band"]
    if traits.get("dose_none"):
        assert _dimension_score(breakdown, "dose") is None
    if traits.get("dose_partial_no_rda"):
        # The shared unbenchmarked neutral on the generic reference 22.
        assert _dimension_score(breakdown, "dose") == 12.54
        assert (
            breakdown["dimensions"]["dose"]["metadata"]["window_proxy_status"]
            == "limited_assessability_unbenchmarked_purpose"
        )
    if traits.get("trust_zero"):
        assert _verification_strength(breakdown) == 0
    if traits.get("trust_positive"):
        assert _verification_strength(breakdown) > 0
    if traits.get("trust_high"):
        assert _verification_strength(breakdown) >= 10
    if traits.get("transparency_low"):
        assert _dimension_score(breakdown, "transparency") <= 2


@pytest.mark.parametrize("dsld_id,expected", list(SPORTS_CANARIES.items()))
def test_sports_real_catalog_canary_score_and_traits(dsld_id: str, expected: dict) -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.sports import score_sports
    from scoring_v4.router import class_for_product

    product = _load_canaries().get(dsld_id)
    if not product:
        pytest.skip(f"sports canary {dsld_id} not found: {expected['label']}")
    _require_strict_v4_contract(product, expected["label"])

    assert class_for_product(product) == "sports"
    gate = evaluate_completeness_gate(product, "sports")
    assert gate.is_live_eligible, gate.missing_fields

    breakdown = score_sports(product).to_breakdown()
    score = breakdown["score_100"]
    lo, hi = expected["score_range"]
    assert lo <= score <= hi, (expected["label"], score, breakdown)

    traits = expected["traits"]
    for name, value in traits.get("dimension_scores", {}).items():
        assert _dimension_score(breakdown, name) == pytest.approx(value)
    for name, value in traits.get("form_components", {}).items():
        assert breakdown["dimensions"]["formulation"]["components"][name] == pytest.approx(value)
    if traits.get("dose_max"):
        # re-baseline 2026-06-06: TL Creatine HMB sports dose 20 -> 21; V4.1
        # Step 4 retired the +1 stack support, so the full primary dose is 20.
        assert _dimension_score(breakdown, "dose") == 20
    if traits.get("trust_positive"):
        assert _verification_strength(breakdown) > 0


@pytest.mark.parametrize("dsld_id,expected", list(PROBIOTIC_CANARIES.items()))
def test_probiotic_real_catalog_canary_score_and_traits(dsld_id: str, expected: dict) -> None:
    from scoring_v4.gate_completeness import evaluate_completeness_gate
    from scoring_v4.modules.probiotic import score_probiotic
    from scoring_v4.router import class_for_product

    product = _load_canaries().get(dsld_id)
    if not product:
        pytest.skip(f"probiotic canary {dsld_id} not found: {expected['label']}")
    _require_strict_v4_contract(product, expected["label"])

    assert class_for_product(product) == "probiotic"
    gate = evaluate_completeness_gate(product, "probiotic")
    assert gate.is_live_eligible, gate.missing_fields

    breakdown = score_probiotic(product).to_breakdown()
    score = breakdown["score_100"]
    lo, hi = expected["score_range"]
    assert lo <= score <= hi, (expected["label"], score, breakdown)

    traits = expected["traits"]
    if traits.get("no_independent_delivery"):
        form = breakdown["dimensions"]["formulation"]
        assert form["components"]["A3_delivery_system"] == 0.0
        assert form["metadata"]["delivery_data"]["systems"] == []
    for dimension, value in traits.get("dimension_scores", {}).items():
        assert _dimension_score(breakdown, dimension) == pytest.approx(value)
    if "identity_counts" in traits:
        metadata = breakdown["dimensions"]["formulation"]["metadata"]
        assert (metadata["identified_strain_count"], metadata["total_strain_count"]) == traits["identity_counts"]
    if "evidence_state" in traits:
        assert breakdown["dimensions"]["evidence"]["metadata"]["evidence_result_state"] == traits["evidence_state"]
    if traits.get("form_max"):
        assert _dimension_score(breakdown, "formulation") == 25
    if traits.get("dose_zero"):
        assert _dimension_score(breakdown, "dose") == 0
    if traits.get("dose_positive"):
        assert _dimension_score(breakdown, "dose") > 0
    if "dose_score" in traits:
        dose = breakdown["dimensions"]["dose"]
        assert dose["score"] == pytest.approx(traits["dose_score"]), (
            expected["label"], dose,
        )
    if "aggregate_proxy_detail" in traits:
        # Aggregate disclosure is not a per-strain adequacy estimate: V4.1
        # Step 4 records it as a label limit. Dose V4.1 section 2.3: the
        # hidden per-strain amounts take the shared neutral, never an
        # allocation of the total.
        want = traits["aggregate_proxy_detail"]
        meta = breakdown["dimensions"]["dose"]["metadata"]
        proxy = meta["aggregate_cfu_proxy"]
        assert proxy["applied"] is True
        assert proxy["reason"] == "aggregate_cfu_label_presence"
        assert not {"score", "floor", "cap", "contributions"} & set(proxy)
        assert meta["total_strain_count"] == want["total_strain_count"]
        assert meta["per_strain_cfu_disclosed_count"] == 0
        assert meta["cfu_adequacy_basis"] == "aggregate_cfu_disclosed_only"
        # d2d4128c9 (Oct 18): no general strain benchmark is a completed result.
        assert meta["reference_basis"] == "completed_no_general_strain_benchmark"
        guarantee = meta["cfu_guarantee"]
        assert guarantee["reason"] == want["cfu_guarantee_reason"]
        assert guarantee["applied"] is False  # nothing measured to discount
        dose = breakdown["dimensions"]["dose"]
        assert dose["score"] == pytest.approx(8.55)
        assert meta["strain_measured_count"] == 0
        assert _disclosure_points(dose) == 0.0
        assert dose["metadata"]["window_proxy_reason"] == "aggregate_cfu_not_per_strain"
    if traits.get("studied_formula_afu"):
        meta = breakdown["dimensions"]["dose"]["metadata"]
        assert meta["assessment_status"] == "assessed_studied_formula"
        assert meta["dose_adequacy_basis"] == "studied_formula_native_afu"
        formula = meta["studied_formula_assessment"]
        assert formula["evidence_id"] == "FORMULA_SEED_DS01"
        assert formula["daily_dose"] == {"value": 53_600_000_000.0, "unit": "AFU"}
        assert meta["per_strain_cfu_disclosed_count"] == 0
        assert meta["window_proxy_reason"] == "formula_dose_not_individual_strain_doses"
    if traits.get("trust_zero"):
        assert _verification_strength(breakdown) == 0
    if traits.get("trust_positive"):
        assert _verification_strength(breakdown) > 0


def test_cross_module_canary_count_floor() -> None:
    assert len(GENERIC_CANARIES) >= 3
    assert len(SPORTS_CANARIES) >= 1
    assert len(PROBIOTIC_CANARIES) >= 6


def test_cross_module_canaries_cover_expected_score_bands() -> None:
    generic_ranges = [v["score_range"] for v in GENERIC_CANARIES.values()]
    sports_ranges = [v["score_range"] for v in SPORTS_CANARIES.values()]
    probiotic_ranges = [v["score_range"] for v in PROBIOTIC_CANARIES.values()]

    assert any(hi <= 55 for _lo, hi in generic_ranges), "missing weak generic canary"
    assert any(lo >= 65 for lo, _hi in sports_ranges), "missing high sports canary"
    assert any(hi <= 55 for _lo, hi in probiotic_ranges), "missing weak probiotic canary"
    assert any(lo >= 65 for lo, _hi in probiotic_ranges), "missing high probiotic canary"


def test_merged_serving_canary_from_frozen_raw_label(monkeypatch):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((Path(__file__).parent / "fixtures/serving_column_184730_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    monkeypatch.setattr(sys.modules[__name__], "_CANARY_CACHE", {"184730": enriched})
    test_probiotic_real_catalog_canary_score_and_traits("184730", PROBIOTIC_CANARIES["184730"])
