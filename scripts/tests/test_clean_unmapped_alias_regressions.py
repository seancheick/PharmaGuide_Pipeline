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
        ("Synapsa", "Bacopa"),
        ("NovaSoy", "Isoflavones"),
        ("CardioAid Plant Sterols", "Phytosterols"),
        ("Hesperidin Bioflavonoid extract", "Citrus Bioflavonoids"),
        ("Bifidobacterium breve", "Probiotics"),
        ("Selenium AAC", "Selenium"),
        ("Zinc Mono-L-Methionine Sulfate", "Zinc"),
        ("Pau D’Arco bark extract", "Pau D'Arco"),
        ("Ginkgo biloba 50:1 leaf extract", "Ginkgo"),
        ("Rhodiola (Rhodiola rosea L.) rhizome extract", "Rhodiola"),
        ("Aloe vera leaf gel 200:1 extract", "Aloe Vera"),
        ("Hawthorn 1.8% extract", "Hawthorn"),
        ("Calcium-Magnesium Inositol Hexaphosphate", "Inositol Hexaphosphate"),
        ("Boswellin Super (Boswellia serrata) gum resin extract", "Boswellia"),
        ("Lactobacillus acidophilus L-92", "Lactobacillus Acidophilus"),
        ("N-Acetyl-L-Cysteine/L-Cysteine HCl", "N-Acetyl Cysteine"),
        ("Vanadium Amino Acid Chelate", "Vanadium"),
        ("Pancreatic Enzymes 11x", "Digestive Enzymes"),
        ("Sharp-PS Gold Conjugated PS-DHA", "Phosphatidylserine"),
        ("Coptis (Coptis chinensis) root & rhizome 12:1 extract", "Coptis Rhizome"),
        ("Coriolus (Coriolus versicolor) fruiting body extract", "Kawaratake"),
        ("Artist's Conk", "Artist's Conk"),
        ("Fringe Tree (Chionanthus virginicus) bark extract", "Fringe Tree"),
        ("Lobelia", "Lobelia"),
        ("Quassia", "Quassia"),
        ("Horseradish", "Horseradish"),
        ("Actazin Kiwifruit Powder", "Kiwifruit"),
        ("Tillandsia", "Tillandsia"),
        ("Selenium Chelate", "Selenium"),
        ("Horny Goat Weed P.E.", "Icariin"),
        ("Cholesstrinol HP", "Phytosterols"),
        ("Willow bark 5:1 extract", "White Willow Bark"),
        ("Sprouted Barley Juice", "Barley Juice"),
        ("Beta Zea Carotene", "Beta-Carotene"),
        ("Rennin", "Digestive Enzymes"),
        ("SesaPlex Sesame seed extract", "Sesamin"),
        ("Yucca juice extract", "Yucca"),
        ("Indian Madder", "Indian Madder"),
        ("Oregon Grape (Berberis aquifolium) root 4:1 extract", "Oregon Grape"),
        ("Hops (Humulus lupulus L.) cone 7.5:1 extract", "Hops"),
        ("KSM-66 organic Ashwagandha root extract", "Ashwagandha"),
        ("Ashwagandha (Sensoril brand) root and leaf extract", "Ashwagandha"),
        ("Ashwaganda", "Ashwagandha"),
        ("Citicoline Cognizin brand", "Choline"),
        ("Rhodiola rosea 3% extract", "Rhodiola"),
        ("Panax ginseng 7% extract", "Ginseng"),
        ("Milk Thistle 80% extract", "Milk Thistle"),
        ("St. John's Wort Whole Herb Extract", "St. John's Wort"),
        ("Vitex Berry Extract", "Chasteberry"),
        ("L-Citrulline Hydrochloride", "L-Citrulline"),
        ("Calcium Alpha-Ketoglutarate", "Alpha-Ketoglutarate"),
        ("L-methyfolate", "Vitamin B9"),
        ("Ferrochel Iron Bisglycinate", "Iron"),
        ("OptiMSM Methylsulfonylmethane", "MSM"),
        ("Long Jack", "Tongkat Ali"),
        ("Tongkat Ali 50:1 extract", "Tongkat Ali"),
        ("Boswellia serrata dried extract", "Boswellia"),
        ("AprèsFlex Boswellia serrata", "Boswellia"),
        ("Cellulase Enzymes", "Digestive Enzymes"),
        ("L-Cysteine and N-Acetyl L-Cysteine", "N-Acetyl Cysteine"),
        ("Epigallocatechin 3-Gallate", "Egcg"),
        ("Chromium chromaX(R)", "Chromium"),
        ("PrimaVie purified Shilajit", "Shilajit"),
        ("Safr'Inside", "Saffron"),
        ("Whole Glucan Particle", "Beta-Glucan"),
        ("Guggul lipids powder", "Guggul"),
        ("L-Dihydroxyphenylalanine", "L-Dopa"),
        ("Diadzein", "Daidzein"),
        ("North Atlantic Kelp", "Brown Kelp"),
        ("Blueberry, Wild", "Blueberry"),
        ("L-Alpha-Glycerylphosphorylcholine", "Alpha GPC"),
        ("Isatis", "Woad"),
        ("Pycrinil Artichoke (Cynara cardunculus) leaf extract", "Globe Artichoke"),
        ("Alfalfa (Medicago sativa) aerial part extract", "Alfalfa"),
        ("Ivy extract", "Ivy"),
        ("Parsley herb powder", "Parsley"),
        ("Pumpkin seed meal powder", "Pumpkin"),
        ("Goldenrod Powder", "Goldenrod"),
        ("Cassava", "Cassava"),
        ("Acai Berry Fruit Extract", "Acai"),
        ("Oat 10:1 extract", "Oat Straw"),
        ("Oat Beta Glucan Concentrate", "Beta-Glucan"),
        ("Horsetail aerial parts ext.", "Horsetail"),
        ("MirtoSelect Bilberry", "Bilberry"),
        ("Pycnogenol French Maritime Pine", "Pine Bark Extract"),
        ("Integra-Lean African Mango", "African Mango"),
        ("NT2 Collagen", "Collagen"),
        ("Lemon Grass", "Lemongrass"),
        ("Lithothamnion corallioides", "Calcium"),
        ("Orange Pekoe (Camellia sinensis) extract", "Black Tea Leaf"),
        ("Maitake (Grifola frondosa) fruit body powder", "Maitake"),
        ("narrow-leaved Coneflower (Echinacea angustifoliae) root extract", "Echinacea"),
        ("Velvet Elk Antler powder", "Deer Antler Velvet"),
        ("Buffalo Liver Concentrate", "Organ Extracts"),
        ("Green Peppers", "Green Bell Pepper"),
        ("Gardenia fruit extract", "Gardenia"),
        ("Glehnia root extract", "Glehnia"),
        ("Apricot seed extract", "Apricot"),
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
        ("Lithothamnion corallioides"),
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
    ],
)
def test_descriptor_rows_are_skip_classified(normalizer, name):
    # Descriptor rows are excluded in normalization flow via nutrition/label checks.
    assert normalizer._is_nutrition_fact(name) is True


def test_generic_header_token_is_skip_classified(normalizer):
    assert normalizer._should_skip_ingredient("Ingredients") is True


@pytest.mark.parametrize(
    "name",
    [
        ("from 150 mg Betaine HCl"),
        ("from 800 mg of S-Adenosyl-L-Methionine Disulfate Tosylate"),
    ],
)
def test_from_mg_spec_rows_are_skip_classified(normalizer, name):
    assert normalizer._should_skip_ingredient(name) is True


@pytest.mark.parametrize(
    "name",
    [
        ("Trace Elements"),
        ("Trace Minerals"),
        ("Co-Nutrients"),
        ("Bioactive Enzymes & Proteins"),
        ("Digestive Aids/Enzymes"),
        ("Whole Food Enzymes"),
        ("Complete Digestive Support"),
        ("Herbal Extracts"),
        ("Enzymes"),
        ("Sulfate"),
        ("Lactic Acid Bacteria"),
        ("Ionic Sea Minerals"),
        ("Ionic Trace Minerals"),
        ("Trace Mineral concentrate"),
        ("Ultra Trace Minerals"),
        ("Niacin & Niacinamide"),
        ("Niacin and Niacinamide"),
        ("FoodState Orange Vitamin C"),
        ("Nature's C with QPower"),
        ("Futurebiotics BioAccelerators"),
        ("Bronson BioAccelerators"),
        ("Nutrilite Phytonutrient Concentrate"),
        ("Whole Food PhytoAlgae"),
        ("Food Based Nutrients"),
    ],
)
def test_routed_terms_are_not_hard_skipped(normalizer, name):
    assert normalizer._is_nutrition_fact(name) is False
    assert normalizer._should_skip_ingredient(name) is False


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Niacin & Niacinamide", "Vitamin B3"),
        ("Niacin and Niacinamide", "Vitamin B3"),
        ("Niacin/Niacinamide", "Vitamin B3"),
        ("Lactic Acid Bacteria", "Probiotics"),
        ("FoodState Orange Vitamin C", "Vitamin C"),
        ("Nature's C with QPower", "Vitamin C"),
    ],
)
def test_iqm_rerouted_terms_map_to_conservative_forms(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])
    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name",
    [
        ("Herbal Extract"),
        ("Ionic Sea Minerals"),
        ("Ionic Trace Minerals"),
        ("Trace Mineral concentrate"),
        ("Ultra Trace Minerals"),
        ("Futurebiotics BioAccelerators"),
        ("Bronson BioAccelerators"),
        ("Nutrilite Phytonutrient Concentrate"),
        ("Whole Food PhytoAlgae"),
        ("Food Based Nutrients"),
        ("InnoSlim"),
        ("S7"),
        ("Spectra"),
        ("Source-70"),
        ("elevATP"),
        ("Oxi-fend"),
        ("CyanthOx 30"),
        ("EstroG-100"),
        ("ViNitrox"),
        ("Seditol"),
        ("VitaBerry"),
        ("Dermaval"),
        ("Olea-Pro"),
        ("BioCore Optimum Complete"),
        ("Grapefruit Fiber"),
        ("Kefir Starter Culture R0215"),
        ("Fortify Optima"),
        ("HerbaFlor"),
        ("Vitamin F"),
        ("water and vegan Capsule"),
        ("Targeted release capsule"),
        ("Capsules of plant origin"),
        ("Vegan Capsules"),
        ("Vege capsule"),
        ("DRcaps Vegetable Capsule"),
        ("HPMC Vegetable Capsule"),
        ("Plant-Based Hypromellose Capsules"),
        ("organic Nu-Mag"),
        ("Nu-Mag"),
        ("Nu-Rice"),
        ("NuFlow"),
        ("CyLoc"),
        ("PAK"),
        ("AgeLoss Female Factors"),
        ("AgeLoss Male Factors"),
        ("Ecoganic Veggies & Greens"),
        ("Ecoganic Herbs & Superfoods"),
        ("Additional Foods & Extracts"),
        ("Detoxification & Liver Support"),
        ("active Flavonols, Flavonones, Flavones & Naringen"),
        ("Test 1700 Activator"),
        ("Shen Min Herb"),
        ("Charcoal, Activated"),
        ("Dicalcium Phopshate"),
        ("Pregelantinized Corn Starch"),
        ("Natural Flavouring"),
        ("natural Cherry flavour"),
        ("organic Soy Bean fiber"),
        ("Egg Albumin"),
        ("Calcium Caseinate"),
        ("Plasacryl"),
        ("Invetek chewable base"),
        ("fermentation-activated organically grown whole Soya"),
        ("enzyme pre-digested whole Soya"),
        ("high quality Protein"),
    ],
)
def test_descriptor_terms_map_via_other_ingredients_identity(normalizer, name):
    ing = {
        "name": name,
        "quantity": [{"quantity": 10, "unit": "mg"}],
        "unit": "mg",
        "forms": [],
    }
    result = normalizer._process_single_ingredient_enhanced(ing, is_active=True)
    assert result is not None
    assert result["mapped"] is True
