"""Omega router fix — a confident ``omega_3`` taxonomy with a real (trustworthy)
EPA/DHA row must route to the omega module even when the label also discloses
companion fatty acids (omega-6/9, GLA, DPA) that dilute EPA/DHA below the
primary-omega-panel count threshold (``_route_has_primary_omega_panel`` >= 50%).

Real-catalog regressions in the 2026-06-15 shipped build (all ``primary_type``
== ``omega_3`` marine fish oils, all wrongly routed ``generic`` and scored by the
generic rubric instead of the EPA/DHA omega rubric):

  Nordic Naturals Complete Omega Lemon (214233) — EPA 270 + DHA 180 + omega-6 240
    + GLA 70 + omega-9 225  ->  EPA/DHA = 2 of 5 rows (40%)  ->  fell below the gate
  Nordic Naturals Complete Omega-D3 / Jr / Xtra, ProEFA Junior (206027),
  GNC AMP Complete Omega (222789), Minami VeganDHA (28661).

Companion fatty acids are intrinsic to fish/marine oils — they must not demote a
real EPA/DHA product to generic. The fix is gated on ``primary_type == omega_3``
AND a *trustworthy* EPA/DHA row, so every existing guard still holds:
  * incidental DHA in a true multivitamin stays multi (primary_type != omega_3),
  * plant ALA 'omega-3' (flax/chia/hemp) stays generic (not trustworthy / plant-guard),
  * pure EPA/DHA panels stay omega (unchanged).
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


def _complete_omega(name="Complete Omega Lemon", brand="Nordic Naturals", extra=None):
    rows = [
        {"canonical_id": "epa", "name": "Eicosapentaenoic Acid", "quantity": 270, "unit": "mg"},
        {"canonical_id": "dha", "name": "Docosahexaenoic Acid", "quantity": 180, "unit": "mg"},
        {"canonical_id": "omega_6_fatty_acids", "name": "Omega-6 Fatty Acids", "quantity": 240, "unit": "mg"},
        {"canonical_id": "gamma_linolenic_acid", "name": "Gamma-Linolenic Acid", "quantity": 70, "unit": "mg"},
        {"canonical_id": "omega_9_fatty_acids", "name": "Omega-9 Fatty Acids", "quantity": 225, "unit": "mg"},
    ]
    if extra:
        rows.extend(extra)
    return {"product_name": name, "brand_name": brand, "primary_type": "omega_3", **_rows(rows)}


# --- the bug: confident omega_3 fish oils with companion fatty acids ---

def test_complete_omega_with_companion_fatty_acids_routes_omega():
    # EPA/DHA = 2 of 5 rows (40%) -> below the 50% primary-panel gate, but the
    # confident omega_3 taxonomy + trustworthy EPA/DHA must still route omega.
    assert class_for_product(_complete_omega()) == "omega"


def test_proefa_junior_with_parent_and_companions_routes_omega():
    p = _complete_omega(
        name="ProEFA Junior",
        extra=[{"canonical_id": "fish_oil", "name": "Fish Oil", "quantity": 283, "unit": "mg"}],
    )
    assert class_for_product(p) == "omega"


def test_vegandha_dha_plus_dpa_routes_omega():
    p = {
        "product_name": "VeganDHA",
        "brand_name": "Minami Nutrition",
        "primary_type": "omega_3",
        **_rows([
            {"canonical_id": "dha", "name": "DHA", "quantity": 400, "unit": "mg"},
            {"canonical_id": "docosapentaenoic_acid_dpa", "name": "DPA", "quantity": 140, "unit": "mg"},
        ]),
    }
    assert class_for_product(p) == "omega"


def test_algal_dha_with_astaxanthin_adjunct_routes_omega():
    # Real Minami VeganDHA (dsld 28661): DHA 400 + DPA 140 + a trace 1.5 mg
    # astaxanthin antioxidant adjunct. Astaxanthin is a soft omega adjunct, so the
    # product stays an omega-3 product, not generic.
    p = {
        "product_name": "VeganDHA",
        "brand_name": "Minami Nutrition",
        "primary_type": "omega_3",
        **_rows([
            {"canonical_id": "dha", "name": "DHA", "quantity": 400, "unit": "mg"},
            {"canonical_id": "docosapentaenoic_acid_dpa", "name": "DPA", "quantity": 140, "unit": "mg"},
            {"canonical_id": "astaxanthin", "name": "Astaxanthin", "quantity": 1.5, "unit": "mg"},
        ]),
    }
    assert class_for_product(p) == "omega"


# --- guards: the fix must NOT broaden routing for these ---

def test_incidental_dha_in_multivitamin_does_not_route_omega():
    p = {
        "product_name": "Daily Multivitamin",
        "brand_name": "BrandX",
        "primary_type": "multivitamin",
        **_rows([
            {"canonical_id": "vitamin_a", "quantity": 900, "unit": "mcg"},
            {"canonical_id": "vitamin_c", "quantity": 90, "unit": "mg"},
            {"canonical_id": "vitamin_d", "quantity": 20, "unit": "mcg"},
            {"canonical_id": "zinc", "quantity": 11, "unit": "mg"},
            {"canonical_id": "iron", "quantity": 18, "unit": "mg"},
            {"canonical_id": "dha", "quantity": 50, "unit": "mg"},
        ]),
    }
    assert class_for_product(p) != "omega"


def test_plant_ala_flax_omega3_stays_generic():
    p = {
        "product_name": "Flax Oil Omega-3",
        "brand_name": "BrandX",
        "primary_type": "omega_3",
        **_rows([
            {"canonical_id": "alpha_linolenic_acid", "name": "Flaxseed Oil (ALA)", "quantity": 1000, "unit": "mg"},
        ]),
    }
    assert class_for_product(p) == "generic"


def test_mislabeled_flax_as_epa_stays_generic():
    # Even if a flax row is mis-canonicalized to 'epa', its source text is flax,
    # so it is not a trustworthy EPA/DHA row -> generic.
    p = {
        "product_name": "Flax Oil",
        "brand_name": "BrandX",
        "primary_type": "omega_3",
        **_rows([
            {
                "canonical_id": "epa",
                "name": "Flaxseed Oil",
                "raw_source_text": "Organic Flaxseed Oil",
                "quantity": 1000,
                "unit": "mg",
            },
        ]),
    }
    assert class_for_product(p) == "generic"


def test_pure_epa_dha_panel_still_routes_omega():
    p = {
        "product_name": "Ultimate Omega",
        "brand_name": "Nordic Naturals",
        "primary_type": "omega_3",
        **_rows([
            {"canonical_id": "epa", "quantity": 650, "unit": "mg"},
            {"canonical_id": "dha", "quantity": 450, "unit": "mg"},
        ]),
    }
    assert class_for_product(p) == "omega"
