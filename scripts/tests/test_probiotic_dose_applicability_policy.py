"""Clinical dose applicability is exact-arm only and fails closed."""
import pytest

import probiotic_measurements as pm
import studied_formulas
from test_native_study_contexts import context


def arms(*values, basis="discrete_daily_arms", **extra):
    dose = {"basis": basis, "unit": "CFU", "values": list(values),
            "dosage_forms": [], "duration_days": None, "co_therapies": []}
    dose.update(extra)
    return dose


@pytest.mark.parametrize("amount,expected", [
    (1e9, ("EXACT_TESTED_DOSE", "matches_tested_daily_dose")),
    (1e10, ("EXACT_TESTED_DOSE", "matches_tested_daily_dose")),
    (5e9, ("OUTSIDE_TESTED_RANGE", "outside_tested_daily_doses")),
    (2e10, ("OUTSIDE_TESTED_RANGE", "outside_tested_daily_doses")),
    (5e8, ("OUTSIDE_TESTED_RANGE", "outside_tested_daily_doses")),
    (None, ("DOSE_UNKNOWN", "label_dose_unknown")),
])
def test_discrete_arms_are_points_not_an_interpolated_range(amount, expected):
    assert pm.classify_dose_applicability(amount, arms(1e9, 1e10)) == expected


def test_single_arm_matches_only_that_arm():
    assert pm.classify_dose_applicability(1e9, arms(1e9))[0] == "EXACT_TESTED_DOSE"
    assert pm.classify_dose_applicability(1.5e9, arms(1e9))[0] == "OUTSIDE_TESTED_RANGE"


def test_measured_viability_is_not_an_efficacy_dose():
    dose = arms(7.0e9, 4.69e9, basis="measured_viability")
    assert pm.classify_dose_applicability(5e9, dose) == (
        "DOSE_UNKNOWN", "study_daily_dose_unresolved")


def test_frozen_dose_basis_is_canonical_over_legacy_basis():
    dose = arms(1e9, basis="unresolved", dose_basis="per_strain_daily")
    assert pm.effective_clinical_dose_basis(dose) == "discrete_daily_arms"
    assert pm.classify_dose_applicability(1e9, dose) == (
        "EXACT_TESTED_DOSE", "matches_tested_daily_dose")


def test_unknown_frozen_dose_basis_fails_closed_instead_of_using_legacy_basis():
    dose = arms(1e9, dose_basis="invented_basis")
    assert pm.effective_clinical_dose_basis(dose) is None
    assert pm.classify_dose_applicability(1e9, dose) == (
        "DOSE_UNKNOWN", "study_daily_dose_unresolved")


@pytest.mark.parametrize("basis", ["unresolved", "single_challenge"])
def test_unresolved_or_challenge_doses_are_unknown(basis):
    assert pm.classify_dose_applicability(1e9, arms(basis=basis)) == (
        "DOSE_UNKNOWN", "study_daily_dose_unresolved")


def test_unresolved_basis_cannot_carry_a_hidden_numeric_dose():
    row = context(dose=arms(1e9, basis="unresolved"))
    assert studied_formulas.valid_native_study_context(row, "STRAIN_LGG") is False


@pytest.mark.parametrize("mtype,unit", [("mass", "mg"), ("afu", "AFU"), ("spores", "spores")])
def test_non_viable_count_measurements_never_map_onto_cfu_labels(mtype, unit):
    dose = arms(500, measurement_type=mtype, unit=unit)
    assert pm.classify_dose_applicability(500, dose) == (
        "DOSE_UNKNOWN", "study_dose_not_viable_count")


def test_only_exact_tested_dose_earns_credit():
    assert pm.dose_applicability_credit("EXACT_TESTED_DOSE") == 1.0
    assert pm.dose_applicability_credit("WITHIN_TESTED_RANGE") == 0.0
    assert pm.dose_applicability_credit("NEAR_TESTED_RANGE") == 0.0
    assert pm.dose_applicability_credit("OUTSIDE_TESTED_RANGE") == 0.0
    assert pm.dose_applicability_credit("DOSE_UNKNOWN") == 0.0
    assert pm.dose_applicability_credit("made_up") == 0.0


@pytest.mark.parametrize("mtype,unit,valid", [
    (None, "CFU", True), ("viable_count", "CFU", True), ("viable_count", "mg", False),
    ("mass", "mg", True), ("mass", "g", True), ("mass", "CFU", False),
    ("afu", "AFU", True), ("spores", "spores", True), ("plasma", "mg", False),
])
def test_validator_ties_unit_to_measurement_type(mtype, unit, valid):
    dose = {"basis": "unresolved", "unit": unit, "values": [], "dosage_forms": [],
            "duration_days": None, "co_therapies": []}
    if mtype is not None:
        dose["measurement_type"] = mtype
    assert studied_formulas.valid_native_study_context(context(dose=dose), "STRAIN_LGG") is valid
