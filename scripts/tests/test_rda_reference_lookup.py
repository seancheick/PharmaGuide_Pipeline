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


@pytest.mark.parametrize("name", ["Coenzyme Q10", "Inositol", "Lutein", "Glycine", "Creatine"])
def test_reviewed_non_nutritional_anchor_cannot_supply_panel_coverage(calculator, name):
    result = calculator.compute_nutrient_adequacy(name, 50, "mg")
    assert result.rda_ai_source == "unknown"
    assert result.scoring_eligible is False
    # Historical numbers remain descriptive; they do not become nutritional credit.
    assert result.pct_rda is not None


@pytest.mark.parametrize("name", ["Magnesium", "Calcium", "Potassium", "Sodium", "Choline"])
def test_official_nutritional_references_remain_panel_eligible(calculator, name):
    result = calculator.compute_nutrient_adequacy(name, 50, "mg")
    assert result.rda_ai_source in {"rda", "ai"}
    assert result.scoring_eligible is True


def test_reference_eligibility_never_clears_an_independent_upper_limit(calculator):
    result = calculator.compute_nutrient_adequacy("Boron", 40, "mg")
    assert result.scoring_eligible is False
    assert result.over_ul is True
    assert result.pct_ul == 200


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
    """Official DRI references agree across canonical and label-name lookup.

    Retired clinical shortcuts stay absent; their source regimens remain
    descriptive records rather than a second numerical Dose map.
    """
    iqm = json.loads((SCRIPTS / "data/ingredient_quality_map.json").read_text())
    assert not hasattr(generic_dose, "_CLINICAL_ANCHOR_REFERENCE_BY_CANONICAL")
    assert "_clinical_anchor_reference_by_canonical" not in generic_dose._DM
    maps = generic_dose._DRI_REFERENCE_BY_CANONICAL
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
    references = {row["id"]: row for row in json.loads(
        (SCRIPTS / "data/rda_optimal_uls.json").read_text())["nutrient_recommendations"]}
    for canonical, reference, source, amount in (
        ("glycine", "glycine", "22529837", 3000),
        ("betaine", "betaine_tmg", "31809615", 1500),
    ):
        record = references[reference]
        assert source in record["references"]
        assert any(row.get("rda_ai") == amount for row in record["data"])
        assert record["reference_semantics"]["reference_type"] == "discrete_studied_regimen"
        assert generic_dose._adequacy_reference_kind(canonical) == "no_benchmark"
        assert _resolved_id(calculator, record["standard_name"]) == reference


@pytest.mark.parametrize('form', ['acetyl-l-carnitine (alcar)', 'acetyl-l-carnitine', 'acetyl-l-carnitine hydrochloride'])
def test_alcar_does_not_borrow_the_nonacetylated_carnitine_reference(calculator, form):
    assert calculator._find_nutrient('L-Carnitine', form_name=form) is None
    assert calculator._find_nutrient('L-Carnitine', form_name='l-carnitine (free base)')['id'] == 'l_carnitine'


def test_magnesium_preserves_reference_scope_and_source(calculator):
    result = calculator.compute_nutrient_adequacy("Magnesium", 405, "mg").to_dict()
    assert result["reference"]["ul_basis"] == "supplemental_only"
    assert result["reference"]["source_url"] == "https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/"
    assert result["reference"]["ul_note"] == "UL applies to supplemental magnesium only, not food sources"


def test_ul_sentence_qualifies_exposure_and_supplement_scope():
    from rda_ul_calculator import ul_exceedance_sentence
    text = ul_exceedance_sentence(480, 350, "mg", ul_basis="supplemental_only",
                                  exposure_label="At maximum directed daily use")
    assert text.startswith("At maximum directed daily use")
    assert "from supplements" in text
    assert "480 mg" in text
    assert "before other sources" not in text
