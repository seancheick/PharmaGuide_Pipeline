"""A blend whose own children are exactly the nine EAAs is an EAA total.

GNC Essential Amino Acids (66953) prints "Micro-Peptide Essential Amino
Complex 1,600 mg" over L-Histidine, L-Isoleucine, L-Leucine, L-Lysine,
L-Methionine, L-Phenylalanine, L-Threonine, L-Tryptophan and L-Valine (no
amounts), plus a separate "hydrolyzed Whey Peptide Complex 100 mg". The EAA
aggregate owner (`scoring_input_contract._derive_explicit_eaa_aggregate_evidence`)
accepted only the header names "Essential Amino Acids" and variants, so the
complex got a name-slug identity, its 1.6 g was lent to L-Histidine, and sports
Dose scored the 100 mg whey line instead. The header's own composition proves
the identity; the amounts of each amino acid stay undisclosed.
"""
import copy
import json
import logging

import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _enrich(raw):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]


def _raw():
    return json.loads((FIXTURES / "eaa_66953_raw.json").read_text())


def test_the_complex_is_scored_as_an_eaa_total():
    # Which primary wins is a separate question: the protein band credits the
    # 100 mg whey line a flat 8 below 15 g (Dose-model proposal, 2026-09-28).
    from scoring_v4.modules.sports_dose import _score_primary

    score, basis = _score_primary(_enrich(_raw()), "eaa")
    assert basis == "eaa_under_5_g" and score > 0


def test_no_amino_acid_borrows_the_complex_total():
    from scoring_input_contract import is_lent_blend_mass
    from scoring_v4.modules.generic_helpers import get_active_ingredients

    assert not [r["name"] for r in get_active_ingredients(_enrich(_raw())) if is_lent_blend_mass(r)]


def test_a_complex_with_a_non_eaa_child_is_not_an_eaa_total():
    raw = _raw()
    header = raw["ingredientRows"][0]
    extra = copy.deepcopy(header["nestedRows"][0])
    extra.update(name="Taurine", ingredientGroup="Taurine", ingredientId=999999, order=99)
    header["nestedRows"].append(extra)
    from scoring_v4.modules.sports_dose import _score_primary

    assert _score_primary(_enrich(raw), "eaa")[1] == "eaa_incomplete_under_6"


@pytest.fixture(scope="module")
def eaa_product():
    return _enrich(_raw())


def test_the_declared_eaa_product_owns_the_sports_primary(eaa_product):
    from scoring_input_contract import classify_ingredient_roles, get_scoring_ingredients
    from scoring_v4.modules.sports_helpers import primary_sports_identity, sports_subtype
    from scoring_v4.scored_artifact import build_scored_artifact

    rows = get_scoring_ingredients(eaa_product).rows
    roles = {role["canonical_id"]: role for role in
             classify_ingredient_roles(eaa_product, module="sports", rows=rows)}
    assert roles["essential_amino_acids"]["role"] == "primary"
    assert roles["whey_protein"]["role"] == "adjunct"
    assert primary_sports_identity(eaa_product) == "eaa"
    assert sports_subtype(eaa_product) == "bcaa_eaa"
    artifact = build_scored_artifact(eaa_product)
    assert artifact["quality_pillars_v4"]["dose"]["components"]["archetype"] == "sports_bcaa_eaa"
    dose = artifact["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]
    assert dose["primary_identity"] == "eaa"
    assert dose["dose_basis"].startswith("eaa_")


@pytest.mark.parametrize("protein_amount", [None, 0, 100, 10000])
def test_named_amino_mixture_primary_does_not_depend_on_protein_mass(protein_amount):
    from scoring_input_contract import classify_ingredient_roles, get_scoring_ingredients
    from scoring_v4.modules.sports_helpers import primary_sports_identity, sports_subtype
    from scoring_v4.modules.sports_dose import score_dose

    raw = _raw()
    whey = raw["ingredientRows"][1]
    if protein_amount is None:
        whey["quantity"] = []
    else:
        for quantity in whey["quantity"]:
            quantity["quantity"] = protein_amount
    product = _enrich(raw)
    rows = get_scoring_ingredients(product).rows
    roles = classify_ingredient_roles(product, module="sports", rows=rows)
    assert next(r for r in roles if r["canonical_id"] == "essential_amino_acids")["role"] == "primary"
    assert all(r["role"] not in {"primary", "claim_prominent"}
               for r in roles if r["canonical_id"] == "whey_protein")
    assert primary_sports_identity(product) == "eaa"
    assert sports_subtype(product) == "bcaa_eaa"
    assert score_dose(product)["metadata"]["primary_identity"] == "eaa"
