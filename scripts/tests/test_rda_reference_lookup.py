"""Reference lookup must resolve a label name to the SAME compound, never a substring.

The old partial-name fallback returned the first reference whose key appeared
inside the name, so "TMG (Trimethylglycine)" was dosed against glycine's 3 g
anchor and "Echinacea" against NAC ("nac" is inside "echinacea").
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rda_ul_calculator import RDAULCalculator
from scoring_v4.modules import generic_dose

SCRIPTS = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def calculator() -> RDAULCalculator:
    return RDAULCalculator()


def _resolved_id(calculator: RDAULCalculator, name: str):
    hit = calculator._find_nutrient(name)
    return hit.get("id") if hit else None


@pytest.mark.parametrize(
    "name, expected",
    [
        ("TMG (Trimethylglycine)", "betaine_tmg"),
        ("Vitamin B1 (Thiamine)", "thiamin"),
        ("Vitamin B2 (Riboflavin)", "riboflavin"),
        ("Vitamin B3 (Niacin)", "niacin"),
        ("Vitamin B5 (Pantothenic Acid)", "pantothenic_acid"),
        ("Vitamin B6 (Pyridoxine)", "vitamin_b6"),
        ("Vitamin B7 (Biotin)", "biotin"),
        ("Vitamin B9 (Folate)", "folate"),
        ("Vitamin K1", "vitamin_k"),
        ("Vitamin K2", "vitamin_k"),
        ("Vitamin D3", "vitamin_d"),
        ("Vitamin D2", "vitamin_d"),
        ("GABA (Gamma-Aminobutyric Acid)", "gaba_gamma_aminobutyric_acid"),
        ("L-Glycine", "glycine"),
        ("Diindolylmethane (DIM)", "dim_diindolylmethane"),
        ("SAMe (S-Adenosyl-L-Methionine)", "sam_e_s_adenosyl_methionine"),
    ],
)
def test_same_compound_names_resolve(calculator, name, expected) -> None:
    assert _resolved_id(calculator, name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "Echinacea",
        "Echinacea Purpurea Root Extract",
        "DMAE (Dimethylaminoethanol)",
        "Dimethyl Glycine",
        "Malate",
        "Butyric Acid",
        "Phosphatidylcholine",
        "Phosphatidylinositol",
        "Inositol Hexaphosphate (IP6)",
        "Soybean (Glycine Max)",
        "Velositol (Amylopectin-Chromium Complex)",
        "Salt (Sodium Chloride)",
        "Oil Vehicle (Non-Active)",
        "Sodium Magnesium Chlorophyllin",
        "Agmatine Sulfate",
        "Vanadyl Sulfate",
        "Calcium D-Glucarate",
        "Calcium Pyruvate",
        "Sesame Seed Oil",
        "Glutathione Peroxidase",
    ],
)
def test_different_compounds_do_not_borrow_a_reference(calculator, name) -> None:
    assert _resolved_id(calculator, name) is None


def test_name_parts_naming_two_references_resolve_to_neither(calculator) -> None:
    assert _resolved_id(calculator, "Folate (Biotin)") is None


def test_hcl_alias_does_not_claim_the_sulfate_trial_reference(calculator) -> None:
    assert _resolved_id(calculator, "Glucosamine HCl") is None
    assert _resolved_id(calculator, "Glucosamine Sulfate") == "glucosamine_sulfate"


@pytest.mark.parametrize("form", ["glucosamine hydrochloride", "n-acetyl glucosamine (NAG)"])
def test_resolved_glucosamine_form_keeps_its_own_study_material(calculator, form) -> None:
    assert calculator._find_nutrient("Glucosamine", form_name=form) is None


def test_scoring_reference_maps_agree_with_the_lookup(calculator) -> None:
    """generic_dose decides the dose curve by canonical id, but the enriched
    pct_rda comes from this name lookup. The IQM name the enricher passes must
    resolve to the reference the scoring map names, or to no reference."""
    iqm = json.loads((SCRIPTS / "data/ingredient_quality_map.json").read_text())
    maps = {
        **generic_dose._DRI_REFERENCE_BY_CANONICAL,
        **generic_dose._CLINICAL_ANCHOR_REFERENCE_BY_CANONICAL,
    }
    mismatches = {}
    for canonical, reference in maps.items():
        entry = iqm.get(canonical) or {}
        group = entry.get("nutrient_group_id")
        name = ((iqm.get(group) or {}).get("standard_name") if group else None) or entry.get("standard_name")
        if not name:
            continue
        resolved = _resolved_id(calculator, name)
        if resolved not in (reference, None):
            mismatches[canonical] = (name, resolved, reference)
    assert mismatches == {}
