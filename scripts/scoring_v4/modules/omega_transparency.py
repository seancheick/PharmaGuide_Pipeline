"""v4 Omega Transparency dimension — P1.6.5.

Scores omega-3 Transparency against the 15-point rubric in
omega_rubric.json:

    Positive components (omega-specific):
      - epa_or_dha_disclosed   5  (at least one EPA or DHA labeled with
                                   positive mg quantity AND valid unit;
                                   reuses the omega completeness-gate logic)
      - form_disclosed         3  (TG / rTG / EE / PL explicit; reuses
                                   omega_formulation._detect_form)
      - source_disclosed       3  (fish / krill / algae / cod liver /
                                   species named; reuses
                                   omega_formulation._source_disclosed)
      - oxidation_disclosed    2  (TOTOX / peroxide / anisidine values
                                   labeled — usually 0 today; future-ready
                                   for when lot-test scrapers populate)
      - b3_claim_compliance    up to +4 (allergen_free / gluten_free /
                                  vegan reused from generic_transparency)

    Penalties (reused from generic_transparency):
      - b2_false_allergen_free_claim up to -2
      - b5_opacity (class-aware)     up to -5
        (omega defaults to the 'generic' B5 class so the standard
         opacity multiplier applies; not the probiotic 0.4x)
      - b6_marketing / disease claim -5

  Hard-clamped at dimension_cap = 15.

Max positive reachable: 5 + 3 + 3 + 2 + 4 = 17, capped at 15. The
2-point headroom over the cap means a product with full B3 +
disclosure ALSO needs minor B2/B5/B6 penalties to actually hit 15
naturally — or the cap clamps. This is intentional discipline so a
perfect Transparency score requires both disclosure AND clean labels.

Per §13 architecture lock — no v3 imports. Reuses v4 omega_formulation
helpers (form/source detection) and v4 generic_transparency helpers
(penalty machinery + B3) — all v4-only.
"""

from __future__ import annotations

from typing import Any, Dict, List

from scoring_v4.modules.generic_helpers import get_active_ingredients
from scoring_v4.modules.generic_transparency import (
    _derive_claim_validations,
    _score_b2_false_allergen_claim_penalty,
    _score_b3_claim_compliance,
    _score_b5_proprietary_blend_penalty,
    _score_b6_disease_claim_penalty,
)
from scoring_v4.modules.omega_formulation import (
    _detect_form,
    _epa_dha_and_oil_mass_mg,
    _source_disclosed,
    _verified_quality_programs,
)


PHASE_MARKER = "P1.6.5_omega_transparency"
CAP_TRANSPARENCY = 15.0
DATA_LIMITED_TRANSPARENCY_FLOOR = 12.0
DATA_LIMITED_TRANSPARENCY_MIN_EPA_DHA_MG = 750.0


# Oxidation-signal keys checked on the product blob. Future-ready: when
# lot-test scrapers add these, the credit fires automatically.
_OXIDATION_TOP_LEVEL_KEYS = (
    "oxidation_data",
    "totox",
    "totox_value",
    "peroxide_value",
    "anisidine_value",
    "lot_oxidation",
    "lot_test_data",
)


def _load_rubric() -> Dict[str, Any]:
    from scoring_v4.config_registry import load_rubric
    return load_rubric("omega")  # Phase 0: shared registry (validated + fingerprinted)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


_VALID_UNITS = {"mg", "milligram", "milligrams", "g", "gram", "grams", "gram(s)",
                "mcg", "ug", "µg", "microgram", "micrograms"}
_OMEGA_CANONICALS = {"epa", "dha", "epa_dha"}


def _epa_or_dha_disclosed(product: Dict[str, Any]) -> bool:
    """At least one EPA/DHA/EPA+DHA ingredient with positive quantity AND
    valid unit. Mirrors the omega completeness-gate logic — single
    'is this product actually disclosing EPA/DHA?' check across the
    module."""
    for ing in get_active_ingredients(product):
        if not isinstance(ing, dict):
            continue
        canon = _norm(ing.get("canonical_id"))
        if canon not in _OMEGA_CANONICALS:
            continue
        unit = _norm(ing.get("unit") or ing.get("unit_normalized") or ing.get("normalized_unit"))
        if unit not in _VALID_UNITS:
            continue
        for qty_key in ("quantity", "amount", "dose", "dosage"):
            try:
                q = float(ing.get(qty_key))
                if q > 0:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def _oxidation_disclosed(product: Dict[str, Any]) -> bool:
    """True when the enriched blob contains lot-level oxidation/TOTOX/
    peroxide/anisidine values. Today this is almost always False
    (DSLD labels rarely surface lot test values). Future-ready for
    when IFOS lot reports or other scrapers populate these fields."""
    # 1. Top-level oxidation keys (any non-empty value counts)
    for key in _OXIDATION_TOP_LEVEL_KEYS:
        value = product.get(key)
        if value:
            if isinstance(value, dict) and not value:
                continue
            if isinstance(value, (list, str)) and not value:
                continue
            return True

    # 2. certification_data.oxidation_data / .lot_test_data
    cert_data = _safe_dict(product.get("certification_data"))
    for key in ("oxidation_data", "lot_test_data", "totox", "peroxide_value"):
        value = cert_data.get(key)
        if value:
            return True

    # 3. evidence_based programs with oxidation/TOTOX in the rule_id or
    #    display_name (future scrapers may emit TOTOX as a rules_db program)
    evidence = _safe_dict(cert_data.get("evidence_based"))
    for program in _safe_list(evidence.get("third_party_programs")):
        if not isinstance(program, dict):
            continue
        rid = _norm(program.get("rule_id"))
        name = _norm(program.get("display_name"))
        if "totox" in rid or "peroxide" in rid or "oxidation" in rid:
            return True
        if "totox" in name or "peroxide" in name or "oxidation" in name:
            return True

    return False


def score_transparency(product: Any) -> Dict[str, Any]:
    """Score omega-class Transparency dimension."""
    if not isinstance(product, dict):
        product = {}

    rubric = _load_rubric()
    t_cfg = rubric["transparency"]
    epa_dha_pts = float(t_cfg.get("epa_or_dha_disclosed", 5) or 5)
    form_pts = float(t_cfg.get("form_disclosed", 3) or 3)
    source_pts = float(t_cfg.get("source_disclosed", 3) or 3)
    oxidation_pts = float(_safe_dict(t_cfg.get("oxidation_disclosed")).get("score", 2) or 2)
    b3_cap = float(_safe_dict(t_cfg.get("b3_claim_compliance")).get("cap", 4) or 4)

    flags: List[str] = []

    # Positive components
    components: Dict[str, float] = {}
    if _epa_or_dha_disclosed(product):
        components["epa_or_dha_disclosed"] = epa_dha_pts
    if _detect_form(product) != "undefined":
        components["form_disclosed"] = form_pts
    if _source_disclosed(product):
        components["source_disclosed"] = source_pts
    if _oxidation_disclosed(product):
        components["oxidation_disclosed"] = oxidation_pts

    # B3 reused from generic — produces 0..4 based on allergen_free /
    # gluten_free / vegan validations.
    b2_for_validations, b2_meta = _score_b2_false_allergen_claim_penalty(product)
    allergen_valid, gluten_valid, vegan_valid, claim_flags = _derive_claim_validations(
        product, b2_for_validations
    )
    flags.extend(claim_flags)
    b3 = _score_b3_claim_compliance(
        allergen_free=allergen_valid,
        gluten_free=gluten_valid,
        vegan_or_vegetarian=vegan_valid,
    )
    b3_capped = min(b3, b3_cap)
    if b3_capped > 0:
        components["b3_claim_compliance"] = round(b3_capped, 2)

    # Penalties reused from generic_transparency. B5 will detect omega
    # products as the 'generic' B5 class (since omega isn't in the
    # probiotic/multi/sports_active routes); the standard 1.0x multiplier
    # applies.
    b2_penalty = b2_for_validations  # already non-negative magnitude
    b5_penalty, b5_evidence = _score_b5_proprietary_blend_penalty(product, flags)
    b6_penalty = _score_b6_disease_claim_penalty(product, flags)

    penalties: Dict[str, float] = {}
    if b2_penalty > 0:
        penalties["b2_false_allergen_free_claim"] = -round(b2_penalty, 4)
    if b5_penalty > 0:
        penalties["b5_proprietary_blend_opacity"] = -round(b5_penalty, 4)
    if b6_penalty > 0:
        penalties["b6_marketing_claims"] = -round(b6_penalty, 4)

    positive_total = sum(components.values())
    penalty_total = sum(abs(v) for v in penalties.values())
    raw_total = positive_total - penalty_total
    data_limited_floor = _data_limited_transparency_floor(product, raw_total, components)
    if data_limited_floor["applied"]:
        adjustment = round(float(data_limited_floor["adjustment"]), 4)
        components["data_limited_transparency_floor"] = adjustment
        positive_total = sum(components.values())
        raw_total = positive_total - penalty_total
    score = max(0.0, min(CAP_TRANSPARENCY, raw_total))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_total, 4),
        "positive_total": round(positive_total, 4),
        "penalty_total": round(penalty_total, 4),
        "cap_applied": raw_total > CAP_TRANSPARENCY,
        "floor_applied": raw_total < 0.0,
        "claim_validations": {
            "allergen_free": bool(allergen_valid),
            "gluten_free": bool(gluten_valid),
            "vegan_or_vegetarian": bool(vegan_valid),
        },
        "flags": sorted(set(flags)),
        "b2_seen_allergens": b2_meta.get("seen_allergens", {}),
        "b5_blend_count": len(b5_evidence),
        "data_limited_transparency_floor_applied": bool(data_limited_floor["applied"]),
        "data_limited_transparency_floor": data_limited_floor,
    }

    return {
        "score": round(score, 2),
        "max": CAP_TRANSPARENCY,
        "components": components,
        "penalties": penalties,
        "metadata": metadata,
    }


def _data_limited_transparency_floor(
    product: Dict[str, Any],
    raw_total: float,
    components: Dict[str, float],
) -> Dict[str, Any]:
    """Floor transparency for verified, high-disclosure omega products.

    A product with itemized EPA/DHA, named source, high EPA+DHA dose, and
    third-party quality verification has disclosed the consumer-critical omega
    facts. Missing molecular form / lot oxidation remains a data limitation, so
    it cannot reach full transparency, but it should not sit at 9/15 beside
    commodity labels. This is deliberately gated by the same quality-program
    evidence used by the formulation data-limited floor.
    """
    masses = _epa_dha_and_oil_mass_mg(product)
    quality_programs = _verified_quality_programs(product)
    payload: Dict[str, Any] = {
        "applied": False,
        "floor": DATA_LIMITED_TRANSPARENCY_FLOOR,
        "min_epa_dha_mg": DATA_LIMITED_TRANSPARENCY_MIN_EPA_DHA_MG,
        "epa_dha_mg": round(masses["epa_dha_mg"], 4),
        "quality_programs": quality_programs,
    }
    if (
        _detect_form(product) == "undefined"
        and "epa_or_dha_disclosed" in components
        and "source_disclosed" in components
        and masses["epa_dha_mg"] >= DATA_LIMITED_TRANSPARENCY_MIN_EPA_DHA_MG
        and quality_programs
        and raw_total < DATA_LIMITED_TRANSPARENCY_FLOOR
    ):
        payload["applied"] = True
        payload["adjustment"] = round(DATA_LIMITED_TRANSPARENCY_FLOOR - raw_total, 4)
    return payload
