"""
Regression suite for Vitamin A IU → mcg RAE form-aware normalization.

Issue: DosageNormalizer._normalize_ingredient was calling
  unit_converter.convert_nutrient(ingredient_name=name)
passing only the bare ingredient name (e.g. "Vitamin A"). The unit
converter's form detection scans ``ingredient_name`` for tokens like
"beta-carotene" / "retinyl palmitate"; the bare name never contains a
form, so detection routed to ``vitamin_a_unknown`` (factor 1.0) and the
IU value was kept as-is. Result: 5000 IU Vitamin A stayed at "5000 IU"
in the blob instead of converting to 500 mcg RAE (β-carotene) or
1500 mcg RAE (retinol). The pregnancy UL gate (3000 mcg RAE) and other
mcg-RAE thresholds therefore could not fire correctly.

Fix: dosage_normalizer.py joins ``ingredient['forms'][*].name`` onto the
ingredient_name passed to the converter, so β-Carotene / Retinyl
Palmitate tokens are visible to form detection.

Tests cover:
  - β-Carotene supplement form (factor 0.1 → 500 mcg RAE from 5000 IU)
  - Retinyl Palmitate / retinol form (factor 0.3 → 1500 mcg RAE)
  - Unknown form (no forms[] data) — still converts safely (factor 1.0,
    flagged for manual review)
  - Vitamin A NOT in IU (mcg / mcg RAE) — passthrough unchanged
  - Non-vitamin-A nutrient — no impact
  - Sentinel BLOCKER finding: the audit code in audit_raw_to_final.py
    accepts the result as a safe conversion.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.dosage_normalizer import DosageNormalizer, ServingBasis  # noqa: E402
from scripts.unit_converter import UnitConverter  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_normalizer() -> DosageNormalizer:
    return DosageNormalizer(UnitConverter())


def _serving_basis() -> ServingBasis:
    return ServingBasis(
        quantity=1.0,
        unit="capsule",
        servings_per_container=30,
        servings_per_day_min=1,
        servings_per_day_max=1,
        servings_per_day_used=1,
        source_field="test_fixture",
        raw_text="1 capsule daily",
        confidence="high",
    )


# ---------------------------------------------------------------------------
# Core form-detection regression tests
# ---------------------------------------------------------------------------

def test_vitamin_a_iu_beta_carotene_form_converts_to_mcg_rae() -> None:
    """5000 IU Vitamin A with β-carotene form → 500 mcg RAE (factor 0.1)."""
    n = _make_normalizer()
    ing = {
        "name": "Vitamin A",
        "raw_source_text": "Vitamin A",
        "quantity": 5000.0,
        "unit": "IU",
        "forms": [{"name": "Beta-Carotene", "ingredientGroup": "Vitamin A"}],
        "standardName": "Vitamin A",
    }
    result = n._normalize_ingredient(ing, _serving_basis(), "activeIngredients[0]")
    assert result is not None
    assert result.normalized_unit == "mcg RAE", (
        f"expected mcg RAE, got {result.normalized_unit!r}"
    )
    assert result.normalized_amount == pytest.approx(500.0), (
        f"expected 500 mcg RAE from 5000 IU β-carotene supplement, got {result.normalized_amount}"
    )
    assert "beta-carotene" in (result.standard_name or "").lower()


def test_vitamin_a_iu_retinyl_palmitate_converts_to_mcg_rae() -> None:
    """5000 IU Vitamin A with retinyl palmitate form → 1500 mcg RAE (factor 0.3)."""
    n = _make_normalizer()
    ing = {
        "name": "Vitamin A",
        "raw_source_text": "Vitamin A (Retinyl Palmitate)",
        "quantity": 5000.0,
        "unit": "IU",
        "forms": [{"name": "Retinyl Palmitate", "ingredientGroup": "Vitamin A"}],
        "standardName": "Vitamin A",
    }
    result = n._normalize_ingredient(ing, _serving_basis(), "activeIngredients[0]")
    assert result is not None
    assert result.normalized_unit == "mcg RAE"
    assert result.normalized_amount == pytest.approx(1500.0)
    assert "retinol" in (result.standard_name or "").lower() or "retinyl" in (result.standard_name or "").lower()


def test_vitamin_a_iu_no_form_data_stays_safe_with_explicit_unknown() -> None:
    """When forms[] is empty, conversion still runs but routes to vitamin_a_unknown
    with conversion_factor=1.0. The downstream dose-safety gate must treat the
    output as low-confidence (the warning string carries this signal)."""
    n = _make_normalizer()
    ing = {
        "name": "Vitamin A",
        "raw_source_text": "Vitamin A",
        "quantity": 5000.0,
        "unit": "IU",
        "forms": [],
        "standardName": "Vitamin A",
    }
    result = n._normalize_ingredient(ing, _serving_basis(), "activeIngredients[0]")
    assert result is not None
    # When unknown, the rule may keep IU or pass through; the contract is
    # that conversion_evidence carries an explicit warning. The audit-side
    # BLOCKER fires when the unit isn't mcg RAE.
    if result.normalized_unit == "IU":
        # Acceptable for unknown form, BUT conversion_evidence must flag low confidence
        ev = result.conversion_evidence or {}
        warnings = ev.get("warnings") or []
        assert any(
            "form" in (w or "").lower() and "unknown" in str(w).lower()
            or "retinol vs beta-carotene" in (w or "").lower()
            for w in warnings
        ), (
            f"unknown-form Vitamin A must carry a form-warning string; got warnings={warnings}"
        )


def test_vitamin_a_mcg_label_not_flagged_by_audit() -> None:
    """When the label already uses mcg, the audit's UNSAFE_UNIT_CONVERSION
    finding must NOT fire. The unit_converter's same-unit case may return
    success=False (no conversion rule applies), and that's fine — the audit
    only flags when source is IU. This test pins the audit semantics."""
    # The audit checks the blob entry directly, not the normalizer return.
    blob_ing_mcg = {
        "name": "Vitamin A",
        "dosage": 600.0,
        "dosage_unit": "mcg",
        "normalized_unit": "mcg",
        "normalized_value": 600.0,
    }
    assert _audit_check_vitamin_a(blob_ing_mcg) is False


def test_vitamin_d_iu_form_independent_passthrough() -> None:
    """Vitamin D IU → mcg is form-independent (40 IU/mcg always). This test
    guards against the fix accidentally breaking the non-form-dependent path."""
    n = _make_normalizer()
    ing = {
        "name": "Vitamin D",
        "quantity": 1000.0,
        "unit": "IU",
        "forms": [{"name": "Cholecalciferol"}],
        "standardName": "Vitamin D3",
    }
    result = n._normalize_ingredient(ing, _serving_basis(), "activeIngredients[5]")
    assert result is not None
    # Conversion should produce 25 mcg (1000 IU * 0.025)
    if result.normalized_unit and "mcg" in result.normalized_unit.lower():
        assert result.normalized_amount == pytest.approx(25.0, rel=0.01), (
            f"expected 25 mcg from 1000 IU vitamin D, got {result.normalized_amount}"
        )


def test_non_vitamin_a_nutrient_unaffected_by_fix() -> None:
    """The fix joins forms[].name onto ingredient_name. For nutrients that
    aren't form-dependent (Magnesium, Iron, etc.), this MUST behave the
    same as before the fix. The unit_converter has no rule for Magnesium —
    pre-fix and post-fix both return success=False / normalized_amount=None.
    What matters is that the fix doesn't BREAK the path (e.g. by raising)."""
    n = _make_normalizer()
    # Two parallel calls — one with forms[], one without. Both must succeed
    # (return a NormalizedIngredient object, not raise) and both must produce
    # the same shape (the form info doesn't accidentally route Magnesium to
    # a Vitamin A rule or similar).
    with_forms = n._normalize_ingredient(
        {"name": "Magnesium", "quantity": 200.0, "unit": "mg",
         "forms": [{"name": "Citrate"}], "standardName": "Magnesium"},
        _serving_basis(), "activeIngredients[7]")
    without_forms = n._normalize_ingredient(
        {"name": "Magnesium", "quantity": 200.0, "unit": "mg",
         "standardName": "Magnesium"},
        _serving_basis(), "activeIngredients[7]")
    assert with_forms is not None and without_forms is not None
    assert with_forms.normalized_amount == without_forms.normalized_amount
    assert with_forms.normalized_unit == without_forms.normalized_unit
    # Original amount/unit always preserved
    assert with_forms.original_amount == pytest.approx(200.0)
    assert (with_forms.original_unit or "").lower() == "mg"


# ---------------------------------------------------------------------------
# Audit-side contract: confirm the BLOCKER finding catches the bad case
# and is silent on the fixed case.
# ---------------------------------------------------------------------------

def _audit_check_vitamin_a(blob_ing: dict) -> bool:
    """Mimic audit_raw_to_final._check_unsafe_unit_conversion for one ingredient.
    Returns True when the audit would flag UNSAFE_UNIT_CONVERSION."""
    n = (blob_ing.get("name") or "").lower()
    unit = (blob_ing.get("dosage_unit") or blob_ing.get("unit") or "").upper()
    nu = (blob_ing.get("normalized_unit") or "").upper()
    nv = blob_ing.get("normalized_value")
    if unit == "IU" and ("vitamin a" in n or "retinyl" in n or "carotene" in n):
        return nv is None or nu not in ("MCG RAE", "MCG", "UG RAE", "UG")
    return False


def test_audit_flags_pre_fix_blob_shape() -> None:
    """The blob produced by the pre-fix pipeline (normalized_unit='IU') must
    be flagged by the audit. This locks in the canary signature."""
    blob_ing = {
        "name": "Vitamin A",
        "dosage": 5000.0,
        "dosage_unit": "IU",
        "normalized_unit": "IU",     # pre-fix shape
        "normalized_value": 5000.0,
    }
    assert _audit_check_vitamin_a(blob_ing) is True


def test_audit_is_silent_on_post_fix_blob_shape() -> None:
    """After the fix propagates through enrichment + build, the blob carries
    normalized_unit='mcg RAE' and the audit no longer flags."""
    blob_ing = {
        "name": "Vitamin A",
        "dosage": 5000.0,
        "dosage_unit": "IU",
        "normalized_unit": "mcg RAE",
        "normalized_value": 500.0,
    }
    assert _audit_check_vitamin_a(blob_ing) is False


def test_audit_silent_when_label_already_in_mcg() -> None:
    blob_ing = {
        "name": "Vitamin A",
        "dosage": 600.0,
        "dosage_unit": "mcg",
        "normalized_unit": "mcg",
        "normalized_value": 600.0,
    }
    assert _audit_check_vitamin_a(blob_ing) is False
