"""Label-unit vocabulary contract for clinical dose evaluation.

Every ``CLINICAL_DOSE_CONVERSION_RELEASE_BLOCK`` finding in the 2026-07-24
release run came from one defect class: the dose comparator did not know the
unit token printed on the label.  Two clinically distinct situations were
collapsed into one release-blocking ``conversion_error``:

1. **Comparable amounts the pipeline simply could not spell.**  ``U`` / ``UI``
   are International Units, ``ng`` is a mass, ``mg NE`` is niacin's own label
   unit, ``mg AT`` is alpha-tocopherol mass.  These are deterministic
   conversions that were silently dropped.

2. **Units that are not a comparable amount at all.**  ``%`` (percent DV),
   ``mcg/g`` (a standardization ratio), ``GDU`` / ``FCCPU`` / ``PU`` /
   ``m.c.u.`` (enzyme activity), ``NP`` (DSLD "not provided") and unrecognised
   tokens do not express how much of the subject the consumer takes.  That is
   clinical uncertainty about the dose — the authored ``amount_unknown``
   contract — not an engineering defect, and it must not block publication.

``conversion_error`` keeps its fail-closed meaning: the units WERE comparable
and the conversion machinery still failed.  See
``test_conversion_error_still_blocks_when_units_are_comparable``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _threshold(unit: str, value: float, target_id: str = "heart_disease") -> dict:
    return {
        "scope": "condition",
        "target_id": target_id,
        "basis": "per_day",
        "comparator": ">",
        "value": value,
        "unit": unit,
        "severity_if_met": "caution",
        "severity_if_not_met": "monitor",
    }


def _evaluate(enricher, ingredient: dict, threshold: dict) -> dict:
    _severity, result = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        threshold["target_id"],
        ingredient,
        1.0,
        "monitor",
    )
    return result


# --------------------------------------------------------------------------
# 1. Comparable amounts: the label unit must resolve to a real comparison.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "observed_unit,quantity,expected_status",
    [
        # DSLD prints Vitamin D International Units as "U" (66382) and "UI"
        # (67030) alongside sibling rows that use "IU" on the same label.
        ("U", 1000.0, "below_threshold"),
        ("UI", 1000.0, "below_threshold"),
        ("IU", 1000.0, "below_threshold"),
        ("U", 12000.0, "above_threshold"),
        # 64433 records Vitamin D in mg; mg -> mcg -> IU is exact, and the
        # implausible magnitude must surface as a fired threshold, not silence.
        ("mg", 800.0, "above_threshold"),
        ("mcg", 50.0, "below_threshold"),
    ],
)
def test_international_unit_aliases_are_evaluable(
    enricher, observed_unit, quantity, expected_status
):
    result = _evaluate(
        enricher,
        {
            "quantity": quantity,
            "unit": observed_unit,
            "name": "Vitamin D",
            "raw_source_text": "Vitamin D",
            "canonical_id": "vitamin_d",
        },
        _threshold("IU", 4000),
    )
    assert result["evaluation_status"] == expected_status
    assert result["release_blocking"] is False


def test_nanogram_is_a_mass_unit(enricher):
    """46729 records Vitamin B6 as ``40 ng``; ng -> mg is exact."""
    result = _evaluate(
        enricher,
        {
            "quantity": 40.0,
            "unit": "ng",
            "name": "Vitamin B6",
            "raw_source_text": "Vitamin B6",
            "canonical_id": "vitamin_b6_pyridoxine",
        },
        _threshold("mg", 200),
    )
    assert result["evaluation_status"] == "below_threshold"
    assert result["release_blocking"] is False


@pytest.mark.parametrize(
    "name,canonical_id,observed_unit,quantity,threshold_unit,threshold_value,expected",
    [
        # 1 mg NE == 1 mg of supplemental niacin (NE only rescales dietary
        # tryptophan), so niacin's own FDA label unit is comparable with mg.
        ("Niacin", "vitamin_b3_niacin", "mg NE", 30.0, "mg", 1000, "below_threshold"),
        ("Niacin", "vitamin_b3_niacin", "mg NE", 1500.0, "mg", 1000, "above_threshold"),
        # "mg AT" is literally milligrams of alpha-tocopherol (259789).
        ("Vitamin E", "vitamin_e", "mg AT", 83.76, "mg", 300, "below_threshold"),
        ("Vitamin E", "vitamin_e", "mg AT", 400.0, "mg", 300, "above_threshold"),
    ],
)
def test_nutrient_equivalence_units_compare_as_their_base_mass(
    enricher,
    name,
    canonical_id,
    observed_unit,
    quantity,
    threshold_unit,
    threshold_value,
    expected,
):
    result = _evaluate(
        enricher,
        {
            "quantity": quantity,
            "unit": observed_unit,
            "name": name,
            "raw_source_text": name,
            "canonical_id": canonical_id,
        },
        _threshold(threshold_unit, threshold_value),
    )
    assert result["evaluation_status"] == expected
    assert result["release_blocking"] is False


# --------------------------------------------------------------------------
# 2. Non-comparable units: honest amount_unknown, never a release block.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "observed_unit,quantity,name,canonical_id",
    [
        ("%", 6.0, "Calcium", "calcium"),                     # 16730 percent DV
        ("mcg/g", 2000.0, "Allicin", "allicin"),              # 246104 ratio
        ("GDU", 20.0, "Bromelain", "bromelain"),              # 2256 activity
        ("FCCPU", 300604.2, "Bromelain", "bromelain"),        # 18382 activity
        ("PU", 500000.0, "Bromelain", "bromelain"),           # 29295 activity
        ("m.c.u.", 1500.0, "Biotin", "vitamin_b7_biotin"),    # 254204 activity
        ("NP", 0.0, "Calcium", "calcium"),                    # DSLD sentinel
        ("mmg", 250.0, "Caffeine Anhydrous", "caffeine"),     # 243029 garbled
    ],
)
def test_non_comparable_units_are_amount_unknown_not_release_blocking(
    enricher, observed_unit, quantity, name, canonical_id
):
    result = _evaluate(
        enricher,
        {
            "quantity": quantity,
            "unit": observed_unit,
            "name": name,
            "raw_source_text": name,
            "canonical_id": canonical_id,
        },
        _threshold("mg", 1000),
    )
    assert result["evaluation_status"] == "amount_unknown"
    assert result["release_blocking"] is False
    # The authored amount-missing policy owns the consumer outcome; the
    # evaluator must not invent a disposition of its own.
    assert result["consumer_disposition"] == (
        result["decision_rule"]["amount_missing_disposition"]
    )


def test_non_comparable_unit_honours_authored_amount_missing_disposition(enricher):
    threshold = _threshold("mg", 1000)
    threshold["amount_missing_disposition"] = "review"
    result = _evaluate(
        enricher,
        {
            "quantity": 20.0,
            "unit": "GDU",
            "name": "Bromelain",
            "raw_source_text": "Bromelain",
            "canonical_id": "bromelain",
        },
        threshold,
    )
    assert result["evaluation_status"] == "amount_unknown"
    assert result["consumer_disposition"] == "review"
    assert result["release_blocking"] is False


def test_bare_units_on_a_non_iu_subject_stay_a_loud_contract_gap(enricher):
    """29032 records Lysozyme as ``1000000 U`` — an enzyme activity count.

    ``U`` reads as International Units, and no nutrient rule can bridge an
    enzyme's IU to a mass, so this remains release-blocking on purpose: an
    unauthored subject should fail loudly rather than be quietly filed as an
    undisclosed dose.  No product in the corpus hits this today.
    """
    result = _evaluate(
        enricher,
        {
            "quantity": 1000000.0,
            "unit": "U",
            "name": "Lysozyme",
            "raw_source_text": "Lysozyme",
            "canonical_id": "lysozyme",
        },
        _threshold("mg", 500),
    )
    assert result["evaluation_status"] == "conversion_error"
    assert result["release_blocking"] is True


def test_min_effective_dose_floor_also_reports_unit_not_comparable(enricher):
    """The ``min_effective_dose`` evaluator shares the same contract."""
    result = enricher._evaluate_min_effective_dose_decision(
        {"value": 200, "unit": "mg", "basis": "per_day"},
        {
            "quantity": 500000.0,
            "unit": "PU",
            "name": "Bromelain",
            "raw_source_text": "Bromelain",
            "canonical_id": "bromelain",
        },
        1.0,
        "monitor",
    )
    assert result["evaluation_status"] == "amount_unknown"
    assert result["release_blocking"] is False


# --------------------------------------------------------------------------
# 3. Fail-closed is preserved.
# --------------------------------------------------------------------------

def test_conversion_error_still_blocks_when_units_are_comparable(enricher):
    """Both units are comparable quantities but no rule bridges them.

    Vitamin C has no IU definition, so an IU label against a mg threshold is a
    genuine data-contract defect and must keep blocking the release.
    """
    result = _evaluate(
        enricher,
        {
            "quantity": 500.0,
            "unit": "IU",
            "name": "Vitamin C",
            "raw_source_text": "Vitamin C",
            "canonical_id": "vitamin_c",
        },
        _threshold("mg", 1000),
    )
    assert result["evaluation_status"] == "conversion_error"
    assert result["release_blocking"] is True


def test_missing_quantity_is_still_amount_unknown(enricher):
    result = _evaluate(
        enricher,
        {
            "quantity": None,
            "unit": "mg",
            "name": "Calcium",
            "raw_source_text": "Calcium",
            "canonical_id": "calcium",
        },
        _threshold("mg", 1000),
    )
    assert result["evaluation_status"] == "amount_unknown"
    assert result["release_blocking"] is False
