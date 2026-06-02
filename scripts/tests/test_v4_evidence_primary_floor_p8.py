"""Phase 8 — primary-ingredient evidence floor (generic module).

The top-N additive evidence pipeline rewards ingredient COUNT: a focused single
clinically-validated ingredient (KSM-66) scored ~4.5/20 while two generic minerals
scored ~11.5/20. The floor lifts the dimension when the product's MASS-DOMINANT
active is strongly & positively evidenced at a clinical dose — keyed on the
primary active (not a well-studied trace co-ingredient), opt-in to the generic
module only (omega/probiotic/multi reuse this scorer and must not inherit it).
"""
from __future__ import annotations

from scoring_v4.modules.generic_evidence import (  # noqa: E402
    score_evidence, PRIMARY_FLOOR_STRONG, PRIMARY_FLOOR_MODERATE,
)


def _match(*, ingredient="Ashwagandha", standard_name=None, study_type="rct_multiple",
           effect_direction="positive_strong", evidence_level="ingredient-human",
           total_enrollment=500, **extra):
    row = {"id": f"INGR_{ingredient.upper()}", "ingredient": ingredient,
           "standard_name": standard_name or ingredient, "study_type": study_type,
           "evidence_level": evidence_level, "effect_direction": effect_direction,
           "total_enrollment": total_enrollment}
    row.update(extra)
    return row


def _ing(name="Ashwagandha", canonical_id="ashwagandha", quantity=600, unit="mg"):
    return {"name": name, "standard_name": name, "canonical_id": canonical_id,
            "mapped": True, "bio_score": 11, "score": 11, "quantity": quantity, "unit": unit}


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
    # does not. The trace ingredient must NOT anchor a floor.
    ings = [_ing("Magnesium", "magnesium", 1000, "mg"),
            _ing("Selenium", "selenium", 50, "mcg")]
    matches = [_match(ingredient="Selenium", standard_name="Selenium", study_type="rct_multiple")]
    out = score_evidence(_product(ings, matches), apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 0.0


def test_weak_effect_floors_below_strong_effect():
    # a meta with positive_WEAK effect must floor below a positive_strong one
    # (14 * 0.85 = 11.9), mirroring the pipeline's weak-effect discount.
    p = _product([_ing()], [_match(study_type="rct_multiple", effect_direction="positive_weak")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == round(14.0 * 0.85, 4)


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


# --- v4.1 branded-RCT evidence tier (KSM-66 / Meriva / Sensoril) ----------

def test_branded_strong_floors_to_18():
    """A branded clinically-studied extract with strong (meta/multi-RCT) evidence
    earns 18 — above a non-branded strong single (14) — but still below the 19-20
    band reserved for multi-active breadth."""
    p = _product([_ing()], [_match(study_type="rct_multiple", evidence_level="branded-rct")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 18.0
    assert out["score"] >= 18.0


def test_branded_moderate_floors_to_17():
    """Branded extract with a single RCT / clinical strain -> 17 (branded but
    not multi-RCT depth)."""
    p = _product([_ing()], [_match(study_type="rct_single", evidence_level="branded-rct")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 17.0


def test_branded_strong_weak_effect_discounts():
    """Effect-strength discount still applies on top of the branded tier
    (18 * 0.85 = 15.3) — a weak-effect branded meta floors below a strong one."""
    p = _product([_ing()], [_match(study_type="rct_multiple", evidence_level="branded-rct",
                                   effect_direction="positive_weak")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == round(18.0 * 0.85, 4)


def test_non_branded_strong_stays_14():
    """Guard: a merely-strong generic single does NOT get the branded tier."""
    p = _product([_ing()], [_match(study_type="rct_multiple", evidence_level="ingredient-human")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 14.0


def test_branded_subclinical_dose_still_blocks_floor():
    """Even a branded extract below its min clinical dose cannot float the floor."""
    p = _product([_ing(quantity=50)],
                 [_match(study_type="rct_multiple", evidence_level="branded-rct",
                         min_clinical_dose=300.0)])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 0.0


def test_branded_trace_ingredient_does_not_float_product():
    """A branded strong match on a TRACE co-ingredient (not mass-dominant) must
    not float the product."""
    ings = [_ing("Magnesium", "magnesium", 1000, "mg"),
            _ing("Sensoril Ashwagandha", "ashwagandha", 50, "mg")]
    matches = [_match(ingredient="Sensoril Ashwagandha", standard_name="Sensoril Ashwagandha",
                      study_type="rct_multiple", evidence_level="branded-rct")]
    out = score_evidence(_product(ings, matches), apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 0.0
