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
        ("Glucosamine Sulfate 2NaCl", "Glucosamine"),
        ("Pylopass Lactobacillus reuteri", "Probiotics"),
        ("Bitter Orange Citrus Bioflavonoids", "Citrus Bioflavonoids"),
        ("Pancreatin 4X", "Digestive Enzymes"),
        ("Pancreatin 8X", "Digestive Enzymes"),
        ("Pancrelipase", "Digestive Enzymes"),
        ("Immunoglobulin G", "Immunoglobulin"),
        ("Grape seed ext.", "Grape Seed Extract"),
        ("Guggul Gum Extract", "Guggul"),
        ("S-Adenosyl Methionine", "SAMe"),
        ("S-Adenosylmethionine Tosylate", "SAMe"),
        ("Betain HCl", "TMG"),
        ("sodium hyaluronate", "Hyaluronic Acid"),
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
        ("Siberian Eleuthero", "Ginseng"),
        ("Phosphatidyl L-Serine", "Phosphatidylserine"),
        ("M.S.M.", "MSM"),
        ("Para-Amino Benzoic Acid", "PABA"),
        ("Ginkgold Ginkgo biloba extract", "Ginkgo"),
        ("Chaste extract", "Chasteberry"),
        ("Testofen Fenugreek seed extract", "Fenugreek"),
        ("Beta 1,3 Glucan", "Beta-Glucan"),
        ("Rutin (Sophora japonica) flower bud extract", "Citrus Bioflavonoids"),
        ("S-Acetyl-L-Glutathione", "Glutathione"),
        ("Carnipure L-Carnitine", "L-Carnitine"),
        ("Black Cohosh (Cimicifuga racemosa) root and rhizome extract", "Black Cohosh"),
        ("Icelandic Kelp", "Iodine"),
        ("L-Lysine Monohydrochloride", "L-Lysine"),
        ("Boron Amino Acid Chelate", "Boron"),
        ("Glucosamine Sulphate 2KCl", "Glucosamine"),
        ("isolated Soy Protein", "Protein"),
        ("Soy Protein isolate", "Protein"),
        ("L-Cysteine/N-Acetyl L-Cysteine", "N-Acetyl Cysteine"),
        ("Alpha-Lipoic Acid & R-Lipoic Acid", "Alpha Lipoic Acid"),
        ("Niacinamide/Niacin", "Vitamin B3"),
        ("dried Ferrous Sulfate", "Iron"),
        ("Joint Shield 5-Loxin Advanced Boswellia serrata extract", "Boswellia"),
        ("Mixed Bioflavonoids", "Citrus Bioflavonoids"),
        ("Sensoril Ashwagandha root & leaf extract", "Ashwagandha"),
        ("Vitamin K1/K2", "Vitamin K"),
        ("DL-Alpha Tocopheryl Acetate", "Vitamin E"),
        ("S. cerevisiae", "S. cerevisiae"),
        ("Pituitary", "Pituitary"),
        ("Kidney", "Kidney"),
        ("Pancreas", "Pancreas"),
        ("Heart", "Heart"),
        ("Ovary", "Ovary"),
        ("Hypericins", "St. John's Wort"),
        ("Andrographis aerial parts extract", "Andrographis"),
        ("Horehound", "Horehound"),
        ("Wheat Grass/Barley Grass", "Wheat Grass/Barley Grass"),
        ("Oyster extract", "oyster extract"),
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
        ("FD&C Yellow #6 Aluminum Lake"),
        ("FD&C Yellow #5 Lake"),
        ("FD&C Yellow #5 Aluminum Lake"),
        ("FD&C Blue #1 Lake"),
        ("FD&C Blue #2 Lake"),
        ("FD&C Blue #2 Aluminum Lake"),
        ("FD&C Red #40 Aluminum Lake"),
        ("Methylcellulose"),
        ("Cellulose, Plant"),
        ("Vegetable Modified Cellulose"),
        ("Film Coat"),
        ("Glycerin Coating"),
        ("Methocel"),
        ("Sodium Carboxymethycellulose"),
        ("Cellulose & Glycerin Coating"),
        ("Food Grade Coating"),
        ("Vegetable Stearates"),
        ("Di Calcium Phosphate"),
        ("Dibasic Calcium Phosphate Dihydrate"),
        ("pregelatinized Corn Starch"),
        ("Microcystalline Cellulose"),
        ("Veg. Cellulose"),
        ("Hydroxypropylmethyl Cellulose"),
        ("Magnesium Vegetable Stearate"),
        ("Cab-o-sil"),
        ("Veg. Magnesium Stearate"),
        ("Vegetable-Based Coating"),
        ("aqueous-based Coating"),
        ("Triglycerides"),
        ("Blue #1 Lake"),
        ("natural Anise flavor"),
        ("Vanilla Flavor, Natural"),
        ("Oil of Peppermint"),
        ("China Wax"),
        ("Pea Starch"),
        ("Methacrylic Acid"),
        ("Alginic Acid"),
        ("Vegetable Magnesium Silicate"),
        ("Dextrates"),
        ("Glycerol Palmitostearate"),
        ("Artificial color"),
        ("Calcium Sulfate"),
        ("Tapioca Dextrose"),
        ("Dextrose Monohydrate"),
        ("Lactose Monohydrate"),
        ("Carbomer"),
        ("yellow Ochre"),
        ("Hydroxypropyl-Beta-Cyclodextrin"),
        ("natural Lithothamnion calcarea"),
        ("Lithothamnion calcarea"),
        ("hydrogenated Cottonseed oil"),
        ("Sterotex NF"),
        ("Sodium Metasilicate"),
        ("Oligosaccharides"),
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
        ("Trace Elements"),
        ("Trace Minerals"),
        ("Co-Nutrients"),
        ("Bioactive Enzymes & Proteins"),
        ("Digestive Aids/Enzymes"),
        ("Whole Food Enzymes"),
        ("Complete Digestive Support"),
        ("Herbal Extracts"),
        ("Enzymes"),
        ("Carotenoid Mix"),
        ("Sulfate"),
    ],
)
def test_descriptor_rows_are_skip_classified(normalizer, name):
    # Descriptor rows are excluded in normalization flow via nutrition/label checks.
    assert normalizer._is_nutrition_fact(name) is True
