import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrichment_contract_validator import EnrichmentContractValidator
from enhanced_normalizer import EnhancedDSLDNormalizer


def _f_rules(product):
    violations = EnrichmentContractValidator().validate(product)
    return [v for v in violations if v.rule.startswith("F.")]


def _h_rules(product):
    violations = EnrichmentContractValidator().validate(product)
    return [v for v in violations if v.rule.startswith("H.")]


def _normalize_label_product(*, ingredient_rows=None, other_ingredients=None):
    return EnhancedDSLDNormalizer().normalize_product(
        {
            "id": "label-ledger-producer-contract",
            "fullName": "Label Ledger Producer Contract",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": ingredient_rows or [],
            "otheringredients": {"ingredients": other_ingredients or []},
        }
    )


def test_label_ledger_omits_literal_none_placeholder_without_contract_drift():
    product = _normalize_label_product(other_ingredients=[{"name": "None"}])

    assert _h_rules(product) == []
    assert product["display_ingredients"] == []
    assert product["label_ledger_omissions"] == [
        {
            "raw_source_path": "otheringredients.ingredients[0]",
            "raw_source_text": "None",
            "omission_reason": "empty_source_text",
        }
    ]


def test_nested_nutrition_fact_is_displayed_but_never_scored():
    product = _normalize_label_product(
        ingredient_rows=[
            {
                "name": "Calories",
                "ingredientGroup": "Amount Per Serving",
                "order": 1,
                "quantity": [{"quantity": 35, "unit": "cal"}],
                "nestedRows": [
                    {
                        "name": "Calories from Fat",
                        "ingredientGroup": "Amount Per Serving",
                        "order": 2,
                        "quantity": [{"quantity": 10, "unit": "cal"}],
                    }
                ],
            }
        ]
    )

    assert _h_rules(product) == []
    rows = {
        row["raw_source_text"]: row for row in product["display_ingredients"]
    }
    assert rows["Calories"]["display_type"] == "nutrition_fact"
    assert rows["Calories from Fat"]["display_type"] == "nutrition_fact"
    assert rows["Calories"]["score_included"] is False
    assert rows["Calories from Fat"]["score_included"] is False


def test_inactive_disclosed_form_is_folded_into_parent_label_row():
    product = _normalize_label_product(
        other_ingredients=[
            {
                "name": "Gelatin",
                "forms": [{"name": "Bovine", "category": "Animal Part or Source"}],
            }
        ]
    )

    assert _h_rules(product) == []
    assert len(product["display_ingredients"]) == 1
    parent = product["display_ingredients"][0]
    assert parent["label_display_name"] == "Gelatin"
    assert parent["label_display_form"] == "Bovine"
    assert parent["form_display_state"] == "listed_not_assessed"
    assert [
        component["raw_source_text"]
        for component in parent["folded_label_components"]
    ] == ["Bovine"]


def test_structural_blend_parent_has_one_path_bound_display_row():
    product = _normalize_label_product(
        ingredient_rows=[
            {
                "name": "Organic Alkalizing Green Juice Powders",
                "ingredientGroup": "Blend (Herb/Botanical)",
                "category": "blend",
                "order": 1,
                "quantity": [{"quantity": 117, "unit": "mg"}],
                "nestedRows": [
                    {
                        "name": "Organic Wheat Grass Juice Powder",
                        "ingredientGroup": "Wheat grass",
                        "category": "botanical",
                        "order": 2,
                    }
                ],
            }
        ]
    )

    assert _h_rules(product) == []
    parent_rows = [
        row
        for row in product["display_ingredients"]
        if row["raw_source_text"] == "Organic Alkalizing Green Juice Powders"
    ]
    assert len(parent_rows) == 1
    assert parent_rows[0]["raw_source_path"] == "ingredientRows[0]"
    assert parent_rows[0]["display_type"] == "structural_container"


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
                _row(identity_decision_reason="disclosed_form_unmapped")
            ],
        },
    }

    rules = {v.rule for v in _f_rules(product)}

    assert "F.14" in rules


def test_every_cleaner_role_literal_is_in_the_one_shared_vocabulary():
    """The Cleaner must not start emitting a role its consumers cannot read.

    Four hand-kept role lists once drifted: a role the Cleaner emitted was
    missing from the Stage-2.4 copy and failed 9 brands. Every consumer now
    imports the constants.py vocabulary; this pins the producer to it too.
    """
    import re
    from pathlib import Path

    import audit_source_of_truth_contract
    import scoring_input_contract
    from constants import CLEANER_NON_SCORABLE_ROLES, CLEANER_SCORABLE_ROLES

    source = (Path(__file__).resolve().parents[1] / "enhanced_normalizer.py").read_text()
    assigned = set(re.findall(r'cleaner_row_role"?\]?\s*[:=]\s*"([a-z_]+)"', source))
    assigned |= set(re.findall(r'"(composition_leaf|nested_display_only)"\s*\n?\s*(?:if|else)', source))
    assert {"active_scorable", "standardization_marker", "blend_header_total"} <= assigned
    assert assigned <= CLEANER_SCORABLE_ROLES | CLEANER_NON_SCORABLE_ROLES

    assert EnrichmentContractValidator.CLEANER_NON_SCORABLE_ROLES is CLEANER_NON_SCORABLE_ROLES
    assert EnrichmentContractValidator.CLEANER_SCORABLE_ROLES is CLEANER_SCORABLE_ROLES
    assert scoring_input_contract.EXCLUDED_CLEANER_ROLES is CLEANER_NON_SCORABLE_ROLES
    assert scoring_input_contract.VALID_ACTIVE_ROLES is CLEANER_SCORABLE_ROLES
    assert audit_source_of_truth_contract.SCORABLE_BLOCKED_ROLES is CLEANER_NON_SCORABLE_ROLES
    assert not CLEANER_SCORABLE_ROLES & CLEANER_NON_SCORABLE_ROLES


def test_dose_class_and_identity_state_vocabularies_have_one_owner():
    import enrich_supplements_v3
    import scoring_input_contract
    from constants import IQD_DOSE_EVIDENCE_CLASSES
    from identity_integrity import IDENTITY_DISPOSITIONS

    assert EnrichmentContractValidator.VALID_IQD_DOSE_CLASSES is IQD_DOSE_EVIDENCE_CLASSES
    assert scoring_input_contract.VALID_DOSE_CLASSES is IQD_DOSE_EVIDENCE_CLASSES
    assert enrich_supplements_v3.SupplementEnricherV3._IQD_DOSE_EVIDENCE_CLASSES is IQD_DOSE_EVIDENCE_CLASSES
    assert EnrichmentContractValidator.DISPLAY_LEDGER_IDENTITY_STATES == frozenset(IDENTITY_DISPOSITIONS)
