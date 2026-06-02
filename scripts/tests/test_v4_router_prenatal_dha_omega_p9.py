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


def test_prenatal_herbal_support_does_not_route_to_full_prenatal_multi():
    # Real-catalog pattern: "Prenatal Tummy Comfort" is an herbal support SKU,
    # not a prenatal multivitamin. Prenatal wording alone must not invoke the
    # folate/iron/iodine/choline/DHA floor.
    product = {
        "product_name": "Prenatal Tummy Comfort",
        "brand_name": "GNC Women's",
        "primary_type": "herbal_botanical",
        **_rows([
            {"canonical_id": "vitamin_b6_pyridoxine", "quantity": 25, "unit": "mg"},
            {"canonical_id": "peppermint", "quantity": 40, "unit": "mg"},
            {"canonical_id": "ginger", "quantity": 30, "unit": "mg"},
        ]),
    }
    assert class_for_product(product) == "generic"


def test_prenatal_bundle_name_does_not_force_single_mineral_to_multi():
    # Real-catalog pattern: a single Calcium 600 product can live in a prenatal
    # program/bundle. The product itself is still a single-mineral supplement.
    product = {
        "product_name": "Calcium 600",
        "fullName": "Calcium 600",
        "brand_name": "GNC Women's",
        "bundleName": "Prenatal Program",
        "primary_type": "single_mineral",
        **_rows([
            {"canonical_id": "calcium", "quantity": 600, "unit": "mg"},
        ]),
    }
    assert class_for_product(product) == "generic"


def test_underclassified_broad_prenatal_panel_still_routes_multi():
    # If taxonomy under-classifies a real prenatal multi, panel breadth plus
    # prenatal label intent is enough to route to the multi/prenatal rubric.
    product = {
        "product_name": "Prenatal Gummies",
        "primary_type": "general_supplement",
        **_rows([
            {"canonical_id": "vitamin_b9_folate", "quantity": 600, "unit": "mcg"},
            {"canonical_id": "iron", "quantity": 18, "unit": "mg"},
            {"canonical_id": "iodine", "quantity": 150, "unit": "mcg"},
            {"canonical_id": "vitamin_d", "quantity": 25, "unit": "mcg"},
            {"canonical_id": "vitamin_b12_cobalamin", "quantity": 4, "unit": "mcg"},
            {"canonical_id": "zinc", "quantity": 5, "unit": "mg"},
        ]),
    }
    assert class_for_product(product) == "multi_or_prenatal"


def test_bundle_only_prenatal_dha_component_does_not_route_multi():
    # Real-catalog pattern: product label is just DHA, while the bundle says
    # "DHA Prenatal Multivitamin". Bundle context must not make the DHA
    # component look like a full prenatal multi.
    product = {
        "product_name": "DHA",
        "fullName": "DHA",
        "brand_name": "CVS Pharmacy",
        "bundleName": "DHA Prenatal Multivitamin",
        "primary_type": "general_supplement",
        **_rows([]),
    }
    assert class_for_product(product) == "omega"
