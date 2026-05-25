"""v4 greens routing locks.

Greens/superfood products can contain probiotic strains, but taxonomy
primary_type remains the class contract until a dedicated greens module ships.
The probiotic-data fallback must not override explicit greens taxonomy.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def test_greens_primary_type_with_probiotic_data_routes_generic_until_greens_module() -> None:
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Raw Organic Perfect Food Green Superfood",
        "primary_type": "greens_powder",
        "supplement_taxonomy": {"primary_type": "greens_powder"},
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 2,
            "has_cfu": True,
            "total_cfu": 1500000000,
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Organic Greens Blend",
                    "canonical_id": "wheatgrass",
                    "quantity": 1000,
                    "unit": "mg",
                }
            ]
        },
    }

    assert class_for_product(product) == "generic"


def test_explicit_probiotic_primary_type_still_routes_probiotic() -> None:
    from scoring_v4.router import class_for_product

    product = {
        "product_name": "Probiotic Greens",
        "primary_type": "probiotic",
        "supplement_taxonomy": {"primary_type": "probiotic"},
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 2,
            "has_cfu": True,
            "total_cfu": 1500000000,
        },
    }

    assert class_for_product(product) == "probiotic"
