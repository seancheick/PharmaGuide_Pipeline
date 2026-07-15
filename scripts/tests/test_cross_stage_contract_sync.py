"""Producer/consumer fields stay aligned across enrich, validate, and score (G3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from enrichment_contract_validator import EnrichmentContractValidator
from score_supplements import SupplementScorer


def test_validator_reads_top_level_canonical_form_factor() -> None:
    product = {
        "id": "gummy-contract",
        "form_factor": "gummy",
        "form_factor_canonical": "gummy",
        "serving_basis": {
            "basis_unit": "gummy(ie",
            "canonical_serving_size_quantity": 2,
        },
        "match_ledger": {"domains": {}, "summary": {}},
    }

    violations = EnrichmentContractValidator().validate(product)

    assert any(violation.rule == "D.1a" for violation in violations)


def test_ingredient_allergens_use_bounded_alias_evidence() -> None:
    enricher = SupplementEnricherV3()

    result = enricher._check_allergens(
        [
            {"name": "Whey Protein Isolate", "standardName": "Whey Protein"},
            {"name": "Sodium Caseinate", "standardName": "Sodium Caseinate"},
        ],
        {"activeIngredients": [], "inactiveIngredients": []},
    )

    assert any(row["allergen_name"].lower() == "milk" for row in result["allergens"])


def test_manufacturing_region_emits_country_not_regex_phrase() -> None:
    enricher = SupplementEnricherV3()

    result = enricher._extract_country({"fullName": "Made in Germany"})

    assert result["country"] == "Germany"


def test_inactive_ledger_source_section_can_trigger_mapping_flag() -> None:
    scorer = SupplementScorer()
    product = {
        "ingredient_quality_data": {
            "ingredients": [{
                "name": "Vitamin C", "canonical_id": "vitamin_c", "mapped": True,
                "quantity": 100, "unit": "mg", "has_dose": True,
            }],
            "ingredients_scorable": [{
                "name": "Vitamin C", "canonical_id": "vitamin_c", "mapped": True,
                "quantity": 100, "unit": "mg", "has_dose": True,
            }],
        },
        "match_ledger": {"domains": {"ingredients": {"entries": [{
            "decision": "unmatched",
            "source_section": "inactive",
            "raw_source_path": "",
        }]}}},
    }

    gate = scorer._mapping_gate(product)

    assert "UNMAPPED_INACTIVE_INGREDIENT" in gate["flags"]
