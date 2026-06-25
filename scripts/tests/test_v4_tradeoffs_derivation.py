"""Regression tests for `derive_v4_tradeoffs` — the V4-sourced replacement for
the V3-section-derived `score_bonuses` / `score_penalties`.

Contract (V4 cutover):
  * Bonuses come from `_v4_module_breakdown.dimensions.formulation.components`
    (A2..A6, A5a..A5d) and `_v4_module_breakdown.verification_bonus.components`
    (B4a..B4c). A5e natural-source and the hypoallergenic bonus are DROPPED.
  * Nuanced transparency penalties (B2 false-allergen-free, B3 compliance,
    B5 opacity, B6 marketing) come from the V4 transparency dimension.
  * Safety penalties (B0 banned/recalled, B1 harmful additive, B1 dietary sugar,
    B7 dose-over-UL) gate on ENRICHED presence — never under-warn — and preserve
    their per-item detail. CAERS/B8 is intentionally NOT surfaced: it was dead in
    production (0 shipped blobs), v4 does not score it, and its count-based
    "strength" over-warns on safe staples (e.g. calcium).
  * The derivation reads ZERO V3 section scores: `scored` carries no
    "breakdown" / "section_scores" in any test here.

Flutter only renders `label`(/`reason`) and `detail`(/`description`) — see
lib/.../sections/tradeoffs_section.dart `_toTradeoff` — so the assertions key
on those, plus the stable `id` for locating items.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.build_final_db import derive_v4_tradeoffs  # noqa: E402


def _scored_v4(*, form=None, form_pen=None, transp_pen=None, transp_comp=None,
               transp_meta=None, verif=None, manuf_violation=None, dose=None, dose_meta=None):
    """A `scored` dict carrying ONLY the v4 contract — no v3 breakdown."""
    return {
        "_v4_module_breakdown": {
            "dimensions": {
                "formulation": {"components": form or {}, "penalties": form_pen or {}},
                "dose": {"components": dose or {}, "metadata": dose_meta or {}},
                "transparency": {
                    "penalties": transp_pen or {},
                    "components": transp_comp or {},
                    "metadata": transp_meta or {},
                },
            },
            "verification_bonus": {"components": verif or {}},
            "manufacturer_violations": manuf_violation or {},
        }
    }


def _ids(items):
    return {i.get("id") for i in items}


def _by_id(items, _id):
    return next(i for i in items if i.get("id") == _id)


# --------------------------------------------------------------------------
# Bonuses — from v4 formulation + verification components.
# --------------------------------------------------------------------------

def test_bonuses_from_v4_formulation_components():
    scored = _scored_v4(
        form={"A2_premium_forms": 1.5, "A5a_organic": 0.5, "A6_single_ingredient": 1.0},
        verif={"B4a_verified_certifications": 1.0, "B4b_gmp": 0.5},
    )
    bonuses, _ = derive_v4_tradeoffs(scored, {})
    labels = {b["label"] for b in bonuses}
    assert "Premium ingredient forms" in labels
    assert "Certified organic" in labels
    assert "Single-nutrient premium form" in labels
    assert "Third-party purity testing" in labels
    assert "GMP certified facility" in labels
    # the bonus score mirrors the v4 component value
    assert _by_id(bonuses, "A2")["score"] == 1.5


def test_omega3_dose_bonus_from_v4_module():
    """The omega module credits dose via epa_dha_band; surface it as the
    'Omega-3 dose bonus' chip with the band label as detail."""
    scored = _scored_v4(dose={"epa_dha_band": 20.0},
                        dose_meta={"epa_dha_band_label": "high_clinical"})
    bonuses, _ = derive_v4_tradeoffs(scored, {})
    omega = _by_id(bonuses, "omega3")
    assert omega["label"] == "Omega-3 dose bonus"
    assert omega["detail"] == "high clinical"


def test_probiotic_quality_bonus_from_v4_module():
    """The probiotic module credits strain quality via formulation components;
    surface it as the 'Probiotic quality bonus' chip."""
    scored = _scored_v4(form={"clinical_strain_codes": 8.0, "named_species_diversity": 2.0})
    bonuses, _ = derive_v4_tradeoffs(scored, {})
    prob = _by_id(bonuses, "probiotic")
    assert prob["label"] == "Probiotic quality bonus"
    assert prob["score"] == 10.0


def test_dropped_bonuses_never_emit():
    """A5e natural-source and hypoallergenic have no user-facing home in v4."""
    scored = _scored_v4(
        form={"A5e_natural_source": 2.0},
        transp_comp={"hypoallergenic_bonus": 1.0},
    )
    bonuses, _ = derive_v4_tradeoffs(scored, {})
    assert "B_hypo" not in _ids(bonuses)
    assert not any("natural-source" in b["label"].lower() for b in bonuses)


# --------------------------------------------------------------------------
# Transparency penalties — from the v4 transparency dimension.
# --------------------------------------------------------------------------

def test_transparency_penalties_from_v4():
    scored = _scored_v4(
        transp_pen={
            "B5_proprietary_blend_opacity": -2.0,
            "B6_marketing_claims": -1.0,
        },
        transp_comp={"B3_claim_compliance": -1.0},
        transp_meta={"B5_blend_count": 3},
    )
    _, penalties = derive_v4_tradeoffs(scored, {})
    ids = _ids(penalties)
    assert {"B5", "B6", "B3"} <= ids
    assert _by_id(penalties, "B5")["blend_count"] == 3


def test_b2_declared_allergen_from_enriched():
    """B2 keeps the v3 user-facing meaning (allergen presence), not v4's
    narrower false-allergen-free-claim signal."""
    enriched = {"allergen_hits": [
        {"allergen_name": "Milk", "severity_level": "high", "presence_type": "contains"},
    ]}
    _, penalties = derive_v4_tradeoffs(_scored_v4(), enriched)
    b2 = _by_id(penalties, "B2")
    assert b2["label"] == "Declared allergen source: Milk"


def test_transparency_penalties_absent_when_zero():
    scored = _scored_v4(transp_pen={"B5_proprietary_blend_opacity": 0.0})
    _, penalties = derive_v4_tradeoffs(scored, {})
    assert "B5" not in _ids(penalties)


# --------------------------------------------------------------------------
# Safety penalties — gate on ENRICHED presence, detail preserved.
# --------------------------------------------------------------------------

def test_b0_banned_from_enriched_presence():
    enriched = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"status": "banned", "ingredient": "Ephedra",
                     "match_type": "exact", "reason": "FDA banned stimulant"},
                ]
            }
        }
    }
    _, penalties = derive_v4_tradeoffs(_scored_v4(), enriched)
    b0 = _by_id(penalties, "B0")
    assert b0["label"] == "Banned: Ephedra"
    assert "stimulant" in b0["reason"].lower()


def test_b1_harmful_additive_from_enriched():
    enriched = {"harmful_additives": [
        {"additive_name": "Disodium EDTA", "severity_level": "moderate",
         "mechanism_of_harm": "Non-selective chelator"},
    ]}
    _, penalties = derive_v4_tradeoffs(_scored_v4(), enriched)
    b1 = _by_id(penalties, "B1")
    assert b1["label"] == "Harmful additive: Disodium EDTA"


def test_b7_dose_over_ul_detail_preserved():
    enriched = {"rda_ul_data": {"safety_flags": [
        {"nutrient": "Vitamin B3 (Niacin)", "amount": 1000.0, "ul": 35, "pct_ul": 2857.14},
    ]}}
    _, penalties = derive_v4_tradeoffs(_scored_v4(), enriched)
    b7 = _by_id(penalties, "B7")
    assert "Vitamin B3 (Niacin)" in b7["label"]
    assert "2857% of UL" in b7["label"]
    assert b7["severity"] == "critical"


def test_b8_caers_not_surfaced():
    """CAERS/B8 must NOT appear — dead in production, v4 doesn't score it, and a
    count-based signal over-warns on safe staples. A calcium active (a 'strong'
    CAERS signal) yields no B8 con."""
    enriched = {"ingredient_quality_data": {"ingredients": [{"canonical_id": "calcium"}]}}
    _, penalties = derive_v4_tradeoffs(_scored_v4(), enriched)
    assert "B8" not in _ids(penalties)


def test_no_v3_section_dependency():
    """Smoke: a scored dict with NO breakdown/section_scores still derives."""
    scored = _scored_v4(form={"A2_premium_forms": 1.0})
    assert "breakdown" not in scored and "section_scores" not in scored
    bonuses, penalties = derive_v4_tradeoffs(scored, {})
    assert isinstance(bonuses, list) and isinstance(penalties, list)
    assert "Premium ingredient forms" in {b["label"] for b in bonuses}
