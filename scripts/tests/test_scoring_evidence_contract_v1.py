from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from score_supplements_v4 import score_product_v4  # noqa: E402
from scoring_input_contract import get_scoring_ingredients  # noqa: E402
from scoring_input_contract import derive_product_scoring_evidence  # noqa: E402
from scoring_v4.router import class_for_product  # noqa: E402


def _load_product(dsld_id: str) -> dict:
    for path in (SCRIPTS_ROOT / "products").glob("output_*_enriched/enriched/*.json"):
        payload = json.loads(path.read_text())
        products = payload if isinstance(payload, list) else payload.get("products", [])
        for product in products:
            if str(product.get("dsld_id") or product.get("id")) == dsld_id:
                return product
    raise AssertionError(f"Could not find enriched product {dsld_id}")


def _evidence_rows(product: dict, evidence_type: str) -> list[dict]:
    result = get_scoring_ingredients(product, strict=True)
    return [
        row for row in result.rows
        if row.get("scoring_input_kind") == "product_level_evidence"
        and row.get("evidence_type") == evidence_type
    ]


def test_protein_macro_reaches_v4_as_sports_primary_dose_evidence() -> None:
    product = _load_product("180692")

    rows = _evidence_rows(product, "sports_primary_dose")
    assert rows, "Protein macro dose must be normalized into ScoringEvidence v1"
    assert max(float(row["quantity"]) for row in rows) >= 19.0

    out = score_product_v4(product)
    assert out["v4_verdict"] != "NOT_SCORED"


def test_omega_aggregate_and_forms_reach_v4_as_epa_dha_evidence() -> None:
    for dsld_id, minimum in (("13801", 750.0), ("26691", 500.0), ("259484", 4.5)):
        product = _load_product(dsld_id)

        rows = _evidence_rows(product, "omega_epa_dha_aggregate")
        assert rows, f"{dsld_id} must emit omega EPA/DHA aggregate evidence"
        assert max(float(row["quantity"]) for row in rows) >= minimum

        out = score_product_v4(product)
        assert out["v4_verdict"] != "NOT_SCORED"


def test_vitamin_carried_in_fish_oil_does_not_emit_omega_evidence() -> None:
    product = {
        "product_name": "Vitamin A 3,000 mcg",
        "primary_type": "single_vitamin",
        "supplement_taxonomy": {"primary_type": "single_vitamin"},
        "activeIngredients": [
            {
                "name": "Vitamin A",
                "standardName": "Fish Oil",
                "raw_source_text": "Vitamin A",
                "canonical_id": "vitamin_a",
                "quantity": 3000.0,
                "unit": "mcg",
                "raw_source_path": "ingredientRows[0]",
                "forms": [{"name": "from Norwegian Cod Liver Oil"}],
            }
        ],
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Vitamin A",
                    "canonical_id": "vitamin_a",
                    "quantity": 3000.0,
                    "unit": "mcg",
                    "raw_source_path": "ingredientRows[0]",
                    "mapped": True,
                }
            ]
        },
    }

    assert not [
        row for row in derive_product_scoring_evidence(product)
        if row.get("evidence_type") == "omega_epa_dha_aggregate"
    ]
    assert class_for_product(product) == "generic"


def test_enzyme_activity_reaches_v4_as_non_mass_dose_evidence() -> None:
    product = _load_product("293966")

    rows = _evidence_rows(product, "enzyme_activity")
    assert rows, "PPI/ALU/BLGU activity units must be scoring evidence"
    assert any(str(row.get("unit")).lower() == "ppi" for row in rows)

    out = score_product_v4(product)
    assert out["v4_verdict"] != "NOT_SCORED"


def test_galu_enzyme_activity_reaches_v4_as_non_mass_dose_evidence() -> None:
    """Alpha-galactosidase products commonly disclose GALU activity units.
    GALU is a real enzyme activity unit and must not be treated as no dose.
    """
    product = {
        "product_name": "Beanaid",
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Alpha-Galactosidase",
                    "standard_name": "Digestive Enzymes",
                    "canonical_id": "digestive_enzymes",
                    "mapped": True,
                    "quantity": 0,
                    "unit": "NP",
                    "notes": "Alpha Galactosidase (Form: Aspergillus niger) Note: 300 GALU",
                    "raw_source_text": "Alpha-Galactosidase",
                    "raw_source_path": "ingredientRows[0]",
                    "cleaner_row_role": "active_scorable",
                    "score_eligible_by_cleaner": True,
                    "score_exclusion_reason": None,
                }
            ],
        },
    }

    rows = [
        row for row in derive_product_scoring_evidence(product)
        if row.get("evidence_type") == "enzyme_activity"
    ]

    assert rows
    assert rows[0]["dose_value"] == 300.0
    assert rows[0]["dose_unit"] == "GALU"
    assert rows[0]["dose_class"] == "enzyme_activity"


def test_single_active_title_embedded_mass_reaches_v4_as_low_confidence_dose_evidence() -> None:
    product = {
        "product_name": "Tocotrienols 50 mg",
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Tocotrienol-Tocopherol Complex",
                    "standard_name": "Tocotrienols",
                    "canonical_id": "vitamin_e",
                    "mapped": True,
                    "quantity": 0,
                    "unit": "NP",
                    "raw_source_text": "Tocotrienol-Tocopherol Complex",
                    "raw_source_path": "ingredientRows[0]",
                    "cleaner_row_role": "active_scorable",
                    "score_eligible_by_cleaner": True,
                    "score_exclusion_reason": None,
                }
            ],
        },
    }

    rows = [
        row for row in derive_product_scoring_evidence(product)
        if row.get("reason") == "single_active_title_embedded_mass"
    ]

    assert rows
    assert rows[0]["dose_value"] == 50.0
    assert rows[0]["dose_unit"].lower() == "mg"
    assert rows[0]["confidence"] == "low"


def test_title_embedded_mass_does_not_apply_to_multi_identity_oil_titles() -> None:
    product = {
        "product_name": "1300 mg Omega 3-6-9 Fish, Flax, Borage",
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Fish Oil",
                    "canonical_id": "fish_oil",
                    "mapped": True,
                    "quantity": 0,
                    "unit": "NP",
                    "raw_source_path": "ingredientRows[0]",
                    "cleaner_row_role": "active_scorable",
                    "score_eligible_by_cleaner": True,
                },
                {
                    "name": "Flaxseed Oil",
                    "canonical_id": "flaxseed",
                    "mapped": True,
                    "quantity": 0,
                    "unit": "NP",
                    "raw_source_path": "ingredientRows[1]",
                    "cleaner_row_role": "active_scorable",
                    "score_eligible_by_cleaner": True,
                },
            ],
        },
    }

    assert not [
        row for row in derive_product_scoring_evidence(product)
        if row.get("reason") == "single_active_title_embedded_mass"
    ]


def test_identity_bearing_blend_total_reaches_v4_as_anchor_mass_evidence() -> None:
    product = _load_product("309492")

    rows = _evidence_rows(product, "blend_anchor_mass")
    assert rows, "Identity-bearing blend totals must not disappear from scoring"
    assert rows[0]["canonical_id"] == "quercetin"
    assert float(rows[0]["quantity"]) >= 300.0

    out = score_product_v4(product)
    assert out["v4_verdict"] == "SAFE"
    completeness = out["v4_breakdown"]["completeness_gate"]
    assert "conservative_blend_anchor_mass" in completeness["soft_missing"]
    assert completeness["score_cap"] is None
    assert completeness["verdict_ceiling"] is None


def test_percent_dv_only_dose_counts_as_conservative_dose_evidence() -> None:
    product = _load_product("76510")

    out = score_product_v4(product)
    assert out["v4_verdict"] != "NOT_SCORED"


def test_cod_liver_oil_in_forms_does_not_emit_omega_evidence() -> None:
    """Carrier text in forms[] must not create omega evidence (forms-array path)."""
    product = {
        "product_name": "Vitamin D3 1000 IU",
        "primary_type": "single_vitamin",
        "supplement_taxonomy": {"primary_type": "single_vitamin"},
        "activeIngredients": [
            {
                "name": "Vitamin D3",
                "standardName": "Cholecalciferol",
                "raw_source_text": "Vitamin D3",
                "canonical_id": "vitamin_d",
                "quantity": 25.0,
                "unit": "mcg",
                "raw_source_path": "ingredientRows[0]",
                "forms": [{"name": "from Cod Liver Oil"}],
            }
        ],
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Vitamin D3",
                    "canonical_id": "vitamin_d",
                    "quantity": 25.0,
                    "unit": "mcg",
                    "raw_source_path": "ingredientRows[0]",
                    "mapped": True,
                }
            ]
        },
    }
    omega_rows = [
        row for row in derive_product_scoring_evidence(product)
        if row.get("evidence_type") == "omega_epa_dha_aggregate"
    ]
    assert not omega_rows, "Carrier text 'from Cod Liver Oil' in forms must not emit omega evidence"


def test_enzyme_evidence_carries_new_identity_fields() -> None:
    """Enzyme evidence rows carry the new identity chain fields."""
    product = _load_product("293966")

    result = get_scoring_ingredients(product, strict=True)
    enzyme_rows = [
        row for row in result.rows
        if row.get("scoring_input_kind") == "product_level_evidence"
        and row.get("evidence_type") == "enzyme_activity"
    ]
    assert enzyme_rows, "Must have enzyme_activity evidence rows"
    for row in enzyme_rows:
        assert row.get("evidence_origin") == "compatibility_derived"
        assert row.get("dose_class") == "enzyme_activity"
        assert "clean_identity_id" in row
        assert "scoring_parent_id" in row
        assert "evidence_canonical_id" in row
