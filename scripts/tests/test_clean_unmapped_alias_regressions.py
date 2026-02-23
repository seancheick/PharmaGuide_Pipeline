import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Magtein Magnesium L-Threonate", "Magnesium"),
        ("NIAGEN Nicotinamide Riboside", "Nicotinamide Riboside"),
        ("N-Acetyl L-Cysteine", "N-Acetyl Cysteine"),
        ("Glucosamine Sulfate 2KCI", "Glucosamine"),
        ("Pylopass Lactobacillus reuteri", "Probiotics"),
        ("Bitter Orange Citrus Bioflavonoids", "Bitter Orange"),
        ("melatonin, micronized", "Melatonin"),
        ("Phase 2 White Kidney (bean) extract", "Common Bean Extract"),
        ("Red Sockeye Salmon Oil, Natural, Wild", "Fish Oil"),
        ("cold pressed omega rich Flax seed Oil", "Flaxseed"),
        ("Ashwagandha Leaf, Root Extract", "Ashwagandha"),
        ("Dairy Digestive Enymes", "Digestive Enzymes"),
        ("TeaSlender Green Tea Phytosome", "Green Tea Extract"),
        ("Oligopin French Maritime Pine (Pinus pinaster) extract", "Pine Bark Extract"),
        ("Wellmune WGP", "Beta-Glucan"),
        ("Bioferrin", "Lactoferrin"),
        ("Beta-Glucanase", "Digestive Enzymes"),
    ],
)
def test_high_frequency_active_aliases_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])
    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name",
    [
        ("wild crafted Marshmallow"),
        ("wild crafted Red Clover"),
        ("wild crafted Uva Ursi"),
    ],
)
def test_wild_crafted_prefix_normalization_maps(normalizer, name):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])
    assert mapped is True
    assert standard_name


@pytest.mark.parametrize(
    "name",
    [
        ("Hydroxypropyl Methyl Cellulose"),
        ("Hydroxypropyl Methylcellulose Phthalate"),
        ("Vegetable Pullulan"),
        ("non-GMO Vegetable Glycerin"),
        ("Dicalcium Phosphate Anhydrous"),
        ("FD&C Yellow #6 Lake"),
    ],
)
def test_high_frequency_inactive_aliases_map(normalizer, name):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])
    assert mapped is True
    assert standard_name


@pytest.mark.parametrize(
    "name",
    [
        ("Total Polyphenols"),
        ("Contains 12.5 mcg of Stabilized Allicin"),
    ],
)
def test_descriptor_rows_are_skip_classified(normalizer, name):
    # Descriptor rows are excluded in normalization flow via nutrition/label checks.
    assert normalizer._is_nutrition_fact(name) is True
