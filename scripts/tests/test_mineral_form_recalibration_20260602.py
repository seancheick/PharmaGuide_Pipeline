"""Regression tests for 2026-06-02 Zn/Mg/Fe mineral form recalibration.

This locks the clinician rule applied after live API verification:
bio_score is absorption/bioavailability only, while score is
bio_score + natural bonus, capped at 18.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / "data" / "ingredient_quality_map.json"


@pytest.fixture(scope="module")
def iqm():
    return json.loads(IQM_PATH.read_text())


EXPECTED_BIO_SCORES = {
    "magnesium": {
        "magnesium citrate": 14,
        "magnesium aspartate": 14,
        "magnesium lactate": 13,
        "magnesium chloride": 13,
        "magnesium glycinate": 12,
        "magnesium citrate-malate": 12,
        "magnesium malate": 11,
        "magnesium amino acid chelate": 11,
        "magnesium threonate": 10,
        "magnesium taurate": 10,
        "magnesium gluconate": 10,
        "magnesium ascorbate (as magnesium source)": 10,
        "magnesium acetyl-taurate": 9,
        "magnesium orotate": 9,
        "magnesium pyruvate": 9,
        "magnesium succinate": 9,
        "magnesium brown rice chelate": 6,
        "magnesium carbonate": 6,
        "magnesium phosphate": 6,
        "magnesium (unspecified)": 5,
        "magnesium sulfate": 4,
        "magnesium oxide": 3,
        "magnesium hydroxide": 3,
    },
    "zinc": {
        "zinc picolinate": 13,
        "zinc bisglycinate": 13,
        "zinc aspartate": 13,
        "zinc acetate": 12,
        "zinc citrate": 12,
        "zinc gluconate": 12,
        "zinc monomethionine": 12,
        "zinc amino acid chelate": 12,
        "zinc chloride": 10,
        "zinc lactate": 10,
        "zinc sulfate": 10,
        "zinc ascorbate (as zinc source)": 10,
        "zinc carnosine": 9,
        "zinc orotate": 9,
        "zinc malate": 9,
        "zinc brown rice chelate": 8,
        "zinc (unspecified)": 6,
        "zinc carbonate": 6,
        "zinc oxide": 5,
        "zinc phosphate": 5,
    },
    "iron": {
        "heme iron polypeptide": 15,
        "iron bisglycinate": 13,
        "ferrous ascorbate": 13,
        "ferrous fumarate": 12,
        "ferrous gluconate": 11,
        "iron amino acid chelate": 11,
        "iron protein succinylate": 10,
        "ferrous sulfate": 10,
        "liposomal iron": 10,
        "polysaccharide-iron complex": 9,
        "microencapsulated iron": 9,
        "carbonyl iron": 8,
        "iron picolinate": 8,
        "ferric citrate": 7,
        "iron brown rice chelate": 6,
        "iron (unspecified)": 6,
        "ferric sulfate": 6,
        "ferric pyrophosphate": 6,
        "ferric iron": 5,
        "iron oxide": 2,
    },
}


@pytest.mark.parametrize(
    "parent,form_name,expected",
    [
        (parent, form_name, expected)
        for parent, forms in EXPECTED_BIO_SCORES.items()
        for form_name, expected in forms.items()
    ],
)
def test_clinician_mineral_bio_score_table(iqm, parent, form_name, expected):
    form = iqm[parent]["forms"].get(form_name)
    assert form is not None, f"{parent}::{form_name} missing"
    assert form["bio_score"] == expected


@pytest.mark.parametrize(
    "parent,form_name",
    [
        (parent, form_name)
        for parent, forms in EXPECTED_BIO_SCORES.items()
        for form_name in forms
    ],
)
def test_mineral_score_matches_natural_bonus_formula(iqm, parent, form_name):
    form = iqm[parent]["forms"][form_name]
    expected = min(18, form["bio_score"] + (3 if form["natural"] else 0))
    assert form["score"] == expected


@pytest.mark.parametrize(
    "parent,form_name,unii,cui,status",
    [
        ("zinc", "zinc chloride", "86Q357L16B", "C0078774", ("exact_match", "exact_match")),
        ("zinc", "zinc lactate", "2GXR25858Y", "C2240534", ("exact_match", "exact_match")),
        ("zinc", "zinc carbonate", "EQR32Y7H0M", "C0078772", ("exact_match", "exact_match")),
        ("zinc", "zinc phosphate", "1E2MCT2M62", "C0078788", ("exact_match", "exact_match")),
        ("zinc", "zinc malate", "3M0U6DM996", None, ("exact_match", "no_exact_match")),
        ("zinc", "zinc ascorbate (as zinc source)", "9TI35313XW", "C1337243", ("exact_match", "exact_match")),
        ("magnesium", "magnesium phosphate", "453COF7817", "C0065527", ("exact_match", "exact_match")),
        ("magnesium", "magnesium citrate-malate", None, None, ("no_exact_match", "no_exact_match")),
        ("magnesium", "magnesium pyruvate", None, None, ("no_exact_match", "no_exact_match")),
        ("magnesium", "magnesium succinate", "B728YV86FE", "C1366048", ("exact_match", "exact_match")),
        ("iron", "ferric pyrophosphate", "QK8899250F", "C0117541", ("exact_match", "exact_match")),
    ],
)
def test_new_mineral_forms_have_api_identity_evidence(iqm, parent, form_name, unii, cui, status):
    form = iqm[parent]["forms"].get(form_name)
    assert form is not None
    external_ids = form.get("external_ids") or {}
    assert external_ids.get("unii") == unii
    assert external_ids.get("cui") == cui
    verification = form.get("api_verification") or {}
    assert verification.get("verified_at") == "2026-06-02"
    assert verification.get("gsrs_unii_status") == status[0]
    assert verification.get("umls_cui_status") == status[1]
    assert verification.get("report") == "scripts/audits/mineral_forms_20260602/api_verification.json"


def test_mineral_ascorbate_redirects_point_to_existing_forms(iqm):
    magnesium_redirect = iqm["vitamin_c"]["forms"]["magnesium ascorbate"]["redirect"]
    zinc_redirect = iqm["vitamin_c"]["forms"]["zinc ascorbate"]["redirect"]
    assert magnesium_redirect == "magnesium.forms.magnesium ascorbate (as magnesium source)"
    assert zinc_redirect == "zinc.forms.zinc ascorbate (as zinc source)"
    assert "magnesium ascorbate (as magnesium source)" in iqm["magnesium"]["forms"]
    assert "zinc ascorbate (as zinc source)" in iqm["zinc"]["forms"]
