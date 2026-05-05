#!/usr/bin/env python3
"""Cleaner form-from-name extraction regression tests.

Triggering bug: Thorne Basic Prenatal (DSLD 328830) emitted forms=[]
on the 'Vitamin A Palmitate' active row because the cleaner regex
only matched the legacy 'retinyl palmitate' pattern. Labels that say
'Vitamin A Palmitate' (vitamin + ester named separately) leaked
through with no form, so build_final_db's downstream form derivation
came out empty.

The Phase A bridge in build_final_db falls back to matched_form so
Flutter recovers, but the cleaner is the upstream source of truth.
These tests pin the patterns we now recognize so regressions surface
at the cleaner boundary instead of relying on the bridge.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


# -- Vitamin A esters without the 'retinyl' prefix ---------------------------

def test_vitamin_a_palmitate_extracts_retinyl_palmitate(normalizer):
    """Thorne Basic Prenatal regression — was returning []."""
    forms = normalizer._extract_forms_from_ingredient_name("Vitamin A Palmitate")
    assert "retinyl palmitate" in forms


def test_vitamin_a_acetate_extracts_retinyl_acetate(normalizer):
    forms = normalizer._extract_forms_from_ingredient_name("Vitamin A Acetate")
    assert "retinyl acetate" in forms


def test_vitamin_a_alone_stays_empty(normalizer):
    """'Vitamin A' with no form token is genuinely unknown form. The
    cleaner must not invent one — the canonical contract relies on
    this to emit form_status='unknown' for the partner row."""
    assert normalizer._extract_forms_from_ingredient_name("Vitamin A") == []


# -- Vitamin K isoforms ------------------------------------------------------

def test_mk_7_extracts_menaquinone_7(normalizer):
    forms = normalizer._extract_forms_from_ingredient_name("Vitamin K2 MK-7")
    assert "menaquinone-7" in forms


def test_mk7_without_hyphen_extracts_menaquinone_7(normalizer):
    # Some labels write "MK7" with no hyphen.
    assert "menaquinone-7" in normalizer._extract_forms_from_ingredient_name(
        "Vitamin K2 MK7"
    )


def test_menaquinone_7_extracts_menaquinone_7(normalizer):
    forms = normalizer._extract_forms_from_ingredient_name("Vitamin K2 as Menaquinone-7")
    assert "menaquinone-7" in forms


def test_mk_4_extracts_menaquinone_4(normalizer):
    forms = normalizer._extract_forms_from_ingredient_name("Vitamin K2 MK-4")
    assert "menaquinone-4" in forms


def test_phylloquinone_extracts_phylloquinone(normalizer):
    forms = normalizer._extract_forms_from_ingredient_name("Vitamin K1 Phylloquinone")
    assert "phylloquinone" in forms


def test_phytonadione_extracts_phylloquinone(normalizer):
    # Phytonadione is the USP monograph name for phylloquinone (K1).
    forms = normalizer._extract_forms_from_ingredient_name("Phytonadione")
    assert "phylloquinone" in forms


# -- Folate forms (active vs synthetic) --------------------------------------

def test_l_5_mthf_extracts_methyltetrahydrofolate(normalizer):
    forms = normalizer._extract_forms_from_ingredient_name("Folate as L-5-MTHF")
    assert "5-methyltetrahydrofolate" in forms


def test_5_mthf_extracts_methyltetrahydrofolate(normalizer):
    assert "5-methyltetrahydrofolate" in normalizer._extract_forms_from_ingredient_name("5-MTHF")


def test_methylfolate_extracts_methyltetrahydrofolate(normalizer):
    assert "5-methyltetrahydrofolate" in normalizer._extract_forms_from_ingredient_name("Methylfolate")


def test_full_chemical_name_extracts_methyltetrahydrofolate(normalizer):
    assert "5-methyltetrahydrofolate" in normalizer._extract_forms_from_ingredient_name(
        "5-Methyltetrahydrofolate"
    )


def test_folic_acid_extracts_folic_acid(normalizer):
    forms = normalizer._extract_forms_from_ingredient_name("Folic Acid")
    assert "folic acid" in forms


def test_methylated_folate_takes_precedence_over_folic_acid(normalizer):
    """A label that mentions both should resolve to the active form."""
    forms = normalizer._extract_forms_from_ingredient_name(
        "Folate (as L-5-MTHF, not folic acid)"
    )
    assert "5-methyltetrahydrofolate" in forms
    assert "folic acid" not in forms


# -- Mineral salt long tail (was TODO(M9-DEFER)) -----------------------------

@pytest.mark.parametrize("label, expected", [
    ("Magnesium L-Threonate", "threonate"),
    ("Magnesium Orotate", "orotate"),
    ("Iron Fumarate", "fumarate"),
    ("Calcium Lactate", "lactate"),
    ("Zinc Gluconate", "gluconate"),
    ("Magnesium Aspartate", "aspartate"),
    ("Magnesium Succinate", "succinate"),
    ("Zinc Pidolate", "pidolate"),
])
def test_mineral_salt_extraction(normalizer, label, expected):
    assert expected in normalizer._extract_forms_from_ingredient_name(label)


# -- B-vitamin active vs synthetic forms -------------------------------------

@pytest.mark.parametrize("label, expected", [
    # B6
    ("Vitamin B6 P-5-P", "pyridoxal-5-phosphate"),
    ("Pyridoxal-5-Phosphate", "pyridoxal-5-phosphate"),
    ("Pyridoxine HCl", "pyridoxine"),
    # B2
    ("Riboflavin-5-Phosphate", "riboflavin-5-phosphate"),
    ("FMN", "riboflavin-5-phosphate"),
    ("Riboflavin", "riboflavin"),
    # B3
    ("Niacinamide", "niacinamide"),
    ("Nicotinic Acid", "nicotinic acid"),
    ("Inositol Hexanicotinate", "inositol hexanicotinate"),
    # B1
    ("Thiamine Mononitrate", "thiamine mononitrate"),
    ("Thiamine HCl", "thiamine hydrochloride"),
    ("Benfotiamine", "benfotiamine"),
    # B5
    ("Pantethine", "pantethine"),
    ("Calcium Pantothenate", "calcium pantothenate"),
    ("Pantothenic Acid", "pantothenic acid"),
])
def test_b_vitamin_form_extraction(normalizer, label, expected):
    assert expected in normalizer._extract_forms_from_ingredient_name(label)


# -- Selenium / CoQ10 / Choline ----------------------------------------------

@pytest.mark.parametrize("label, expected", [
    ("L-Selenomethionine", "selenomethionine"),
    ("Selenomethionine", "selenomethionine"),
    ("Sodium Selenate", "sodium selenate"),
    ("Sodium Selenite", "sodium selenite"),
    ("Ubiquinol", "ubiquinol"),
    ("Ubiquinone", "ubiquinone"),
    ("CoQ10 (as Ubiquinol)", "ubiquinol"),
    ("Alpha-GPC", "alpha-gpc"),
    ("Citicoline", "citicoline"),
    ("CDP-Choline", "citicoline"),
    ("Choline Bitartrate", "choline bitartrate"),
])
def test_other_form_sensitive_nutrient_extraction(normalizer, label, expected):
    assert expected in normalizer._extract_forms_from_ingredient_name(label)


# -- Omega-3 molecular forms -------------------------------------------------
# These feed the scorer's _PREMIUM_OMEGA3_FORM_PATTERN haystack
# (score_supplements.py:78-82) so the A2 premium-delivery bonus
# triggers when the label discloses a real molecular form.

@pytest.mark.parametrize("label, expected", [
    ("Fish Oil (Triglyceride)", "triglyceride"),
    ("Fish Oil (Natural Triglyceride form)", "natural triglyceride"),
    ("EPA (rTG)", "re-esterified triglyceride"),
    ("Re-Esterified Triglyceride Fish Oil", "re-esterified triglyceride"),
    ("EPA (Ethyl Ester)", "ethyl ester"),
    ("DHA Ethyl Ester", "ethyl ester"),
    ("Krill Oil (Phospholipid)", "phospholipid"),
    ("Krill Phospholipid Concentrate", "krill phospholipid"),
    ("Free Fatty Acid Fish Oil", "free fatty acid"),
    ("EPA FFA", "free fatty acid"),
    ("Monoglyceride Fish Oil", "monoglyceride"),
])
def test_omega3_molecular_form_extraction(normalizer, label, expected):
    assert expected in normalizer._extract_forms_from_ingredient_name(label)


# -- Omega-3 source oils -----------------------------------------------------

@pytest.mark.parametrize("label, expected", [
    ("Algae Oil", "algae oil"),
    ("Algal Oil", "algae oil"),
    ("DHA from Algae", "algae oil"),
    ("Krill Oil", "krill oil"),
    ("Calamari Oil", "calamari oil"),
    ("Squid Oil", "calamari oil"),
    ("Fish Oil", "fish oil"),
])
def test_omega3_source_oil_extraction(normalizer, label, expected):
    assert expected in normalizer._extract_forms_from_ingredient_name(label)


# -- Postbiotic / probiotic carrier forms ------------------------------------

@pytest.mark.parametrize("label, expected", [
    ("Lactobacillus acidophilus (heat-killed)", "heat-killed"),
    ("Heat-Killed L. plantarum", "heat-killed"),
    ("Tyndallized Bifidobacterium", "heat-killed"),
    ("Inactivated L. paracasei", "inactivated"),
    ("Bacterial Lysate", "lysate"),
    ("Postbiotic Cell Lysate", "lysate"),
    ("Microencapsulated L. acidophilus", "microencapsulated"),
    ("Bacillus coagulans (spore-based)", "spore-based"),
    ("Spore-Forming Probiotic", "spore-based"),
    # vocab consolidates 'acid-stable' / 'acid-resistant' / 'acid-protected'
    # synonyms to a single canonical 'acid-resistant'.
    ("Acid-Stable L. rhamnosus", "acid-resistant"),
])
def test_probiotic_form_extraction(normalizer, label, expected):
    assert expected in normalizer._extract_forms_from_ingredient_name(label)


# -- Prebiotic forms ---------------------------------------------------------

@pytest.mark.parametrize("label, expected", [
    ("Inulin", "inulin"),
    ("Fructooligosaccharides (FOS)", "fructooligosaccharide"),
    ("FOS", "fructooligosaccharide"),
    ("Galactooligosaccharides", "galactooligosaccharide"),
    ("GOS", "galactooligosaccharide"),
    ("Xylooligosaccharides", "xylooligosaccharide"),
    ("XOS", "xylooligosaccharide"),
    ("Resistant Starch", "resistant starch"),
])
def test_prebiotic_form_extraction(normalizer, label, expected):
    assert expected in normalizer._extract_forms_from_ingredient_name(label)


# -- Negative: bare nutrient names must NOT invent a form --------------------

@pytest.mark.parametrize("label", [
    "Vitamin A",
    "Vitamin B12",
    "Vitamin D",
    "Multi-Vitamin Complex",
    "Mineral Blend",
])
def test_bare_nutrient_names_yield_no_form(normalizer, label):
    """The canonical contract relies on empty forms[] -> form_status='unknown'.
    The cleaner must not hallucinate a form when the label didn't disclose one.
    """
    assert normalizer._extract_forms_from_ingredient_name(label) == []
