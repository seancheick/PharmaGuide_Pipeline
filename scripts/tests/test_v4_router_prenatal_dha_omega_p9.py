"""Phase 9.5 router fix — a single-purpose 'Prenatal DHA' (actives are primarily
EPA/DHA) is an OMEGA supplement, not an incomplete prenatal multivitamin. The
prenatal name keyword must not pull it into multi_or_prenatal, where the
prenatal-panel-coverage dose scorer crushes it for lacking folate/iron it was
never meant to contain (Thorne Prenatal DHA 650mg -> POOR before this fix).
A real prenatal MULTI (broad nutrient panel) still routes multi_or_prenatal.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scoring_v4.router import class_for_product  # noqa: E402


def _rows(rows):
    return {"ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows}}


def test_prenatal_dha_omega_only_routes_omega():
    # Thorne Prenatal DHA: only DHA + EPA -> omega panel is all rows -> omega
    product = {
        "product_name": "Prenatal DHA 650 mg",
        "brand_name": "Thorne",
        "primary_type": "omega_3",
        **_rows([
            {"canonical_id": "dha", "quantity": 650, "unit": "mg"},
            {"canonical_id": "epa", "quantity": 200, "unit": "mg"},
        ]),
    }
    assert class_for_product(product) == "omega"


def test_full_prenatal_multivitamin_stays_multi():
    # A real prenatal multi: broad nutrient panel, DHA is a minority of rows
    product = {
        "product_name": "Complete Prenatal Multivitamin",
        "brand_name": "BrandX",
        "primary_type": "multivitamin",
        **_rows([
            {"canonical_id": "folate", "quantity": 800, "unit": "mcg"},
            {"canonical_id": "iron", "quantity": 27, "unit": "mg"},
            {"canonical_id": "iodine", "quantity": 150, "unit": "mcg"},
            {"canonical_id": "choline", "quantity": 55, "unit": "mg"},
            {"canonical_id": "dha", "quantity": 200, "unit": "mg"},
        ]),
    }
    assert class_for_product(product) == "multi_or_prenatal"
