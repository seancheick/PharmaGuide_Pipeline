"""Phase 8 — primary-ingredient evidence floor (generic module).

The top-N additive evidence pipeline rewards ingredient COUNT: a focused single
clinically-validated ingredient (KSM-66) scored ~4.5/20 while two generic minerals
scored ~11.5/20. The floor lifts the dimension when the product's PROMINENT
active (the shared role owner's purpose, still holding half the heaviest active's
mass as the retained exposure stand-in) is strongly & positively evidenced at a
clinical dose — never a well-studied trace co-ingredient. Generic, sports and
fiber opt in; omega/probiotic/multi reuse this scorer and do not.
"""
from __future__ import annotations

from scoring_v4.modules.generic_evidence import (  # noqa: E402
    score_evidence, PRIMARY_FLOOR_STRONG, PRIMARY_FLOOR_MODERATE,
    PRIMARY_FLOOR_REPLICATED_STRONG, EFFECT_DIRECTION_MULTIPLIERS,
)


def _match(*, ingredient="Ashwagandha", standard_name=None, study_type="rct_multiple",
           effect_direction="positive_strong", evidence_level="ingredient-human",
           total_enrollment=500, **extra):
    # Explicit arithmetic fixture IDs cannot inherit a live ingredient hold.
    # Real held-source behavior is covered by the owner/consumer regressions.
    row = {"id": f"TEST_ELIGIBLE_{ingredient.upper()}", "ingredient": ingredient,
           "standard_name": standard_name or ingredient, "study_type": study_type,
           "evidence_level": evidence_level, "effect_direction": effect_direction,
           "total_enrollment": total_enrollment}
    row.update(extra)
    return row


def _ing(name="Ashwagandha", canonical_id="ashwagandha", quantity=600, unit="mg"):
    return {"name": name, "standard_name": name, "canonical_id": canonical_id,
            "mapped": True, "bio_score": 11, "quantity": quantity, "unit": unit}


def _product(ingredients, matches):
    return {"status": "active", "form_factor": "capsule",
            "supplement_type": {"type": "single_nutrient"},
            "ingredient_quality_data": {"ingredients_scorable": ingredients, "ingredients": ingredients},
            "evidence_data": {"clinical_matches": matches}}


def test_mass_primary_strong_floors_to_14():
    p = _product([_ing()], [_match(study_type="rct_multiple")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["score"] >= PRIMARY_FLOOR_STRONG == 14.0
    assert out["metadata"]["primary_evidence_floor"] == 14.0
    assert out["metadata"]["primary_evidence_floor_canonical"] == "ashwagandha"


def test_floor_not_applied_without_opt_in():
    # omega/probiotic/multi reuse this scorer WITHOUT the floor flag (default).
    p = _product([_ing()], [_match(study_type="rct_multiple")])
    out = score_evidence(p)  # apply_primary_floor defaults False
    assert out["metadata"]["primary_evidence_floor"] == 0.0
    assert out["score"] < 14.0


def test_trace_strong_ingredient_does_not_floor():
    # selenium (trace, 0.05 mg) has a strong match; magnesium (primary, 1000 mg)
    # does not. The trace ingredient must NOT anchor the CLINICAL floor (14).
    # P5: magnesium (mass-dominant essential) earns the nutrition-authority floor
    # (10); the selenium trace match still does not push it to the clinical tier.
    ings = [_ing("Magnesium", "magnesium", 1000, "mg"),
            _ing("Selenium", "selenium", 50, "mcg")]
    matches = [_match(ingredient="Selenium", standard_name="Selenium", study_type="rct_multiple")]
    out = score_evidence(_product(ings, matches), apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 10.0
    assert out["metadata"]["nutrition_authority_canonical"] == "magnesium"


def test_weak_effect_floors_below_strong_effect():
    """A weak-effect meta must floor below a positive_strong one.

    Pre-lock that was 14 * 0.85 = 11.9; direction_ceiling now caps a non-strong
    direction at the MODERATE base weighted by its multiplier. The invariant the
    test exists for — weak sits below strong — is unchanged.
    """
    p = _product([_ing()], [_match(study_type="rct_multiple", effect_direction="positive_weak")])
    out = score_evidence(p, apply_primary_floor=True)

    ceiling = round(PRIMARY_FLOOR_MODERATE * EFFECT_DIRECTION_MULTIPLIERS["positive_weak"], 4)
    assert out["metadata"]["primary_evidence_floor"] == ceiling
    assert ceiling < PRIMARY_FLOOR_STRONG


def test_moderate_study_floors_to_11():
    p = _product([_ing()], [_match(study_type="rct_single")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_MODERATE == 11.0
    assert out["score"] >= 11.0


def test_negative_effect_does_not_floor():
    p = _product([_ing()], [_match(study_type="rct_multiple", effect_direction="negative")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 0.0


def test_weak_study_type_does_not_floor():
    p = _product([_ing()], [_match(study_type="observational")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 0.0


# --- Replicated-body tier (Dr Pham framework, October 28, 2026) ------------
# The near-perfect floor once followed a brand marker or an ingredient allowlist.
# One or two small manufacturer-supplied trials could reach 20/20 that way. It now
# follows the reviewed evidence body: clinician-approved contexts of the record
# must show at least three consistent, independent RCT families for one
# condition, with no contradictory family. A brand or ingredient name earns nothing.

_REVIEW = {"reviewer": "Test clinician", "reviewed_at": "2026-10-01",
           "scope": "identity_dose_outcome_applicability"}


def _context(family, *, direction="positive", condition="perceived_stress",
             role="direct_rct", review_status="clinician_approved", scope="branded_material"):
    return {"context_id": family, "trial_family": family, "condition": condition,
            "evidence_role": role, "review_status": review_status, "identity_scope": scope,
            "scoring_eligible": True, "clinical_review": dict(_REVIEW),
            "outcomes": [{"name": "Perceived stress", "direction": direction,
                          "hierarchy": "primary", "kind": "patient_important"}]}


def _replicated(*families, **kwargs):
    return [_context(family, **kwargs) for family in families or ("a", "b", "c")]


def _registered(monkeypatch, *matches):
    """Replication is read from the clinical registry, never from the match."""
    import clinical_applicability
    registry = {**clinical_applicability.reviewed_entries(), **{m["id"]: m for m in matches}}
    monkeypatch.setattr(clinical_applicability, "reviewed_entries", lambda: registry)
    return list(matches)


def test_branded_record_without_replicated_body_is_strong_not_exceptional():
    """BRAND_ASTAREAL/KSM-66 shape: a branded multi-RCT record with no approved
    replicated body floors at the ordinary strong base, 14 (15.6/20), not 18 (20/20)."""
    p = _product([_ing()], [_match(study_type="rct_multiple", evidence_level="branded-rct")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_STRONG == 14.0


def test_single_branded_rct_is_moderate():
    """One branded trial is a moderate floor (11 = 12.2/20), never 17 (18.9/20)."""
    p = _product([_ing()], [_match(study_type="rct_single", evidence_level="branded-rct")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_MODERATE == 11.0


def test_brand_id_prefix_no_longer_elevates():
    p = _product(
        [_ing("BioCell Collagen", "collagen", 1000, "mg")],
        [_match(id="BRAND_BIOCELL", ingredient="BioCell", standard_name="BioCell Collagen",
                study_type="rct_multiple", evidence_level="product-human")],
    )
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 14.0


def test_replicated_body_reaches_exceptional_floor(monkeypatch):
    p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple",
                                                         study_contexts=_replicated())))
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_REPLICATED_STRONG == 18.0


def test_replication_needs_three_families_for_one_condition(monkeypatch):
    two = _replicated("a", "b")
    split = [_context("a"), _context("b"), _context("c", condition="sleep")]
    for contexts in (two, split):
        p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple",
                                                             study_contexts=contexts)))
        assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_contradictory_family_blocks_exceptional_floor(monkeypatch):
    contexts = _replicated() + [_context("d", direction="null")]
    p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple",
                                                         study_contexts=contexts)))
    assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_indirect_pooled_or_unapproved_contexts_are_not_replication(monkeypatch):
    """A meta-analysis is not linked to its independent trials, a context still
    pending clinical review authorizes nothing (context_accepted_for_scoring),
    and a combination formula's result is not this ingredient's (directness)."""
    pooled = _replicated("a", "b", "c", role="meta_analysis")
    pending = _replicated(review_status="source_verified_pending_clinical_review")
    combination = _replicated(scope="combination")
    unscoped = _replicated(scope=None)
    for contexts in (pooled, pending, combination, unscoped):
        p = _product([_ing()], _registered(monkeypatch, _match(study_type="systematic_review_meta",
                                                             study_contexts=contexts)))
        assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_unregistered_match_cannot_supply_its_own_replication():
    """Contexts carried on a match that is not a registry record (or that differ
    from its record) never broaden reviewed scope."""
    p = _product([_ing()], [_match(study_type="rct_multiple", study_contexts=_replicated())])
    assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_replicated_single_rct_record_stays_moderate(monkeypatch):
    p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_single",
                                                         study_contexts=_replicated())))
    assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 11.0


def test_weak_effect_cannot_ride_the_replicated_strong_base(monkeypatch):
    """direction_ceiling (locked 2026-09-18): only positive_strong anchors a strong
    base; weaker directions cap at the MODERATE base times their multiplier."""
    p = _product([_ing()], _registered(monkeypatch, _match(
        study_type="rct_multiple", effect_direction="positive_weak", study_contexts=_replicated())))
    out = score_evidence(p, apply_primary_floor=True)
    ceiling = round(PRIMARY_FLOOR_MODERATE * EFFECT_DIRECTION_MULTIPLIERS["positive_weak"], 4)
    assert out["metadata"]["primary_evidence_floor"] == ceiling


def test_retired_ingredient_allowlist_no_longer_elevates():
    """Psyllium, vitamin D, folate and creatine reach the exceptional floor only
    through a replicated reviewed body, like every other record."""
    p = _product([_ing("Psyllium", "psyllium", 5000, "mg")],
                 [_match(ingredient="Psyllium", standard_name="Psyllium",
                         canonical_id="psyllium", study_type="rct_multiple",
                         evidence_level="ingredient-human")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 14.0
    assert out["metadata"]["primary_evidence_floor_canonical"] == "psyllium"


def test_studied_amount_does_not_gate_evidence_floor(monkeypatch):
    p = _product([_ing(quantity=50)],
                 _registered(monkeypatch, _match(study_type="rct_multiple", min_clinical_dose=300.0,
                                                 study_contexts=_replicated())))
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 18.0


def test_branded_trace_ingredient_does_not_float_product():
    """A branded strong match on a TRACE co-ingredient (not mass-dominant) must
    not float the product to a clinical floor. P5: magnesium (the
    mass-dominant essential) earns the nutrition-authority floor 10 — the trace
    branded ashwagandha does NOT lift it to 18."""
    ings = [_ing("Magnesium", "magnesium", 1000, "mg"),
            _ing("Sensoril Ashwagandha", "ashwagandha", 50, "mg")]
    matches = [_match(ingredient="Sensoril Ashwagandha", standard_name="Sensoril Ashwagandha",
                      study_type="rct_multiple", evidence_level="branded-rct")]
    out = score_evidence(_product(ings, matches), apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 10.0
    assert out["metadata"]["nutrition_authority_canonical"] == "magnesium"


# --- P5 nutrition-authority floor (DRI-essential nutrients) 2026-06 ----------

def test_essential_nutrient_authority_floor_lifts_copper():
    """P5: copper (essential DRI mineral) with no strong RCT match still has
    evidence of necessity -> nutrition-authority floor 10 (below the 14 clinical
    tier). Was evidence 0 -> POOR."""
    p = _product([_ing("Copper", "copper", 2, "mg")], [])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["score"] >= 10.0
    assert out["metadata"]["nutrition_authority_floor_applied"] is True
    assert out["metadata"]["nutrition_authority_canonical"] == "copper"


def test_non_essential_gets_no_authority_floor():
    """Guard: boron (UL only, no RDA) is NOT DRI-essential -> no authority floor,
    stays evidence-light."""
    p = _product([_ing("Boron", "boron", 3, "mg")], [])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["nutrition_authority_floor_applied"] is False
    assert out["score"] < 10.0


def test_authority_floor_never_lowers_stronger_floor():
    """Authority is a floor, never a cap: an essential nutrient with a strong
    clinical record keeps that higher floor (vitamin D strong = 14 > authority 10)."""
    p = _product([_ing("Vitamin D", "vitamin_d", 25, "mcg")],
                 [_match(ingredient="Vitamin D", standard_name="Vitamin D",
                         canonical_id="vitamin_d", study_type="rct_multiple",
                         evidence_level="ingredient-human")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 14.0


def test_authority_floor_is_generic_opt_in_only():
    """omega/probiotic/multi reuse this scorer without the floor flag -> no
    authority floor (they have their own evidence logic)."""
    p = _product([_ing("Copper", "copper", 2, "mg")], [])
    out = score_evidence(p)  # default apply_primary_floor=False
    assert out["metadata"]["nutrition_authority_floor_applied"] is False
    assert out["score"] < 10.0


# --- Public bands (Dr Pham, October 28, 2026; editorial ranges, not GRADE) ---

def test_each_floor_lands_in_its_public_band():
    """On the 18-point generic reference, each automatic floor's public /20 value
    sits inside its band: exceptional 19-20, strong 15-18, moderate 11-14,
    essential-nutrient nutrition 10-12 (between limited and moderate) and
    limited 6-10 for weak or mixed directions."""
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config
    from scoring_v4.modules.generic_evidence import NUTRITION_AUTHORITY_FLOOR

    def public(raw):
        return _pillar_evidence({"score": raw, "metadata": {"evidence_result_state": "evaluated_applicable"}},
                                20.0, "generic_single_molecule", config())["score"]

    assert 19 <= public(PRIMARY_FLOOR_REPLICATED_STRONG) <= 20
    assert 15 <= public(PRIMARY_FLOOR_STRONG) <= 18
    assert 11 <= public(PRIMARY_FLOOR_MODERATE) <= 14
    assert 10 <= public(NUTRITION_AUTHORITY_FLOOR) <= 12
    for direction in ("positive_weak", "mixed"):
        assert 6 <= public(PRIMARY_FLOOR_MODERATE * EFFECT_DIRECTION_MULTIPLIERS[direction]) <= 11
