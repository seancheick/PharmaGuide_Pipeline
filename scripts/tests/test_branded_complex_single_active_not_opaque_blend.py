#!/usr/bin/env python3
"""Branded SINGLE-active ingredients whose name ends in "Complex"/"Matrix"
must NOT be emitted as fully-opaque proprietary blends (v4 B5 root fix).

Bug (v4 scoring): the cleaner (`enhanced_normalizer`) stamps
``proprietaryBlend=True`` + ``disclosureLevel='none'`` on ANY single
ingredient whose name merely *contains* a marketing suffix token
("complex"/"matrix"/"formula"/...). The enricher's
``_collect_proprietary_data`` then turns that soft hint into an
*authoritative* opaque-blend record, so a branded single active with a
disclosed dose and no sub-ingredients is penalized by the B5 transparency
opacity penalty even though it hides nothing.

Verified evidence (enriched corpus): 183201 EpiCor, 273386 Curcumin C3
Complex, 227855 Clarinol CLA, 213448 Boron Complex, 201803/66380 Citrus
Bioflavonoid Complex — each emits
``proprietary_blends=[{disclosure_level:"none", total_weight:<dose>,
hidden_count:0, nested_count:0, child_ingredients:[], sources:["cleaning"]}]``.

ROOT FIX: a candidate with NO sub-ingredients, NO blend parent, that
resolves to ONE known canonical therapeutic ingredient (the chemical-
identity test, same predicate the scorer already trusts via
``_is_known_therapeutic``) is a branded single active — not an opaque
blend. It must NOT produce a B5-scoreable opaque-blend record.

GUARDRAIL (must stay penalized): genuine multi-ingredient blends that
disclose only a total ("Proprietary Blend", "Super Greens Blend") do NOT
resolve to a single canonical ingredient, and blends with undisclosed
nested children are structurally opaque. Both keep the penalty.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _single_active_product(name, standard_name, qty=250, unit="mg"):
    """A cleaned product carrying ONE branded single-active flagged by the
    cleaner as a proprietary blend (disclosure 'none', no sub-ingredients).

    Mirrors the real cleaned shape: scalar ``quantity``, populated
    ``standardName`` (the cleaner resolves the canonical identity), and an
    empty ``nestedIngredients`` list.
    """
    return {
        "id": "999999",
        "fullName": f"{name} Product",
        "brandName": "Test Brand",
        "activeIngredients": [
            {
                "name": name,
                "standardName": standard_name,
                "quantity": qty,
                "unit": unit,
                "proprietaryBlend": True,
                "disclosureLevel": "none",
                "nestedIngredients": [],
            }
        ],
        "inactiveIngredients": [],
    }


def _opaque_blend_entries(proprietary_data):
    return [
        b
        for b in (proprietary_data.get("blends") or [])
        if str(b.get("disclosure_level", "")).lower() == "none"
    ]


# ---------------------------------------------------------------------------
# Branded single actives — must NOT be opaque blends
# ---------------------------------------------------------------------------

# (display name, cleaner-resolved standardName) for the verified corpus cases.
SINGLE_ACTIVE_CASES = [
    ("Curcumin C3 Complex", "Curcumin"),                       # 273386
    ("EpiCor dried Yeast Fermentate Complex", "Yeast Fermentate"),  # 183201
    ("Clarinol CLA Complex", "Conjugated Linoleic Acid"),      # 227855
    ("Boron Complex", "Boron"),                                # 213448
    ("Citrus Bioflavonoid Complex", "Citrus Bioflavonoids"),   # 201803 / 66380
]


@pytest.mark.parametrize("name,standard_name", SINGLE_ACTIVE_CASES)
def test_branded_complex_single_active_not_emitted_as_opaque_blend(
    enricher, name, standard_name
):
    product = _single_active_product(name, standard_name)
    proprietary_data = enricher._collect_proprietary_data(product)

    opaque = _opaque_blend_entries(proprietary_data)
    assert opaque == [], (
        f"{name!r} resolves to one canonical ingredient ({standard_name!r}) with a "
        f"disclosed dose and no sub-ingredients — it hides nothing and must NOT be "
        f"emitted as an opaque proprietary blend. Got: {opaque!r}"
    )
    assert proprietary_data.get("has_proprietary_blends") is False


def test_curcumin_c3_complex_still_scores_as_a_real_active(enricher):
    """The fix must suppress the spurious opacity penalty WITHOUT dropping the
    ingredient from quality scoring — it is still a real, scorable active."""
    product = _single_active_product("Curcumin C3 Complex", "Curcumin")
    iqd = enricher._collect_ingredient_quality_data(product)
    rows = iqd.get("ingredients") or []
    canon = {(r.get("canonical_id") or r.get("standard_name")) for r in rows}
    assert "curcumin" in canon, (
        "Curcumin C3 Complex must remain a scorable active (canonical_id=curcumin); "
        f"got scorable canonicals {canon!r}"
    )


# ---------------------------------------------------------------------------
# Genuine opaque blends — must STAY penalized (control)
# ---------------------------------------------------------------------------


def test_generic_proprietary_blend_total_only_stays_opaque(enricher):
    """"Proprietary Blend" discloses only a total and resolves to NO single
    canonical ingredient — it is genuinely opaque and keeps the penalty."""
    product = _single_active_product("Proprietary Blend", "")
    proprietary_data = enricher._collect_proprietary_data(product)

    assert proprietary_data.get("has_proprietary_blends") is True
    assert _opaque_blend_entries(proprietary_data), (
        "A generic 'Proprietary Blend' that discloses only a total must remain a "
        "B5-scoreable opaque blend (it does not resolve to a single canonical ingredient)."
    )


def test_superfood_blend_total_only_stays_opaque(enricher):
    product = _single_active_product("Super Greens Blend", "")
    proprietary_data = enricher._collect_proprietary_data(product)

    assert proprietary_data.get("has_proprietary_blends") is True
    assert _opaque_blend_entries(proprietary_data)


def test_blend_with_undisclosed_nested_children_stays_opaque(enricher):
    """A multi-ingredient blend with named-but-undosed children is structurally
    opaque regardless of any canonical name match — keep the penalty."""
    product = {
        "id": "999998",
        "fullName": "Joint Support Product",
        "brandName": "Test Brand",
        "activeIngredients": [
            {
                "name": "Joint Support Blend",
                "standardName": "",
                "quantity": 1500,
                "unit": "mg",
                "proprietaryBlend": True,
                "disclosureLevel": "none",
                "nestedIngredients": [
                    {"name": "Glucosamine", "quantity": 0, "unit": "NP"},
                    {"name": "Chondroitin", "quantity": 0, "unit": "NP"},
                    {"name": "MSM", "quantity": 0, "unit": "NP"},
                ],
            }
        ],
        "inactiveIngredients": [],
    }
    proprietary_data = enricher._collect_proprietary_data(product)

    assert proprietary_data.get("has_proprietary_blends") is True
    opaque = _opaque_blend_entries(proprietary_data)
    assert opaque, "A blend with undisclosed nested children must stay opaque."
    assert any((b.get("hidden_count") or 0) >= 1 for b in opaque)


@pytest.fixture(scope="module")
def preparation_labels():
    import json
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    products = {}
    for pid in ("231852", "219249", "201405", "246073", "302668", "277667", "243050", "307567", "188685", "69759"):
        raw = json.loads((Path(__file__).parent / "fixtures" / f"blend_preparation_{pid}_raw.json").read_text())
        cleaned = normalizer.normalize_product(raw)
        enriched, _ = enricher.enrich_product(cleaned)
        scored = build_scored_artifact(enriched)
        products[pid] = (cleaned, enriched, scored, build_detail_blob(enriched, scored))
    return products


@pytest.mark.parametrize("pid,ref,canonical,amount", [
    ("231852", "ingredientRows[3]", "shilajit", 200),
    ("219249", "ingredientRows[4]", "collagen", 20),
])
def test_exact_preparation_is_not_a_generic_blend_total(preparation_labels, pid, ref, canonical, amount):
    cleaned, enriched, scored, blob = preparation_labels[pid]
    [row] = [x for x in cleaned["activeIngredients"] if x["raw_source_path"] == ref]
    assert row["canonical_id"] == canonical
    assert row["quantity"] == amount and row["unit"] == "mg"
    assert row["cleaner_row_role"] == "active_scorable"
    assert row["proprietaryBlend"] is False
    assert not any(x.get("source_row_ref") == ref for x in enriched["proprietary_data"]["blends"])
    if pid == "231852":
        transparency = scored["_v4_module_breakdown"]["dimensions"]["transparency"]
        assert transparency["penalties"]["B5_proprietary_blend_opacity"] == 0
        assert transparency["metadata"]["complete_active_disclosure"]["complete_row_count"] == 2
        assert blob["proprietary_blend_detail"]["has_proprietary_blends"] is False
        assert [x["quantity"] for x in cleaned["activeIngredients"]] == [200, 200]


@pytest.mark.parametrize("pid,ref", [("201405", "ingredientRows[0]"), ("243050", "ingredientRows[11]")])
def test_nutrient_source_form_is_not_an_independent_opaque_formula(preparation_labels, pid, ref):
    cleaned, enriched, _, _ = preparation_labels[pid]
    # Select the literal printed nutrient, not a blend/category alias.
    nutrient = "Potassium" if pid == "201405" else "Chromium"
    [row] = [x for x in cleaned["activeIngredients"] if x["name"] == nutrient]
    assert row["quantity"] > 0
    assert not any(x.get("source_row_ref") == row["raw_source_path"] for x in enriched["proprietary_data"]["blends"])


def test_quantified_biocell_source_constituents_remain_disclosed(preparation_labels):
    _, enriched, _, blob = preparation_labels["246073"]
    blends = [x for x in blob["proprietary_blend_detail"]["blends"] if x.get("source_row_ref") == "ingredientRows[2]"]
    assert blends and all(x["disclosure_level"] == "full" for x in blends)
    assert sorted(x["amount"] for x in blends[0]["child_ingredients"]) == [50, 100, 300]


@pytest.mark.parametrize("pid,units", [("302668", {"HUT", "SAPU", "DPPIV"}), ("277667", {"PC", "LU", "DU", "ALU", "CU"})])
def test_printed_enzyme_activity_is_disclosure_without_mass_conversion(preparation_labels, pid, units):
    _, enriched, _, _ = preparation_labels[pid]
    blends = [x for x in enriched["proprietary_data"]["blends"] if x.get("source_row_ref") == "ingredientRows[0]"]
    assert len(blends) == 1
    assert blends[0]["disclosure_level"] == "full"
    assert {x["unit"] for x in blends[0]["child_ingredients"]} == units
    assert all(x["amount"] > 0 for x in blends[0]["child_ingredients"])


def test_genuine_tamaflex_formula_keeps_its_member_limitation(preparation_labels):
    _, enriched, _, _ = preparation_labels["219249"]
    blends = [x for x in enriched["proprietary_data"]["blends"] if x.get("source_row_ref") == "ingredientRows[3]"]
    assert blends and all(x["disclosure_level"] != "full" for x in blends)
    assert any(x.get("hidden_count", 0) > 0 for x in blends)


@pytest.mark.parametrize("pid,ref", [
    ("307567", "ingredientRows[0]"), ("188685", "ingredientRows[2]"),
    ("69759", "ingredientRows[36].nestedRows[0].nestedRows[0]"),
])
def test_explicit_mixture_context_retains_a_real_opacity_penalty(preparation_labels, pid, ref):
    _, enriched, scored, _ = preparation_labels[pid]
    # A recognized ingredient/assay total does not disclose the other active
    # material (myrosinase) or the members of a protease-source mixture.
    evidence = scored["_v4_module_breakdown"]["dimensions"]["transparency"]["metadata"]["B5_blend_evidence"]
    assert any(x.get("source_row_ref") == ref and x["computed_blend_penalty_magnitude"] > 0 for x in evidence)
    assert enriched["proprietary_data"]["has_proprietary_blends"] is True


def test_a_named_ingredient_amount_is_not_an_unquantified_mixture_total(preparation_labels):
    cleaned, enriched, _, _ = preparation_labels['307567']
    [source] = [r for r in cleaned['activeIngredients'] if r['raw_source_path'] == 'ingredientRows[0]']
    assert source['quantity'] == 35 and source['unit'] == 'mg'
    blends = [r for r in enriched['proprietary_data']['blends'] if r.get('source_row_ref') == 'ingredientRows[0]']
    assert blends
    assert all(r['blend_total_mg'] is None for r in blends)
