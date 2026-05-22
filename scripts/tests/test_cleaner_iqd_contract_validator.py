import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrichment_contract_validator import EnrichmentContractValidator


def _f_rules(product):
    violations = EnrichmentContractValidator().validate(product)
    return [v for v in violations if v.rule.startswith("F.")]


def _row(**overrides):
    base = {
        "name": "Vitamin C",
        "canonical_id": "vitamin_c",
        "raw_source_path": "ingredientRows[0]",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "quantity": 100,
        "unit": "mg",
        "scoreable_identity": True,
        "role_classification": "active_scorable",
    }
    base.update(overrides)
    return base


def test_valid_cleaner_iqd_contract_has_no_f_violations():
    product = {
        "id": "cleaner-iqd-valid",
        "ingredient_quality_data": {
            "ingredients": [_row()],
            "ingredients_scorable": [_row()],
        },
    }

    assert _f_rules(product) == []


def test_iqd_rows_must_preserve_cleaner_provenance_fields():
    product = {
        "id": "cleaner-iqd-missing-provenance",
        "ingredient_quality_data": {
            "ingredients": [_row(raw_source_path="")],
            "ingredients_scorable": [],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.7" in rules


def test_non_scorable_cleaner_roles_cannot_enter_ingredients_scorable():
    product = {
        "id": "cleaner-iqd-blend-header-scorable",
        "ingredient_quality_data": {
            "ingredients": [],
            "ingredients_scorable": [
                _row(
                    name="Proprietary Blend",
                    cleaner_row_role="blend_header_total",
                    score_eligible_by_cleaner=False,
                    score_exclusion_reason="blend_header_total",
                    dose_class="blend_total_weight",
                )
            ],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.4" in rules
    assert "F.5" in rules


def test_inactive_rows_require_explicit_cleaner_promotion_to_be_scorable():
    product = {
        "id": "cleaner-iqd-inactive-leak",
        "ingredient_quality_data": {
            "ingredients": [],
            "ingredients_scorable": [
                _row(
                    name="Leucine",
                    raw_source_path="otheringredients.ingredients[0]",
                    source_section="inactive",
                    cleaner_row_role="active_scorable",
                    score_eligible_by_cleaner=True,
                )
            ],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.6" in rules


def test_explicit_cleaner_misfiled_active_role_allows_inactive_promotion():
    product = {
        "id": "cleaner-iqd-explicit-promotion",
        "ingredient_quality_data": {
            "ingredients": [],
            "ingredients_scorable": [
                _row(
                    raw_source_path="otheringredients.ingredients[0]",
                    source_section="inactive",
                    cleaner_row_role="active_misfiled_in_inactive",
                    score_eligible_by_cleaner=True,
                )
            ],
        },
    }

    assert _f_rules(product) == []


def test_unknown_cleaner_role_is_contract_violation():
    product = {
        "id": "cleaner-iqd-unknown-role",
        "ingredient_quality_data": {
            "ingredients": [_row(cleaner_row_role="therapeutic_guess")],
            "ingredients_scorable": [],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.9" in rules


def test_recognized_non_scorable_cannot_enter_ingredients_scorable():
    product = {
        "id": "iqd-recognized-in-scorable",
        "ingredient_quality_data": {
            "ingredients": [],
            "ingredients_scorable": [
                _row(
                    name="Sunflower Oil",
                    recognized_non_scorable=True,
                    scoreable_identity=False,
                    role_classification="recognized_non_scorable",
                    fallback_class="clinical_fail_safe",
                    fallback_reason="recognized_non_scorable",
                )
            ],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.10" in rules
    assert "F.11" in rules
    assert "F.12" in rules


def test_scorable_iqd_requires_dose_evidence():
    product = {
        "id": "iqd-no-dose",
        "ingredient_quality_data": {
            "ingredients": [],
            "ingredients_scorable": [
                _row(quantity=None, unit="", dose_class="none", has_dose=False)
            ],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.13" in rules


def test_enzyme_activity_counts_as_dose_evidence():
    product = {
        "id": "iqd-enzyme-activity",
        "ingredient_quality_data": {
            "ingredients": [],
            "ingredients_scorable": [
                _row(
                    name="Serrapeptase",
                    canonical_id="serrapeptase",
                    dose_class="enzyme_activity",
                    quantity=None,
                    unit="SPU",
                    has_dose=True,
                )
            ],
        },
    }

    assert _f_rules(product) == []


def test_fallback_iqd_decisions_require_field_level_diagnostics():
    product = {
        "id": "iqd-fallback-missing-diagnostics",
        "ingredient_quality_data": {
            "ingredients": [],
            "ingredients_scorable": [
                _row(identity_decision_reason="form_unmapped_fallback")
            ],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.14" in rules
