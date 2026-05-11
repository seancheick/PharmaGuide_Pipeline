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
        ("CalaMarine Oil concentrate", "Calamari Oil"),
        ("Calamarine Oil concentrate", "Calamari Oil"),
        ("NKO", "Krill Oil"),  # NKO (Neptune Krill Oil) now routes to dedicated krill_oil IQM entry
        ("Titanium Dioxide color", "Titanium Dioxide"),
        ("D-Limonene Oil", "D-Limonene"),
    ],
)
def test_batch1_verified_cleaning_aliases_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("D-Limonene Oil", "Limonene", "Limonene"),
        ("Lime Oil", "Lime", "Lime"),
        ("Titanium Dioxide color", "Titanium Dioxide", "Titanium Dioxide"),
    ],
)
def test_ingredient_group_fallback_maps_unmapped_labels(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


def test_ingredient_group_fallback_does_not_override_direct_name_match(normalizer):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "D-Limonene Oil", [], ingredient_group="Orange"
    )

    assert mapped is True
    assert "D-Limonene".lower() in str(standard_name).lower()


def test_ingredient_group_fallback_uses_exact_normalized_lookup(normalizer):
    # Use a group name that is genuinely absent from all DBs to verify that the
    # group fallback returns unmapped when the group itself cannot be resolved.
    # ("lecithin" was the original fixture but was later added to OI via
    # "lecithin (soy)" / "lecithin (sunflower-derived)" aliases that collapse
    # to "lecithin" after parenthetical stripping, so it now correctly maps.)
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Unknown Carrier", [], ingredient_group="xyzunknowngroup999"
    )

    assert mapped is False
    assert standard_name == "Unknown Carrier"


def test_banned_ingredient_group_fallback_respects_negative_match_terms(normalizer):
    """Sodium Borate with ingredient_group=Borax must NEVER route to banned_recalled
    (negative_match_terms prevents false-positive banned match).

    Updated 2026-04-16: After batch48, "sodium borate" is now aliased under
    boron.forms["boron (unspecified)"] (cross_db_overlap_allowlist authorizes
    this as harmful:iqm context-dependent routing). So it now correctly resolves
    to Boron as a trace mineral source. The safety invariant — that it does
    NOT match Sodium Tetraborate (Borax) banned entry — still holds.
    """
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Sodium Borate", [], ingredient_group="Borax"
    )

    # Safety invariant: negative_match_terms blocks banned match regardless of context
    assert standard_name != "Sodium Tetraborate (Borax)"
    # New behavior: IQM alias now correctly routes to Boron (preserves previous
    # "not banned" guarantee while eliminating the unmapped gap in 4 CVS Spectravite products)
    assert mapped is True
    assert str(standard_name).lower() == "boron"


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Cold-Pressed Lemon Oil", "Lemon Oil"),
        ("Coconut Oil, Extra Virgin", "Coconut Oil"),
        ("pharmaceutical grade, molecularly distilled Fish Oil concentrate", "Fish Oil"),
        ("Beeswax, Natural", "Beeswax"),
    ],
)
def test_descriptor_fallback_maps_modifier_wrapped_labels(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


def test_descriptor_fallback_beats_ingredient_group_collision(normalizer):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "cold-pressed Lemon Oil", [], ingredient_group="Lemon"
    )

    assert mapped is True
    assert "lemon oil" in str(standard_name).lower()
    assert "vitamin b9" not in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Ceramosides Wheat seed extract", "Wheat", "Ceramides"),
        ("TruFlex Chondroitin Sulfate", "Chondroitin Sulfate", "Chondroitin"),
        ("Cococin Coconut Water powder", "Coconut", "Coconut Water"),
        ("Coconut Water", "Coconut", "Coconut Water"),
    ],
)
def test_batch2_aliases_and_new_canonical_beat_group_fallback(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Hydrogenated Vegetable Oil", "Hydrogenated Vegetable Oil"),
        ("natural Rosemary flavor", "Natural Rosemary Flavor"),
        ("Grapefruit Oil", "Grapefruit Oil"),
    ],
)
def test_batch3_inactive_identity_gaps_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(name)

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Sesame seed Oil", "Sesame Oil", "Sesame Seed Oil"),
        ("Sesame Seed Oil", "Sesame Oil", "Sesame Seed Oil"),
        ("Extra Virgin Olive Fruit Oil", "Olive Oil", "Extra Virgin Olive Oil"),
    ],
)
def test_batch4_active_oils_map_to_iqm(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Sesame seed Oil", "Sesame Seed Oil"),
        ("Extra Virgin Olive Fruit Oil", "Extra Virgin Olive Oil"),
    ],
)
def test_batch4_inactive_oils_prefer_other_ingredients(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(name)

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


def test_batch5_prickly_pear_leaf_extract_maps_to_existing_nopal(normalizer):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Prickly Pear Cactus leaf extract", [], ingredient_group="Prickly Pear Cactus"
    )

    assert mapped is True
    assert standard_name == "Nopal"


def test_batch5_soluble_food_starch_maps_as_inactive_other_ingredient(normalizer):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other("soluble Food Starch")

    assert mapped is True
    assert standard_name == "Soluble Food Starch"


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Anchovies", "Fish", "Fish"),
        ("Sunflower", "sunflower", "Sunflower (Source Descriptor)"),
        ("Algae", "Algae (unspecified)", "Algae (Source Descriptor)"),
        ("Nonionic Surfactant", "Nonionic Surfactant", "Nonionic Surfactant (Descriptor)"),
    ],
)
def test_batch6_source_and_descriptor_rows_map_without_overclaiming(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Palm", "Oil Palm", "Palm (Source Descriptor)"),
        ("Canola", "Canola oil", "Canola (Source Descriptor)"),
        ("Orange Cream", "Flavor", "Natural Flavors"),
        ("Beet red", "Beet", "Beetroot Powder"),
    ],
)
def test_batch7_source_color_and_flavor_rows_map_conservatively(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("non-GMO Sunflower Vitamin E", "Vitamin E (unspecified)", "Tocopherol (Preservative)"),
        ("Coconut", "Coconut", "Coconut (Source Descriptor)"),
        ("Carob bean Gum", "Carob", "Natural Gums"),
    ],
)
def test_batch8_inactive_rows_map_to_existing_preservative_gum_or_source_routes(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


def test_batch9_inactive_lanolin_maps_to_conservative_source_identity(normalizer):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        "Lanolin", ingredient_group="Lanolin"
    )

    assert mapped is True
    assert standard_name == "Lanolin"


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("D-Beta Tocotrienol", "Vitamin E"),
        ("Zinc Mono-L-Methionine", "Zinc"),
        ("Pectinase", "Digestive Enzymes"),
    ],
)
def test_batch10_active_exact_aliases_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Olive oil-extra virgin", "Olive Oil", "Extra Virgin Olive Oil"),
        ("natural Lemon flavoring", "Flavor", "Natural Lemon Flavor"),
        ("Carrot Oil", "Carrot oil", "Carrot Oil"),
        ("Sorbitan", "Sorbitan", "Sorbitan"),
        ("Sorbitol Anhydrides", "Header", "Sorbitol Anhydrides"),
    ],
)
def test_batch10_inactive_exact_aliases_and_new_identities_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Omega-3 Cod Liver Oil", "Fish Liver oil", "Cod Liver Oil"),
        ("Marine Lipid Oil", "Marine oil (unspecified)", "Fish Oil"),
        ("Romega 30", "Fish roe oil", "Herring Roe"),
        ("stabilized L-Alpha-Glycerophosphatidylcholine", "Alpha-GPC", "Alpha GPC"),
        ("wild crafted Red Raspberry", "Red Raspberry", "Red Raspberry"),
        ("Carrot Seed Oil", "Carrot oil", "Carrot Seed Oil"),
    ],
)
def test_batch11_active_aliases_and_new_botanical_identity_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


def test_batch11_inactive_high_pc_soy_lecithin_maps_to_existing_soy_lecithin(normalizer):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        "high PC Soy Lecithin", ingredient_group="lecithin"
    )

    assert mapped is True
    assert standard_name == "Soy Lecithin"


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("AcaiRich", "Acai", "Acai"),
    ],
)
def test_batch12_active_exact_brand_alias_maps(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Bone Gelatin", "Gelatin", "Gelatin Capsule"),
        ("Clary Sage Oil", "Clary sage", "Clary Sage Oil"),
        ("Curcuma Oil", "TBD", "Curcuma Oil"),
        ("Rapeseed Vegetable Oil", "Rapeseed Oil", "Rapeseed Oil"),
        ("Soya Oil", "Soybean Oil", "Soy Bean Oil"),
        ("mountain spring Water", "Water", "Spring Water"),
        ("natural Orange and Tangerine flavors", "Flavor", "Natural Citrus-Orange Flavor"),
        ("organic Oat Bran oil", "Oat bran oil", "Oat Bran Oil"),
        ("Carob fruit extract", "Carob", "Carob (St. John's Bread)"),
    ],
)
def test_batch12_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("minor Glycolipids", "Blend (non-nutrient/non-botanical)", "Minor Glycolipids (Descriptor)"),
        ("Diglycerol Monooleate", "Diglycerol monooleate", "Diglycerol Monooleate"),
        ("Glycerol Monooleate", "TBD", "Glycerol Monooleate"),
        ("Halal Gelatin", "Gelatin", "Gelatin Capsule"),
        ("Middle Chain Triglycerides", "Medium chain triglycerides (MCT)", "Medium Chain Triglycerides"),
        ("Modified Sunflower Lecithin", "lecithin", "Sunflower Lecithin"),
        ("Natural creamy Orange flavor", "Orange (unspecified)", "Natural Orange Flavor"),
        ("Palm fruit stearin", "Tristearate", "Palm Stearin"),
        ("Roasted Carob powder", "Carob", "Carob (St. John's Bread)"),
    ],
)
def test_batch13_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("20:1 {Acai} extract", "Acai", "Acai"),
        ("Acai 2:1 extract", "Acai", "Acai"),
        ("Acai Berry 20:1 extract", "Acai", "Acai"),
    ],
)
def test_batch14_active_exact_aliases_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("White Edible Ink", "Color", "White Edible Ink (Descriptor)"),
        ("natural Citrus flavoring", "Flavor", "Natural Citrus Flavor"),
        ("Cochineal C175470", "Cochineal", "Cochineal"),
        ("Cuprous Oxide", "Copper oxide", "Cuprous Oxide"),
        ("Lecithin oil", "lecithin", "Lecithin Oil"),
        ("Nonionic Surfacant", "Surfactant", "Nonionic Surfactant (Descriptor)"),
        ("100% expeller pressed, organic, extra virgin Coconut Oil", "coconut oil", "Extra Virgin Coconut Oil"),
        ("Black Sesame Seed Oil", "Sesame Oil", "Sesame Seed Oil"),
        ("Carob liquid", "Carob", "Carob (St. John's Bread)"),
        ("Sorbitan Monooleate NF", "Sorbitan Ester", "Sorbitan Monooleate"),
        ("Tilapia Fish Gelatin", "Gelatin", "Gelatin Capsule"),
        ("non-GMO modified Tapioca Starch", "Starch", "Modified Food Starch"),
    ],
)
def test_batch14_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Chinese Goldthread", "Chinese Goldthread", "Coptis"),
    ],
)
def test_batch15_active_exact_aliases_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("and water", "Water", "Purified Water"),
        ("Polymethylacrylate", "Header", "Polymethylacrylate"),
        ("Metal Salts", "Metal Salt (unspecified)", "Metal Salts (Descriptor)"),
        ("Oxalic Acid", "Oxalic Acid", "Oxalic Acid"),
        ("Phosphatidylcholine lecithin", "phosphatidylcholine", "Sunflower Lecithin"),
        ("Polyunsaturated Oils", "Polyunsaturated Fat", "Polyunsaturated Oils (Descriptor)"),
        ("added Color", "Color", "Added Color (Descriptor)"),
        ("Carob, Natural, Powder", "Carob", "Carob (St. John's Bread)"),
        ("D-Delta Tocopherol", "Vitamin E (delta tocopherol)", "Tocopherol (Preservative)"),
        ("DL-Alpha Tocopheryl", "Vitamin E (alpha-tocopherol)", "Tocopherol (Preservative)"),
        ("Disodium Edetate", "EDTA", "Disodium Edetate"),
        ("Sunflower Lecithin oil", "lecithin", "Sunflower Lecithin"),
    ],
)
def test_batch15_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Anchovies", "Fish", "Fish"),
        ("Sardines", "Fish", "Fish"),
        ("Shellac glaze", "Shellac", "Shellac"),
        ("Isopropyl Alcohol", "Alcohol", "Isopropyl Alcohol"),
        ("N-Butyl Alcohol", "Alcohol", "N-Butyl Alcohol"),
        ("Natural Lemon flavor Oil", "Lemon", "Natural Lemon Flavor"),
        ("natural Orange Citrus Oil", "Orange (unspecified)", "Natural Citrus-Orange Flavor"),
        (
            "Expeller-pressed Chia (Salvia hispanica L.) seed oil",
            "Chia",
            "Chia Seed Oil",
        ),
        ("Distilled Monoglycerides", "Monoglyceride", "Distilled Monoglycerides"),
        ("Gelatin Bovine", "Bovine (unspecified)", "Gelatin Capsule"),
        ("Glycerin Monooleate", "Glyceride", "Glycerol Monooleate"),
        ("Glycerin Monostearate", "TBD", "Glycerol Monostearate"),
        (
            "High Oleic Safflower and/or Sunflower Oil",
            "Blend (Fatty Acid or Fat/Oil Supplement)",
            "High Oleic Safflower/Sunflower Oil",
        ),
        ("Lemon flavor Oil", "Lemon", "Lemon Flavor Oil"),
        ("Medium Chain Fatty Acids", "Medium chain triglycerides (MCT)", "Medium Chain Fatty Acids"),
        ("Mixed Carotene", "carotenoids", "Carotene, Natural"),
        ("Annato seed extract", "Color", "Annatto (Variants)"),
        ("Sodium Thiosulfate", "Sodium Thiosulfate", "Sodium Thiosulfate"),
        ("White Rice Bran Oil", "Rice Bran", "Rice Bran Oil"),
        ("Tapioca Gelatin", "Starch", "Tapioca Gelatin"),
    ],
)
def test_batch16_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("all Natural Flavoring", "Flavor", "Natural Flavors"),
        ("black edible Ink", "Edible ink", "Black Edible Ink (Descriptor)"),
        ("highly refined Soybean Oil", "Soybean Oil", "Soy Bean Oil"),
        ("pharmaceutical Gelatin", "Gelatin", "Gelatin Capsule"),
        ("10 minims Norwegian cod liver oil", "Fish Liver oil", "Cod Liver Oil (as carrier)"),
        ("Acetylated Monoglyceride", "Acetylated Monoglyceride", "Vegetable Acetoglycerides"),
        ("Algae Omega-3 Oil", "Algal Oil", "Algal Oil (as carrier)"),
        ("Ammonium Hydrogen Carbonate", "Ammonium carbonate", "Ammonium Hydrogen Carbonate"),
        ("Aqueous Shellac", "Coating", "Shellac"),
        ("Buffalo Gelatin", "Gelatin", "Gelatin Capsule"),
        ("Citrus Peel Oil Extract", "Sweet Orange", "Citrus Peel Oil Extract"),
        ("Coconut Oil MCT", "coconut oil", "Medium Chain Triglycerides"),
        ("D-Alpha Tocopherols", "Vitamin E (alpha tocopherol)", "Tocopherol (Preservative)"),
        ("Essential Oil of Orange", "Orange (unspecified)", "Natural Orange Flavor"),
        ("FD&C Blue", "Color", "FD&C Blue (Descriptor)"),
        ("natural food grade Citrus Oil", "Citrus (unspecified)", "Natural Citrus Flavor"),
    ],
)
def test_batch17_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


def test_batch17_partially_hydrogenated_corn_oil_routes_to_harmful(normalizer):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Partially Hydrogenated Corn Oil", [], ingredient_group="Hydrogenated Corn Oil"
    )

    assert mapped is True
    assert standard_name == "Partially Hydrogenated Corn Oil"


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("High Choline Lecithin", "lecithin", "Lecithin"),
        ("liquid Soy Lecithin", "lecithin", "Lecithin"),
        ("Trimethylglycerine Hydrochloride", "Betaine", "TMG"),
        ("Ascorbyl Palmitate and Ascorbate", "Blend (Combination)", "Vitamin C"),
    ],
)
def test_batch18_active_exact_aliases_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("DHA/EPA Algal Oil", "Algal Oil", "Algal Oil (as carrier)"),
        ("Diglyceryl Monooleate", "Diglycerol monooleate", "Diglycerol Monooleate"),
        ("Ethyl Acrylate Copolymer", "Polyacrylate", "Ethyl Acrylate Copolymer"),
        ("FD&C Red", "Color", "FD&C Red (Descriptor)"),
        ("Forest Fruits flavor", "Flavor", "Forest Fruits Flavor"),
        ("Glycerin Fatty Ester", "Glycerol", "Glycerin Fatty Acid Esters"),
        ("Glyceryl Oleate", "Glyceryl oleate", "Glycerol Monooleate"),
        ("Halal Bovine Gelatin", "Gelatin", "Gelatin Capsule"),
    ],
)
def test_batch18_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,forms,ingredient_group,expected",
    [
        ("Nutritional Yeast", [], "Nutritional Yeast", "Saccharomyces cerevisiae (yeast)"),
        ("Kiwi", [], "Kiwi", "Kiwifruit"),
        ("D-Phenylalanine", [], "D-phenylalanine", "D-Phenylalanine"),
        ("organic Microalgae", ["organic"], "Blue-Green Algae", "Blue-Green Algae"),
        ("DAO2", ["Porcine Kidney Extract"], "Kidney", "Kidney Tissue"),
        ("Beef Tissue", [], "Beef", "Beef Tissue"),
        ("Betaine Monohydrate", [], "Betaine", "Betaine Monohydrate"),
        ("Glucose Polymers", [], "Glucose polymer (unspecified)", "Glucose Polymers"),
        ("Sodium Phosphate", [], "Sodium Phosphate", "Sodium Phosphate"),
    ],
)
def test_batch19_exact_aliases_and_group_fallback_map(
    normalizer, name, forms, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, forms, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,forms,ingredient_group,expected",
    [
        ("Sweet Wormwood (leaf) Oil", [], "Sweet Annie", "Sweet Wormwood Leaf Oil"),
        ("Borage", ["Gamma-Linolenic Acid"], "Borage", "Borage Seed Oil"),
        ("Earthrise", ["Spirulina"], "TBD", "Spirulina"),
        ("Orgen-Si", ["Bamboo Extract"], "Bamboo", "Silica"),
    ],
)
def test_batch20_active_exact_aliases_map(normalizer, name, forms, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, forms, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


def test_batch20_isopropylnorsynephrine_routes_to_banned(normalizer):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Isopropylnorsynephrine", [], ingredient_group="Isopropylnorsynephrine"
    )

    assert mapped is True
    assert standard_name == "Isopropylnorsynephrine"


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("White Milo", "Broom Corn", "White Milo"),
        ("Bovine tissue", "Bovine (unspecified)", "Beef Tissue"),
        ("Flour", "Flour (unspecified)", "Flour (Unspecified)"),
        ("neutral Spirits", "TBD", "Alcohol (Ethanol)"),
    ],
)
def test_batch20_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,forms,ingredient_group,expected",
    [
        ("Cherokee Rose 4:1 extract", [], "Cherokee Rose", "Cherokee Rose Fruit"),
        ("Orgen-Bio", ["Biotin"], "Biotin", "Vitamin B7 (Biotin)"),
        ("Artichoke Whole Extract", [], "Artichoke", "Globe Artichoke"),
        ("Avocado", [], "Avocado", "Avocado Fruit"),
        ("Coleus root extract", ["Coleus forskohlii", "Forskolin"], "Coleus", "Coleus Forskohlii Root"),
    ],
)
def test_batch21_active_exact_aliases_map(normalizer, name, forms, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, forms, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Jasmine Rice Bran", "Rice Bran", "Jasmine Rice Bran"),
        ("Rice Substrate", "Rice", "Rice Substrate"),
        ("Sorghum Substrate", "Broom Corn", "Sorghum Substrate"),
        ("Vegetable and Fruit Juices", "Header", "Vegetable and Fruit Juices"),
    ],
)
def test_batch21_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("FD&C Red", "Color", "FD&C Red (Descriptor)"),
        ("Mixed D-Tocopherols", "Vitamin E (mixed tocopherols)", "Tocopherol (Preservative)"),
        ("Forest Fruits flavor", "Flavor", "Forest Fruits Flavor"),
        ("Forest Fruits flavour", "Flavor", "Forest Fruits Flavor"),
        ("Hydroxymethyl Starch", "TBD", "Hydroxymethyl Starch"),
        ("Mono {Glycerides} & Di-Glycerides", "Blend (non-nutrient/non-botanical)", "Mono and Diglycerides"),
        ("Natural Mixed Berry/Orange Flavor", "Flavor", "Natural Flavors"),
        ("Oat Oil", "Oat Oil", "Oat Oil"),
        ("Paprika fruit extract", "Capsicum", "Paprika Extract"),
        ("Polyethylene Glycol 200", "Polyethylene glycol", "Polyethylene Glycol (PEG)"),
        ("Polyglyceryl ester", "Polyglycerols", "Polyglyceryl Ester"),
        ("Polygycitol Syrup", "Polyglycitol", "Polyglycitol Syrup"),
        ("Prenatal Gelatin", "Gelatin", "Gelatin Capsule"),
        ("Providone", "Povidone", "Povidone"),
        ("Rice Wax", "Rice Wax", "Rice Wax"),
        ("Safflower Oil Glyceride", "Blend (Combination)", "Safflower Oil Glyceride"),
        ("Sodium Copper Chlorophyll", "Chlorophyllin", "Sodium Copper Chlorophyllin"),
        ("Sunflower seed Lecithin Oil", "lecithin", "Sunflower Lecithin"),
        ("Sunflower seed Oil Glyceride", "Blend (Combination)", "Sunflower Seed Oil Glyceride"),
        ("Trimethyl Citrate", "Betaine", "Trimethyl Citrate"),
    ],
)
def test_batch22_softgels_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Ink", "Ink", "Ink (Descriptor)"),
        ("Glycerin Fatty Ester", "Glycerol", "Glycerin Fatty Acid Esters"),
        ("Carob and caramel", None, "Carob and Caramel"),
        ("Alpha-Terpineol", "Alpha-terpineol", "Alpha-Terpineol"),
        ("Omega-3 Triglycerides", "Omega-3", "Omega-3 Triglycerides"),
        ("Long Chain Triglycerides", "TBD", "Long Chain Triglycerides"),
        ("Palm Glycerin", "TBD", "Vegetable Glycerin"),
        ("Proprietary Food Emulsifier", "Emulsifier", "Proprietary Food Emulsifier"),
        ("Ultra-Pure Marine Oil", "Marine oil (unspecified)", "Ultra-Pure Marine Oil"),
        ("Trace metals", "Blend (Combination)", "Trace Metals"),
    ],
)
def test_batch23_softgels_inactive_exact_aliases_and_new_identities_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,forms,ingredient_group,expected",
    [
        ("Aricularia auricula", [], "Silver Ear Fungus", "Wood Ear Mushroom"),
        (
            "Cornsilk Zea mays Stigma and Style Extract",
            [],
            "Corn",
            "Corn Silk",
        ),
        ("Poten-Zyme(R) Foiic Acid", [], "Vitamin B9 (folic acid)", "Vitamin B9 (Folate)"),
        (
            "Rhododendron caucasicum Extract",
            [],
            "Rhododendron caucasicum",
            "Rhododendron caucasicum",
        ),
    ],
)
def test_garden_of_life_active_unmapped_labels_map(
    normalizer, name, forms, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, forms, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("non-GMO Vitamin E", "Vitamin E (unspecified)", "Tocopherol (Preservative)"),
        (
            "Probiotic microorganisms",
            "Blend (non-nutrient/non-botanical)",
            "Probiotic Microorganisms (Descriptor)",
        ),
        (
            "Bovine hide Collagen Peptides",
            "Collagen Peptides",
            "Bovine Hide Collagen Peptides",
        ),
        (
            "Bovine Hide Collagen Peptides",
            "Collagen Peptides",
            "Bovine Hide Collagen Peptides",
        ),
        ("organic Arabica fair trade Coffee", "Coffee", "Arabica Coffee"),
        ("Arabica Coffee", "Coffee", "Arabica Coffee"),
        (
            "Garden of Life(R) organic extra virgin Coconut Oil",
            "Coconut Oil",
            "Extra Virgin Coconut Oil",
        ),
        ("Non-GMO Strawberry extract", "Strawberry", "Strawberry"),
        ("colorant", "Color", "Added Color (Descriptor)"),
        ("Algae Omega-3 Oil", "Algal Oil", "Algal Oil (as carrier)"),
        ("non-GMO Sunflower Oil", "Sunflower Oil", "Sunflower Oil"),
        ("organic unsweetened Chocolate", "Chocolate", "Unsweetened Chocolate"),
        ("Corn", "Corn", "Corn (Source Descriptor)"),
        ("Mineral", "Blend", "Mineral (Descriptor)"),
        ("organic Chia", "Chia", "Organic Chia"),
    ],
)
def test_garden_of_life_inactive_unmapped_labels_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,forms,ingredient_group,expected",
    [
        ("Cormino seed extract", [], "Cumin", "Cumin Seed"),
        ("Frauenmantle leaf extract", [], "Lady's Mantle", "Lady's Mantle Leaf"),
        ("Horsemint leaf extract", [], "Horsemint", "Horsemint Leaf"),
        ("Wild olive leaf extract", [], "Olive ", "Olive Leaf Extract"),
    ],
)
def test_gummies_active_unmapped_labels_map(
    normalizer, name, forms, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, forms, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("MCT Vegetable Oil", "Header", "Medium Chain Triglycerides"),
        ("Broad Spectrum Hemp Oil", "Hemp oil", "Hemp Extract"),
        ("Caramel Sugar Syrup", "Header", "Caramel Sugar Syrup"),
        ("Vegetable", "Blend", "Vegetable (Descriptor)"),
        ("Vegetable Concentrate", "Blend", "Vegetable Concentrate"),
        ("Lysine Monohydrochloride", "Lysine", "Lysine Monohydrochloride"),
    ],
)
def test_gummies_nature_inactive_unmapped_labels_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Marine Algae Oil", "Algal Oil", "Algal Oil (as carrier)"),
        ("DHA/EPA Algal Oil", "Algal Oil", "Algal Oil (as carrier)"),
        ("Polyacrylic Resin", "TBD", "Polyacrylic Resin"),
        ("Ethyl Acrylate Copolymer", "Polyacrylate", "Ethyl Acrylate Copolymer"),
        ("Glyceryl Oleate", "Glyceryl oleate", "Glycerol Monooleate"),
    ],
)
def test_nordic_softgels_inactive_unmapped_labels_map(
    normalizer, name, ingredient_group, expected
):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert standard_name == expected


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Magtein Magnesium L-Threonate", "Magnesium"),
        ("NIAGEN Nicotinamide Riboside", "Nicotinamide Riboside"),
        ("N-Acetyl L-Cysteine", "N-Acetyl Cysteine"),
        ("Glucosamine Sulfate 2KCI", "Glucosamine"),
        ("Glucosamine Sulfate 2NaCl", "Glucosamine"),
        ("Pylopass Lactobacillus reuteri", "Lactobacillus Reuteri"),
        ("Bitter Orange Citrus Bioflavonoids", "Bitter Orange"),  # routes to bitter orange risk territory, not generic citrus bioflavonoids
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
        ("S. cerevisiae", "cerevisiae"),
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
        ("Bifidobacterium breve", "Bifidobacterium Breve"),
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
        ("Vanadium Amino Acid Chelate", "Vanadyl Sulfate"),
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
        ("Beta Zea Carotene", "Vitamin A"),
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
        ("Isatis", "Isatis tinctoria"),
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
        ("Vitamin K2-7", "Vitamin K"),
        ("MenaQ7 Vitamin K2", "Vitamin K"),
        ("Quatrefolic (6S)-5-Methyltetrahydrofolate, Glucosamine Salt", "Vitamin B9"),
        ("Quatrefolic (6S)-5-Methyltetrahydrofolic Acid Glucosamine Salt", "Vitamin B9"),
        ("(6S)-N5-Methyltetrahydrofolic Acid Calcium Salt", "Vitamin B9"),
        ("Magnesium Malate Trihydrate", "Magnesium"),
        ("N-Acetyl L-Carnitine Hydrochloride", "L-Carnitine"),
        ("Molybdenum Citrate", "Molybdenum"),
        ("Ferrous Fumarate Anhydrous", "Iron"),
        ("DeltaGold(TM) Tocotrienol", "Vitamin E"),
        ("Nutri-Nano Alpha Lipoic Acid", "Alpha Lipoic Acid"),
        ("Aquamin F", "Calcium"),
        ("Aquamin TG", "Calcium"),
        ("Sucrase", "Digestive Enzymes"),
        ("Protease, Fungal", "Digestive Enzymes"),
        ("Tolerase G", "Digestive Enzymes"),
        ("Astralagus", "Astragalus"),
        ("Buffalo Liver Concentrate", "Organ Extracts"),
        ("Green Peppers", "Green Bell Pepper"),
        ("Gardenia fruit extract", "Gardenia"),
        ("Glehnia root extract", "Glehnia"),
        ("Apricot seed extract", "Apricot"),
        ("Methyliberine", "Methylliberine"),
        ("CoreBiome Tributyrin", "Butyric Acid"),
        ("OpiTAC Glutathione", "Glutathione"),
        ("Lactium", "Casein Hydrolysate"),
        ("Cycloastragenol", "Cycloastragenol"),
        ("Senactiv", "Ginseng"),
        ("Dymethazine", "Dymethazine"),
        ("Laxosterone", "5a-Hydroxy Laxogenin"),
        ("Scullcap", "Skullcap"),
        ("Licorice (Glycyrrhiza glabra) root and rhizome extract", "Licorice"),
        ("Ashwagandha (Withania somnifera) root 15:1 extract", "Ashwagandha"),
        ("Black Cohosh (Actaea racemosa) root & rhizome extract", "Black Cohosh"),
        ("Stinging Nettle (Urtica dioica) root 10:1 extract", "Stinging Nettle"),
        ("Green Tea ext.", "Green Tea"),
        ("Gingko leaf extract", "Ginkgo"),
        ("Leucoselect Grape seed extract", "Grape Seed"),
        ("Noni 4:1 extract", "Noni"),
        ("SDG", "Lignans"),
        ("Piper longum fruit extract", "Long Pepper"),
        ("Bacopa monnieri Whole Herb Extract", "Bacopa"),
        ("Acai Berry Whole Fruit Extract", "Acai"),
        ("Cissus quadrangularis Stem Extract", "Winged Treebine"),
        ("BioVin", "Resveratrol"),
        ("Phase 2", "Common Bean Extract"),
        ("Vitashine", "Vitamin D"),
        ("California Poppy extract", "California Poppy"),
        ("Chinese Salvia", "Danshen"),
        ("Gamma Carotene", "Vitamin A"),
        ("Full Strength Pancreatin", "Digestive Enzymes"),
        ("Yaeyama Chlorella", "Chlorella"),
        ("l3C", "Diindolylmethane"),
        ("Gymnemic Acid", "Gymnema Sylvestre"),
        ("Female Hops cone extract", "Hops"),
        ("TryptoGold", "L-Tryptophan"),
        ("Trachea", "Organ Extracts"),
        ("Ovarian Tissue", "Organ Extracts"),
        ("Sodium Succinate", "Succinic Acid"),
        ("Lagerstroemia speciosa leaf extract", "Corosolic Acid"),
        ("GliSODin", "Superoxide Dismutase"),
        ("Zembrin", "Mesembrine"),
        ("Xanthoparmelia scabrosa", "Xanthoparmelia"),
        ("Yeast Fermentate, Dried", "yeast fermentate"),
        ("EpiCor dried Yeast Fermentate", "yeast fermentate"),
        ("Soynatto Fermented Soyfood", "Isoflavones"),
        ("MaquiBright Aristotelia chilensis berry standardized extract", "Maqui"),
        ("EVNolMax", "Vitamin E"),
        ("ERr 731", "Rhaponticin"),
        ("Ceramide-PCD", "Ceramides"),
        ("Tribulosides", "Tribulus"),
        ("Blue Vervain", "Blue Vervain"),
        ("Paeoniflorin", "paeoniflorin"),
        ("Isovitexin", "isovitexin"),
        ("Gamma-Butyrobetaine Hydrochloride", "gamma-butyrobetaine"),
        ("Gamma-Glutamylcysteines", "Glutathione"),
        ("GKG", "gkg"),
        ("A-KIC", "a-kic"),
        ("2-Beta Coxatene", "2-beta coxatene"),
        ("Sunvitol", "Vitamin E"),
        ("N-Methyl-D-Aspartic Acid", "n-methyl-d-aspartic acid"),
        ("Enzopharm(R) Plus", "enzopharm"),
        ("ATPro", "atpro"),
        ("Mitopure Urolithin A", "Urolithin A"),
        ("Phytopin", "Pine Bark"),
        ("PhytoSure", "phytosure"),
        ("Peat extract", "peat extract"),
        ("Oat", "Oat (Generic)"),
        ("Willow", "White Willow Bark"),
        ("Sirtmax", "Kaempferia"),
        ("Lactotripeptides", "lactotripeptides"),
        ("FRAC(R)", "frac(r)"),
        ("EP107", "ep107"),
        ("DNF-10 Yeast Hydrolysate", "Yeast Fermentate"),
        ("Cyplexinol", "cyplexinol"),
        ("AC-11", "Cat's Claw Bark"),
        ("Propionyl L-Carnitine", "L-Carnitine"),
        ("Prebiotic FOS", "Prebiotics"),
        ("N, N-Dimethyl Glycine HCl", "dimethyl glycine"),
        ("Inositol Nicotinate", "Vitamin B3"),
        ("Niacin Niacinamide & Inositol Hexanicotinate", "Vitamin B3"),
        ("L-Theanine Suntheanine", "L-Theanine"),
        ("L-Glutamic Acid HCl", "L-Glutamic Acid"),
        ("Silicic Acid", "Silicon"),
        ("Magnesio", "Magnesium"),
        ("Porcine (Sus scrofa) Bone Marrow", "Organ Extracts"),
        ("Mammary", "Organ Extracts"),
        ("Mastic tree", "Mastic Gum"),
        ("Macapure", "Maca"),
        ("MacaPure Maca extract", "Maca"),
        ("Maca 0.6% extract", "Maca"),
        ("Milk Thistle powdered extract", "Milk Thistle"),
        ("Milk Thistle Fruit and Seed Extract", "Milk Thistle"),
        ("Pycrinil Artichoke extract", "Cynarin"),
        ("Pueraria mirifica extract", "Pueraria Mirifica"),
        ("Oat Aerial Parts Extract", "Oat Straw"),
        ("Motherwort Aerial Parts Extract", "Motherwort"),
        ("Mojave Yucca root extract", "Yucca"),
        ("Mate leaf extract", "Yerba Mate"),
        ("Laminaria digitata", "Kelp"),
        ("Ivy Leaf Extract", "Ivy"),
        ("Linden", "Linden"),
        ("Neumentix", "Spearmint"),
        ("NEM Natural Eggshell Membrane", "nem"),
        ("Mythocondro", "mythocondro"),
        ("Mobilee", "mobilee"),
        ("Mirtogenol", "Bilberry"),
        ("Minor Cannabinoids", "minor cannabinoids"),
        ("Micronized Purified Flavonoid Fraction", "Diosmin"),
        ("ReceptoMax Precision Release Profile", "receptomax precision release profile"),
        ("Syntol Digestive Yeast Cleanse", "syntol digestive yeast cleanse"),
        ("True Food Superpotency Soyagen", "true food superpotency soyagen"),
        ("ImmunoLin", "immunolin"),
        ("L-Arabinose", "Arabinose"),
        ("Sarcosine", "sarcosine"),
        ("Rutaecarpine", "rutaecarpine"),
        ("Marine Chondroitin Sulphate", "Chondroitin"),
        ("Huperzine", "Huperzine A"),
        ("Horsetail leaf extract", "Horsetail"),
        ("Horsetail leaf & stem extract", "Horsetail"),
        ("Horsetail (Equisetum arvense) 4:1 aerial parts extract", "Horsetail"),
        ("Horse Chestnut 20% extract", "Horse Chestnut Seed"),
        ("Holy Basil (Ocimum sanctum) leaf supercritical CO2 extract", "Holy Basil"),
        ("Hawthorn berry ext.", "Hawthorn"),
        ("Guggul ext.", "Guggul"),
        ("Guggulipid Gum Extract", "Guggul"),
        ("Green Tea leaf 50% extract", "Green Tea"),
        ("Green Tea Leaf Extract, Aqueous", "Green Tea"),
        ("Grape 95% extract", "Grape"),
        ("Ginkgold", "Ginkgo"),
        ("Ginkgoflavonglycosides", "Ginkgo"),
        ("Garcinia cambogia Super CitriMax clinical strength", "Garcinia Cambogia"),
        ("FruiteX-B PhytoBoron", "Boron"),
        ("ChromeMate CM-100M", "Chromium"),
        ("ChromeMate CM-100", "Chromium"),
        ("Chromax Chromium Picolinate", "Chromium"),
        ("Coenzyme Vitamin B2", "Riboflavin"),
        ("Cinnamon Bark Extract, Dried", "Cinnamon"),
        ("Chili Fruit, Seed Extract", "Capsaicin"),
        ("Chicken Collagen", "Collagen"),
        ("Chastetree berry extract", "Chasteberry"),
        ("Chaste Berry Fruit Extract", "Chasteberry"),
        ("Conjugated Bile Acid", "conjugated bile acid"),
        ("Collinsonia root PE", "Stoneroot"),
        ("CogniBoost", "cogniboost"),
        ("Cocoabuterol", "cocoabuterol"),
        ("Cowslip", "Cowslip"),
        ("Diatomaceous Earth", "diatomaceous earth"),
        ("DHQVital Dihydroquercetin", "dhqvital dihydroquercetin"),
        ("Dihydroquercetin-3-Rhamnoside", "Taxifolin"),
        ("ETAS", "etas"),
        ("Ecoganic Super Fruits", "ecoganic super fruits"),
        ("Emothion", "Glutathione"),
        ("Ergogen-XT", "ergogen"),
        ("Eurypeptides", "Tongkat Ali"),
        ("Flavanols", "flavanols"),
        ("GBBGO", "gbbgo"),
        ("Glycosaponins", "glycosaponins"),
        ("Immune Support Response", "immune support response"),
        ("Glucanase", "Digestive Enzymes"),
        ("Chinese Cinnamon (Cinnamomum cassia) bark powder", "Cinnamon"),
        # identity_bioactivity_split Phase 2: Camu Camu now routes to source
        # botanical camu_camu (not vitamin_c). Vitamin C marker credit lives in
        # delivers_markers[] gated on label standardization.
        ("Camu Camu Fruit Extract", "Camu Camu"),
        ("Calcium Glycinate", "Calcium"),
        ("Boswellin Super", "Boswellia"),
        ("Boswella extract", "Boswellia"),
        ("Bioperine Nature’s Thermonutrient", "Piperine"),
        ("Bilberry Berry Extract", "Bilberry"),
        ("Capros", "Amla"),
        ("AlphaSize", "Alpha GPC"),
        ("Acetyl L Carnitine Hydrochloride", "L-Carnitine"),
        ("Bovine (Bos taurus) Placenta", "Organ Extracts"),
        ("Bovine (Bos taurus) Lymph", "Organ Extracts"),
        ("CQR-300 Cissus quadrangularis stem and leaf extract", "Winged Treebine"),
        ("Buchu leaves 4:1 extract", "Buchu"),
        ("Broccoli Seed, Sprout Extract", "Broccoli"),
        ("Broccoli Bud, Stem Extract", "Broccoli"),
        ("Broccoli (Brassica oleracea) floret and stalk concentrate", "Broccoli"),
        ("Boneset aerial parts extract", "Boneset"),
        ("Blackcurrant freeze-dried extract", "Black Currant"),
        ("Black Tea leaves extract", "Black Tea"),
        ("Calcium Glycerophosphate", "calcium glycerophosphate"),
        ("Calcium Caprylate", "calcium caprylate"),
        ("Crominex 3+", "chromium"),  # Now maps via IQM alias → chromium parent
        ("Beta-Ecdysterone", "Ecdysterones"),
        ("Carotene, Natural", "carotene, natural"),
        ("Malate", "malate"),
        ("Lactococcus lactis strain plasma", "Probiotics"),
        ("Benegut Perilla Leaf Extract", "Perilla"),
        ("Bacosides A & B", "Bacopa"),
        ("Avocado/Soy Unsaponifiables", "avocado/soy unsaponifiables"),
        ("Anti-Fungi 11X-88", "anti-fungi 11x-88"),
        ("Anti-Fungi 10X-88", "anti-fungi 10x-88"),
        ("Andrographis aerial extract", "Andrographis"),
        ("Andrograph extract", "Andrographis"),
        ("Amla whole fruit powder", "Amla"),
        ("Alpha-Glycosyl Isoquercitrin", "Quercetin"),
        ("ActivAMP Gynostemma pentaphyllum Extract", "Gypenosides"),
        ("Actazin", "Kiwifruit"),
        ("AMP-XT", "amp-xt"),
        ("resVida", "Resveratrol"),
        ("pTeroPure Pterostilbene", "Pterostilbene"),
        ("organic NeuroFactor whole Coffee", "Coffee Fruit"),
        ("organic Full-Spectrum Ashwagandha  root  powder", "Ashwagandha"),
        ("grassfed Liver", "Organ Extracts"),
        ("grass-fed Bovine", "Organ Extracts"),
        ("dried Noni", "Noni"),
        ("certified organic Chlorella powder", "Chlorella"),
        ("Yodo", "Iodine"),
        ("Yellow Maca Root Extract", "Maca"),
        ("Yacon", "Yacon"),
        ("XanthoForce Hops extract", "Hops"),
        ("Vitex agnus castus extract", "Chasteberry"),
        ("Watercress Aerial Parts Extract", "Watercress"),
        ("naturally-occurring Caffeine", "Caffeine"),
        ("1-Piperoylpiperidine", "Piperine"),
        ("99% pure Hemp Isolate", "hemp isolate"),
        ("L-Asparagine", "l-asparagine"),
        ("Oleamide", "oleamide"),
        ("Phloridzin", "Phlorizin"),
        ("geniVida Genistein", "Genistein"),
        ("Uridine-5'-Monophosphate Heptahydrate Disodium", "Uridine"),
        ("Triacetyluridine", "Uridine"),
        ("Tiamina", "Vitamin B1"),
        ("ZinMax", "Zinc"),
        ("certified organic AlgaeCal", "Calcium"),
        ("acid-stable Protease", "Digestive Enzymes"),
        ("acid stable Protease", "Digestive Enzymes"),
        ("Vanadium Glycinate", "Vanadyl Sulfate"),
        ("Total Beta Glucan", "Beta-Glucan"),
        ("Super CitriMax Garcinia extract", "Garcinia"),
        ("Sulphoraphane", "Sulforaphane"),
        ("St. John’s Wort", "St. John's Wort"),
        ("St. John's Wort Flower, Leaf Extract", "St. John's Wort"),
        ("St. John's Wort Flower Head Extract", "St. John's Wort"),
        ("VitaCholine", "Choline"),
        ("WellTrim iG (IGOB131) African Mango (Irvingia gabonensis) seed extract", "African Mango"),
        ("Wild Yam (Dioscorea opposita) rhizome standardised extract", "Wild Yam"),
        ("whole Oranges", "Orange"),
        ("240 mg whole Oranges", "Orange"),
        ("organic Mimosa pudica", "Mimosa pudica"),
        ("organic Cordyceps (Cordyceps militaris) fruiting body extract", "Cordyceps"),
        ("dry sprouted Barley", "Barley"),
        ("dry Wheat Grass", "Wheatgrass"),
        ("Yucca 4:1 extract", "Yucca"),
        ("Wakame powder", "Fucoidan"),
        ("Uva Ursi 3:1 extract", "Uva Ursi"),
        ("Sweet Fennel seed powder", "Fennel"),
        ("Suma root 4:1 extract", "Suma Root"),
        ("Star Anise Seed Extract", "Star Anise"),
        ("Tea Tree Oil", "Tea Tree"),
        ("total Sulfur", "total sulfur"),
        # Regression: Eicosatrienoic Acid (C20:3n-3) was unmapped in 2 Softgels PIDs (320013, 320017)
        # because it appeared as a flat active (not nested), so contextual suppression never fired.
        # Fix: added IQM form "eicosatrienoic acid (20:3n-3)" under omega_3 key.
        ("Eicosatrienoic Acid", "Omega-3"),
        ("eicosatrienoic acid", "Omega-3"),
        ("ESA", "Omega-3"),
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
        ("FD&C Blue # 1"),
        ("FD&C Blue #2 Lake"),
        ("FD&C Blue #2 Aluminum Lake"),
        ("FD&C Red #40 Aluminum Lake"),
        ("FD&C Red # 40"),
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
        # hydrogenated Cottonseed oil / Sterotex NF removed — ADD_HYDROGENATED_OILS
        # intentionally dropped from harmful_additives.json (low concern for supplements)
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
        ("Herbal Extracts"),
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
    "name",
    [
        ("Carotenoid Mix"),
        ("Carotenoid MIx"),
        ("Enzymes"),
        ("Sulfate"),
        ("Digestive Aids/Enzymes"),
        ("Bioactive Enzymes & Proteins"),
        ("Co-Nutrients"),
        ("Stomach"),
        ("Whole Food Enzymes"),
        ("Complete Digestive Support"),
        ("80 mg broccoli"),
        ("8 mg cabbage"),
        ("Proprietary Mix of Curcumin"),
        ("Nitrate"),
        ("Nitrates"),
        ("50 mg carrots"),
        ("Total Silymarin"),
        ("Macamides and Macaenes"),
        ("Passion Factors"),
    ],
)
def test_section_header_artifacts_are_skip_classified(normalizer, name):
    assert normalizer._is_nutrition_fact(name) is True


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
        ("Aorta"),
        ("Brain"),
        ("Pineal"),
        ("Wheat Bran"),
        ("Sustained Energy Support"),
        ("Sendara"),
        ("The Fiber Expert"),
        ("Plant-Gest Support"),
        ("Amino Acid Triplex"),
        ("PerfectAmino"),
        ("ENT-12(TM)"),
        ("BetaTOR"),
        ("Masquelier's Original OPCs"),
        ("KoAct Calcium Collagen Chelate"),
        ("InSea2"),
        ("BlueActiv"),
        ("PectaSol-C"),
        ("GlucosaGreen"),
        ("Peak02"),
        ("Arrowroot"),
        ("CARE4U"),
        ("Calzbone"),
        ("Hexadrone"),
        ("Vinegar"),
        ("Sodium Caprylate"),
        ("Magnesium Caprylate"),
        ("Ursolic & Oleanolic Acids"),
        ("New Zealand grassfed Bone Marrow"),
        ("Salmon Nasal Cartilage powder"),
        ("edible Hemoglobin"),
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


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Cat’s Claw (Uncaria tomentosa) extract", "Cat"),
        ("Deep Sea Fish Oil, Purified", "Fish Oil"),
        ("Pumpkin Seed Oil, Cold-Pressed", "Pumpkin"),
        ("St. John’s Bread", "carob"),
        ("Brewer’s Yeast", "Brewer"),
        ("L-Methylfolate Calcium Salt", "Folate"),
        ("DL-Malic Acid", "Malic Acid"),
    ],
)
def test_raw_validated_punctuation_and_form_variants_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])
    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("ERr 731 Siberian Rhubarb (Rheum rhaponticum L.) extract", "Rhaponticin"),
        ("Capros Amla extract", "Amla"),
        ("Amla (Emblica officinalis) fruit 5:1 extract", "Amla"),
        ("Black Elder Fruit Extract", "Elderberry"),
        ("Soy Isoflavones 40%", "Isoflavones"),
        ("Japanese Chlorella", "Chlorella"),
        ("BaCognize Ultra Bacopa extract", "Bacopa"),
        ("BroccoVital Myrosinase Broccoli extract", "Sulforaphane"),
        ("Deer Antler horn powder", "Deer Antler"),
        ("Deglycyrrhized Licorice", "Licorice"),
        ("Bilberry standardized extract", "Bilberry"),
        ("Ginkgo [leaf] 50:1 Extract", "Ginkgo"),
        ("Ginkgo Biloba 4:1 Extract", "Ginkgo"),
        ("Rutin NF", "Citrus Bioflavonoids"),
        ("Vegetable Oil Phytosterols", "Phytosterols"),
        ("Plant Phytosterols", "Phytosterols"),
        ("Sitosterol", "Phytosterols"),
        ("L5-MTHF", "Vitamin B9"),
        ("Levomefolate Calcium", "Vitamin B9"),
        ("New-Gar Aged Garlic bulb extract", "Garlic"),
        ("Acetyl-L-Carnitine HCI", "L-Carnitine"),
        ("L-Carnitine HCl", "L-Carnitine"),
        ("ProteaseGL", "Digestive Enzymes"),
        ("Pancreatin 5X", "Digestive Enzymes"),
        ("DigeZyme", "Digestive Enzymes"),
        ("Beta Glucan 3/6/9", "Beta-Glucan"),
        ("Daidzen", "Daidzein"),
        ("Red Clover leaf & stem extract", "Red Clover"),
        ("Bulgarian Tribulus", "Tribulus"),
        ("SDG Flax lignans", "Lignans"),
        ("Arjuna (Terminalia arjuna) bark 5:1 extract", "Arjuna"),
        ("Quercetin Anhydrous", "Quercetin"),
        ("GreenSelect Green Tea Phytosome", "Green Tea"),
        ("Saw Palmetto 45% extract", "Saw Palmetto"),
        ("Hydrolyzed Type II Collagen", "Collagen"),
        ("Bifidobacterium longum longum 35624", "Bifidobacterium Longum"),
        ("LongJaX 20:1 extract", "Tongkat Ali"),
        ("BCM-95 Curcugreen", "Curcumin"),
        ("BCM-95 Bio-Curcumin", "Curcumin"),
        ("Horsetail Grass", "Horsetail"),
        ("AlphaSize Alpha-Glyceryl Phosphoryl Choline", "Alpha GPC"),
        ("Anise 4:1 extract", "Anise"),
        ("Nettles leaf powder", "Stinging Nettle"),
        ("KSM-66 Full-Spectrum Ashwagandha root extract", "Ashwagandha"),
        ("Ashwagandha root & leaf extract", "Ashwagandha"),
        ("Shoden Ashwagandha extract", "Ashwagandha"),
        ("Eurycoma Longjack root extract", "Tongkat Ali"),
        ("K-2", "Vitamin K"),
        ("Devil's Claw 5% extract", "Devil's Claw"),
        ("Amla 4:1 extract", "Amla"),
        ("Creatine Alpha-Ketoglutarate", "Creatine"),
        ("Psyllium Husks", "Psyllium"),
        ("Rhodiola rosea root 3% extract", "Rhodiola"),
        ("Aloe vera gel powder 200:1 concentrate", "Aloe Vera"),
        ("L-5 Methyltetrahydrofolate Calcium Salt", "Vitamin B9"),
        ("Gar-O-Lic Garlic concentrate", "Garlic"),
        ("Licorice root 4:1 extract", "Licorice"),
        ("Policosanol (Saccharum officinarum) dried extract", "Policosanol"),
        ("Brown Flax", "Flaxseed"),
        ("Biotin Pure", "Biotin"),
        ("Beta Phenylethylamine", "Phenylethylamine"),
        ("GlycoCarn GPLC", "L-Carnitine"),
        ("Cereboost American Ginseng (Panax quinquefolius) extract", "Ginseng"),
        ("Monterey Pine (Pinus radiata) extract", "Pine Bark"),
        ("Optimized Curcumin extract", "Curcumin"),
        ("Keto Krill Oil", "Krill Oil"),  # Krill oil products now route to dedicated krill_oil IQM entry
        ("Cinnamon bark 10:1 extract", "Cinnamon"),
        ("Joint Shield 5-Loxin Advanced", "Boswellia"),
        ("Boswellin Forte", "Boswellia"),
        ("3-O-Acetyl-11-Keto-Beta-Boswellic Acid", "Akba"),
        ("Pyridoxal 5-Phosphate Monohydrate", "Vitamin B6"),
        ("Calcium Fructo-Borate", "Boron"),
        ("Oregano leaf supercritical CO2 extract", "Oregano"),
        ("Black Walnut unripe hulls extract", "Black Walnut"),
        ("HyaMax", "Hyaluronic Acid"),
        ("Mexican Wild Yam (Dioscorea villosa) rhizome standardised extract", "Wild Yam"),
        ("BioVin Grape extract", "Grape"),
        ("MegaNatural-BP Grape (Vitis vinifera) extract", "Grape"),
        ("MegaNatural BP Grape seed extract", "Grape"),
        ("SAMe Disulfate Tosylate", "SAMe"),
        ("Sodium R Alpha Lipoic Acid", "Alpha Lipoic Acid"),
        ("Calcium Beta-Hydroxy Beta-Methylbutyrate Monohydrate", "Methylbutyrate"),
        ("Beta Glucan 1,3", "Beta-Glucan"),
        ("Super Berberine", "Berberine"),
        ("EMIQ", "Quercetin"),
        ("Affron Eye", "Saffron"),
        ("Daidzein/Daidzin", "Daidzein"),
        ("Genistein/Genistin", "Genistein"),
        ("Siliphos Silybin Phytosome", "Milk Thistle"),
        ("Total Silybins", "Milk Thistle"),
        ("Banaba 1% extract", "Corosolic Acid"),
        ("L-Valine, Micronized", "L-Valine"),
        ("L-Isoleucine, Micronized", "L-Isoleucine"),
        ("L-Leucine, Micronized", "L-Leucine"),
        ("Butterbur 15% extract", "Butterbur"),
        ("Cordyceps 7% extract", "Cordyceps"),
        ("Paradoxine Grains of Paradise extract", "Grains of Paradise"),
        ("Pistacia lentiscus var. Chia", "Mastic"),
        ("Maitake PD-Fraction powder", "Maitake"),
        ("Desoxyrhaponticin", "Rhaponticin"),
        ("Potassium Carbonate", "Potassium"),
        ("Calcium Formate", "Calcium"),
        ("Probiotic 16 Strains", "Probiotics"),
        ("Lactobacillus gasseri CNCM I-5076", "Lactobacillus Gasseri"),
        ("Pharma GABA", "GABA"),
    ],
)
def test_high_confidence_alias_batch_maps(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])
    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Poria (Poria cocos) sclerotium double extract", "Poria"),
        ("Avena sativa (oat) tops extract", "Oat"),
        ("Neuravena Wild Green Oat extract", "Oat"),
        ("Bitter Melon (Momordica charantia) Fruit Extract 2:1", "Bitter Melon"),
        ("California Poppy [herb] 5:1 extract", "California Poppy"),
        ("Eleutherococcus senticosus root 50:1 extract", "Eleuthero"),
        ("Eleuthero [root] 4:1 extract", "Eleuthero"),
        ("Andrographis aerial parts ext.", "Andrographis"),
        ("Chinese Salvia Root Extract", "Danshen"),
        ("Buchu leaf 4:1 extract", "Buchu"),
        ("Butcher's Broom 10% extract", "Butcher"),
        ("Rosehip fruit extract", "Rose"),
        ("Lonicera japonica flower extract", "Honeysuckle"),
        ("Artichoke aerial extract", "Artichoke"),
        ("Artichoke fruit leaf extract", "Artichoke"),
        ("Toothed Clubmoss Leaf Extract", "Huperzine A"),
        ("Polypodium vulgar powder", "Polypodium"),
        ("Asparagus root extract", "Asparagus"),
        ("Scute root extract", "Skullcap"),
        ("Echinamide (Echinacea purpurea) extract", "Echinacea"),
        ("Olive Water extract", "Olive"),
        ("Guduchi root extract", "Tinospora"),
        ("Celery 10:1 extract", "Celery"),
        # Bitter Orange moved to banned_recalled_ingredients (RISK_BITTER_ORANGE)
        ("Huperzia serrata leaf extract", "Toothed Clubmoss"),
        ("Cape Aloe leaf latex extract", "Aloe"),
        ("Bitter Melon P.E.", "Bitter Melon"),
        ("Daucus sativus", "Carrot"),
        ("Parsnip", "Parsnip"),
        ("Nori yaki", "Nori"),
        ("Horse Chestnut ext.", "Horse Chestnut"),
        ("Polypodium vulgare ext.", "Polypodium"),
        ("Chinese Dodder Seed Extract", "Chinese Dodder"),
        ("False Unicorn", "False Unicorn"),
        ("Squaw Vine", "Squaw Vine"),
        ("Acai berry 4:1 extract", "Acai"),
        ("Acai std. concentrate", "Acai"),
        ("European Vervain", "Vervain"),
        ("Vervain whole herb powder", "Vervain"),
        ("Parsley aerial parts juice powder", "Parsley"),
        ("Andrographis EP80 (Andrographis paniculata) leaf extract", "Andrographis"),
        ("Shankhpushpi", "Shankhpushpi"),
        ("Cascara Sagrada P.E.", "Cascara"),
        ("European Ash (seed, fruit) extract", "European Ash"),
        ("Bulbine natalensis", "Bulbine"),
        ("Brassaiopsis glomerulata", "Brassaiopsis"),
        ("Jiaogulan Leaf Extract", "Jiaogulan"),
        ("Cytokine Suppress Mung Bean extract", "Mung Bean"),
        ("Venetron Rafuma leaf extract", "Apocynum"),
        ("Squash", "Squash"),
    ],
)
def test_high_confidence_botanical_alias_batch_maps(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])
    assert mapped is True
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Milk Thistle extract extract", "Milk Thistle extract"),
        ("Turmeric Rhizome Extract extract", "Turmeric Rhizome Extract"),
        ("organic Flaxseed Oil organic", "organic Flaxseed Oil"),
        ("Organic High Lignan Flaxseed Oil organic", "Organic High Lignan Flaxseed Oil"),
    ],
)
def test_cleaning_strips_duplicate_extract_and_organic_wrappers(normalizer, raw, expected):
    assert normalizer._strip_duplicate_label_artifacts(raw) == expected


def test_cleaning_uses_deduped_name_but_preserves_raw_source_text(normalizer):
    ingredient = {
        "name": "Milk Thistle extract extract",
        "quantity": {"quantity": 500, "unit": "mg"},
        "order": 1,
    }

    processed = normalizer._process_single_ingredient_enhanced(ingredient, is_active=True)
    assert processed is not None
    assert processed.get("name") == "Milk Thistle extract"
    assert processed.get("raw_source_text") == "Milk Thistle extract extract"


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Galactose", "Galactose", "Galactose"),
        ("Alpha Pinene", "Alpha-pinene", "Alpha Pinene"),
        ("Rafuma leaf extract", "Apocynum venetum", "Apocynum Venetum Leaf"),
        ("Calcium 5-formyltetrahydrofolate", "Vitamin B9 (folinic acid)", "Vitamin B9"),
        ("Isomax 30", None, "Isoflavones"),
    ],
)
def test_batch24_softgels_exact_aliases_and_new_identities_map(normalizer, name, ingredient_group, expected):
    if name in {"Galactose", "Alpha Pinene"}:
        standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
            name, ingredient_group=ingredient_group
        )
    else:
        standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
            name, [], ingredient_group=ingredient_group
        )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Allsure(R)", "Garlic"),
        ("Aloe Vera leaf oil", "Aloe Vera"),
        ("Aloe vera leaf Oil", "Aloe Vera"),
        ("Angelica dahurica root 10:1 extract", "Fragrant Angelica Root"),
        ("Artichoke (Cynara scolymus) (leaf) aqueous extract", "Globe Artichoke"),
        ("Bhumiamalaki", "Chanca Piedra"),
        ("Akkalkara", "Akkalkara Root"),
        ("Ashoka", "Ashoka"),
        ("Bhrungraj", "Bhringraj"),
    ],
)
def test_batch25_softgels_active_exact_aliases_and_new_botanicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        # Khadeer is the Ayurvedic name for Acacia catechu (Senegalia catechu).
        # After Batch 5 IQM gap fill (2026-04-29), it maps to the new IQM
        # acacia_catechu parent entry which gives it a real quality score
        # rather than just botanical recognition. This is more accurate —
        # Khadeer ≡ Acacia catechu.
        ("Khadeer", "Acacia Catechu"),
        ("Sariva", "Sariva"),
        ("Corydalis yanhusuo root 10:1 extract", "Corydalis"),
        ("Triphala fruit extract", "Triphala"),
        ("Sphingomyelin", "Sphingomyelin"),
        ("CLA Oil", "CLA"),
    ],
)
def test_batch26_softgels_active_exact_aliases_and_new_canonicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("beta, gamma and delta tocopherols", "Vitamin E", "Tocopherol"),
        ("D-Beta Tocopherols", "Vitamin E (beta tocopherol)", "Tocopherol"),
        ("emulsifier-Polysorbate 80", "Polysorbate", "Polysorbate 80"),
        ("fumed Silicon Dioxide", "Silicon Dioxide", "Silicon Dioxide"),
        ("non-GMO Vegetable Oil", "vegetable oil", "Vegetable Oil"),
        ("unrefined cold-pressed Hemp Seed Oil", "Hemp oil", "Hemp Seed Oil"),
        ("5-formyl tetrahydrofolate", "Vitamin B9 (folinic acid)", "Vitamin B9"),
        ("Apple Cider Concentrate", "Apple", "Apple Cider Concentrate"),
        ("Beta-Sitosterol-3-O-Glucoside", "Beta-Sitosterol", "Beta-Sitosterol-3-O-Glucoside"),
        ("Chinese Cabbage", "Chinese Cabbage", "Chinese Cabbage"),
        ("Conjugated Linoleic Acid Oil", "Conjugated Linoleic Acid", "Conjugated Linoleic Acid Oil"),
    ],
)
def test_batch26_softgels_inactive_exact_aliases_and_new_identities_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Mashparnee", "Mashaparni"),
        ("Mudgaparnee", "Mudgaparni"),
        ("Lodhra", "Lodhra"),
        ("Nagkeshar", "Nagkeshar"),
        ("Galanga", "Greater Galangal"),
        ("Galanga Supercritical extract", "Greater Galangal"),
        ("Chebulic Myrobalan Fruit Extract", "Chebulic Myrobalan"),
        ("Conjugated Linolenic Acid", "CLA"),
        ("Full Spectrum Palm Fruit Extract", "Vitamin E"),
    ],
)
def test_batch27_softgels_active_exact_aliases_and_new_botanicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Nirgundee", "Nirgundi"),
        ("Casein Tryptic Hydrolysate", "Casein Hydrolysate"),
        ("DiosVein", "Diosmin"),
        ("GG-Gold", "Geranylgeraniol"),
        ("Insulina (Cissus sicyoides) leaf extract", "Cissus sicyoides"),
    ],
)
def test_batch28_softgels_active_exact_aliases_and_new_canonicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Svetol French Green Coffee extract", "Green Coffee Bean"),
        ("Jatamasi", "Jatamasi"),
        ("Khurasani Ajwain", "Henbane"),
        ("Jatiphala", "Mace"),
        ("Kokilaksha", "Kokilaksha"),
        ("L-Methylfolate Magnesium, Molar", "Vitamin B9"),
        ("Korean Pine nut seed Oil", "Korean Pine"),
        ("Norway Spruce extract", "Lignans"),
        ("Kola (seed) extract", "Kola Nut"),
    ],
)
def test_batch29_softgels_active_exact_aliases_and_new_botanicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Fish Gelatin from Tilapia", "Fish (including shell)", "Gelatin Capsule"),
        ("Methacrylic Acid Copolymer Type C", "Coating", "Enteric Coating"),
    ],
)
def test_batch29_softgels_inactive_exact_aliases_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Citrus spp. Fruit Extract", "Citrus Fruit Extract"),
    ],
)
def test_batch30_softgels_deferred_accuracy_exact_aliases_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Shuddha Laksha", "Shuddha Laksha"),
        ("Beef Tallow", "Beef Tallow"),
    ],
)
def test_batch31_softgels_deferred_accuracy_new_active_canonicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


def test_batch31_chopchinee_remains_unmapped_until_identity_is_verified(normalizer):
    """Chopchinee spelling is ambiguous: DSLD product 202519 labels it 'Chopchinee' but
    ingredientGroup says 'Himalayan Rhubarb' (Rheum emodi), conflicting with Smilax china
    interpretation. Leaving unmapped is more accurate than forcing a wrong mapping.
    Do NOT add 'chopchinee' to chopchini aliases without resolving this conflict first."""
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping("Chopchinee", [])

    assert mapped is False
    assert standard_name == "Chopchinee"


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Mono and Di-Glycerides", "Blend (non-nutrient/non-botanical)", "Mono and Diglycerides"),
        ("Mono - and Diglycerides", "", "Mono and Diglycerides"),
        ("Mono-di-acyglycerol", "TBD", "Mono and Diglycerides"),
        ("caprylic/capric triglycerides", "Medium chain triglycerides (MCT)", "Medium Chain Triglycerides"),
        ("Tocopherols Concentrate Mixed", "Vitamin E (mixed)", "Tocopherol"),
        ("Vitamin E Oil", "Vitamin E", "Tocopherol"),
        ("non-GMO natural Tocopherols", "Vitamin E (mixed tocopherols)", "Tocopherol"),
        ("annato oil concentrate", "Annatto Oil", "Annatto"),
        ("yellow wax", "Wax (unspecified)", "Beeswax"),
        ("Marine Lip Concentrate", "", "Purified Fish Oil"),
        ("Marine Lipid Concentrate 30 A% TG", "Marine oil (unspecified)", "Purified Fish Oil"),
        ("Propylparabens", "Propyl paraben", "Propylparaben"),
        ("Titanium Dioxide colour", "Titanium Dioxide", "Titanium Dioxide"),
    ],
)
def test_batch32_softgels_inactive_alias_and_parser_targets_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Sonova-400", "Gamma-Linolenic Acid"),
        ("Smilax officinalis root powder", "Sarsaparilla (Honduran)"),
        ("Sandalwood", "White Sandalwood"),
    ],
)
def test_batch33_softgels_active_exact_aliases_and_new_botanicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("D-Alpha-Tocopheryl Polyethylene Glycol 1000 Succinate", "Vitamin E (alpha tocopheryl succinate)", "Tocofersolan"),
        ("Triacylglycerol", "TBD", "Triacylglycerol"),
    ],
)
def test_batch33_softgels_inactive_new_identities_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("OpriBerry(R)", "OptiBerry"),
        ("Seal oil", "Seal Oil"),
        ("Milk Basic Protein", "Milk Basic Protein"),
        ("Omega 7", "Omega-7 Fatty Acids"),
    ],
)
def test_batch34_softgels_active_exact_aliases_and_new_canonicals_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


def test_batch34_hemp_aerial_parts_oil_extract_remains_unmapped_until_policy_is_resolved(normalizer):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Hemp Aerial Parts Oil Extract",
        [],
    )

    assert mapped is False
    assert standard_name == "Hemp Aerial Parts Oil Extract"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Rhodiola crenulata (root) Extract", "Rhodiola"),
        ("Krounchabeej Ghana", "Mucuna Pruriens"),
    ],
)
def test_batch35_softgels_active_exact_aliases_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Vacha", "Calamus"),
        ("Masha", "Black Gram"),
    ],
)
def test_batch36_softgels_active_safety_and_botanical_routes_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


def test_batch36_vidarikanda_remains_unmapped_until_identity_is_verified(normalizer):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping("Vidarikanda", [])

    assert mapped is False
    assert standard_name == "Vidarikanda"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Eicosatrienoic Acid", "Omega-3"),  # now maps via IQM omega_3 form "eicosatrienoic acid (20:3n-3)"
        ("Pine Nut Oil", "Pine Nut Oil"),
    ],
)
def test_batch37_softgels_active_new_entries_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Diglyceride", "Diglyceride", "Mono and Diglycerides"),
        ("Mixed Tocopheryls", "Vitamin E (mixed tocopherols)", "Tocopherol"),
        ("Grape Seed Oil", "Grapeseed Oil", "Grape Seed Oil"),
        ("Potassium Benzoate", "Potassium benzoate", "Potassium Benzoate"),
    ],
)
def test_batch37_softgels_inactive_exact_aliases_and_new_entries_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Proprietary Mulberry leaf extract", "Mulberry"),
    ],
)
def test_batch38_softgels_active_exact_aliases_map(normalizer, name, expected):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("non-ionic Surfactant", "Nonionic surfactant (unspecified)", "Nonionic Surfactant"),
        ("Emulsifiers", "emulsifer", "Emulsifiers"),
        ("Opaquing Agent", "Opaquing agent", "Opaquing Agent"),
        ("Omega ethyl esters", "Blend (Fatty Acid or Fat/Oil Supplement)", "Omega Ethyl Esters"),
        ("Mortierella Alpina Oil", "Mortierella alpina", "Mortierella Alpina Oil"),
        ("Myrcene", "Myrcene", "Myrcene"),
        ("Caryophyllene Beta, Natural", "Caryophyllene", "Beta-Caryophyllene"),
    ],
)
def test_batch38_softgels_inactive_exact_aliases_and_new_entries_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("Tocobiol SF", "TBD", "Tocopherol"),
        ("Mono & Di-Glycerides", "Blend (non-nutrient/non-botanical)", "Mono and Diglycerides"),
        ("Mixed Caratanoids", None, "Natural Colors"),
        ("Sunflower Vitamin E Tocopherols", "Vitamin E (mixed tocopherols)", "Tocopherol"),
        ("Tocopherol rich extract", None, "Tocopherol"),
    ],
)
def test_batch39_softgels_inactive_exact_aliases_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("100% Pure Euphausia superba Antarctic Krill Oil", "Krill Oil", "Krill Oil"),
        ("100% Pure Euphausia superba Antarctic krill oil", "Krill Oil", "Krill Oil"),
        ("Pure Euphausia superba Antarctic Krill Oil", "Krill Oil", "Krill Oil"),
        ("PurityKRILL Krill Oil", "Krill Oil", "Krill Oil"),
        ("Soybean or Safflower Oil", "Blend (Fatty Acid or Fat/Oil Supplement)", "Soybean or Safflower Oil"),
        ("minor Fatty Acids", "Blend (Fatty Acid or Fat/Oil Supplement)", "Minor Fatty Acids"),
        ("Triglyceride Concentrate, Re-esterified", "Triglyceride (unspecified)", "Re-Esterified Triglyceride Concentrate"),
        ("Vegetable juice Anthocyanin", "Anthocyanidins (unspecified)", "Anthocyanin"),
    ],
)
def test_batch40_softgels_inactive_exact_aliases_and_new_entries_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("natural orange crème flavor", "Natural flavor(s)", "Natural Orange Flavor"),
        ("medium-chain glycerides oil", "Medium chain triglycerides (MCT)", "Medium Chain Triglycerides"),
        ("middle chained Triglycerides", "Medium chain triglycerides (MCT)", "Medium Chain Triglycerides"),
        ("refined Soy", "Soy", "Soy Bean Oil"),
        ("vitamin E mixed tocopherol concentrate", "TBD", "Tocopherol (Preservative)"),
        ("Plukenetia volubilis L. Oil", "TBD", "Sacha Inchi Oil"),
        ("skipjack liver oil", "Fish Liver oil", "Skipjack Liver Oil"),
        ("Corn protein", "Corn Protein", "Corn Protein"),
        ("Soy Phospholipid concentrate", "Blend (Fatty Acid or Fat/Oil Supplement)", "Soy Lecithin"),
    ],
)
def test_batch42_softgels_inactive_exact_aliases_and_new_entries_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected == standard_name


# ---------------------------------------------------------------------------
# Batch 41 — Safety routing: Vacha / Acorus calamus (FDA 21 CFR 189.140)
# ---------------------------------------------------------------------------
# Vacha is the Ayurvedic name for Acorus calamus (sweet flag / calamus root).
# FDA prohibits calamus and its derivatives in human food under 21 CFR 189.140
# due to beta-asarone, a confirmed animal carcinogen.  The pipeline MUST route
# all label forms of this ingredient to the banned/recalled surface — never to
# unmapped and never to an active-ingredient score bucket.

@pytest.mark.parametrize(
    "label_text",
    [
        "Vacha",
        "vacha",
        "Acorus calamus",
        "Calamus",
        "Sweet Flag",
    ],
)
def test_batch41_vacha_calamus_routes_to_banned(normalizer, label_text):
    """Every label form of Vacha/Acorus calamus must resolve as mapped=True
    (via banned/recalled DB) and must NOT be left unmapped."""
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(label_text, [])

    assert mapped is True, (
        f"'{label_text}' was not mapped — it should route to banned/recalled "
        f"(Calamus / 21 CFR 189.140).  Got standard_name={standard_name!r}"
    )
    assert "calamus" in str(standard_name).lower(), (
        f"'{label_text}' mapped to {standard_name!r} but expected 'calamus' in the name"
    )


def test_batch41_vacha_check_banned_recalled_returns_true(normalizer):
    """_check_banned_recalled must confirm Vacha/Acorus calamus is in the
    banned DB so the enrichment stage also flags it correctly."""
    assert normalizer._check_banned_recalled("Vacha") is True
    assert normalizer._check_banned_recalled("vacha") is True
    assert normalizer._check_banned_recalled("Acorus calamus") is True
    assert normalizer._check_banned_recalled("Sweet Flag") is True


@pytest.mark.parametrize(
    "name",
    [
        "7-Keto-DHEA",
        "7-Keto-Dehydroepiandrosterone Acetate",
        "7-Keto(R) - Dehydroepiandrosterone Acetate",
    ],
)
def test_batch43_softgels_7keto_variants_route_to_banned(normalizer, name):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True
    assert "7-keto" in str(standard_name).lower()
    assert normalizer._check_banned_recalled(name) is True


@pytest.mark.parametrize(
    "name,ingredient_group,expected",
    [
        ("natural D-Alpha Tocopheryl", "Vitamin E (alpha tocopherol)", "Tocopherol (Preservative)"),
        ("Ruby Red Grape juice extract", "Grape ", "Grape Juice Color"),
        ("polyglycerol fatty acid ester", None, "Mono and Diglycerides"),
        ("oleyl lactylic acid", "Lactylates", "Oleyl Lactylate"),
    ],
)
def test_batch43_softgels_inactive_exact_aliases_and_new_entry_map(normalizer, name, ingredient_group, expected):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True
    assert expected == standard_name


# ── Batch 44: CVS / Double Wood / Equate / Garden of Life unmapped resolution ──


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("CDP Choline", "Choline"),
        ("Alanine", "Alanine"),
        ("Ajuga turkestanica whole herb extract", "Ecdysterone"),
        ("Korean Red Panax Ginseng Extract", "Ginseng"),
        ("Asian Ginseng root (Panax Ginseng) standardized extract", "Ginseng"),
        ("Keratin Peptides, Hydrolyzed", "Keratin"),
        ("Psyllium Hydrophilic Mucilloid", "Psyllium"),
        ("Mimosa pudica seed extract", "Mimosa"),
    ],
)
def test_batch44_active_exact_aliases_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Cellulose Coatiing", None, "Cellulose"),
        ("edible Ink", None, "Ink"),
        ("Soy Polysaccharide", None, "Soy Polysaccharide"),
        ("Enliten High Intensity Sweetener", None, "Stevia"),
    ],
)
def test_batch44_inactive_exact_aliases_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


# ── Batch 45: API-verified new entries and aliases (CVS/DW/Equate/GoL) ──


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        ("Silver", "Silver"),
        ("Magnesium Acetyl-Taurate", "Magnesium"),
        ("Spermidine", "Spermidine"),
        ("Spermidine Trihydrochloride", "Spermidine"),
        ("Organic Barley Grass Juice Concentrate", "Barley"),
    ],
)
def test_batch45_active_exact_aliases_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Polyalditol", None, "Polyalditol"),
        ("Carboxymethyl Starch Sodium", None, "Sodium Starch Glycolate"),
    ],
)
def test_batch45_inactive_exact_aliases_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group=ingredient_group
    )

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


# ── Batch 46: Garden of Life fallback form aliases ──


@pytest.mark.parametrize(
    "name,expected_substring",
    [
        # Turmeric cluster — post identity_bioactivity_split Phase 2, bare
        # turmeric routes to source botanical Turmeric (NOT curcumin).
        # Curcumin Section C credit requires explicit 95%+ standardization
        # declaration per botanical_marker_contributions.json policy.
        ("organic turmeric", "Turmeric"),
        ("organic turmeric root extract", "Turmeric"),
        ("organic fermented turmeric", "Turmeric"),
        ("turmeric curcuminoids", "Turmeric"),
        ("turmeric rhizome root extract", "Turmeric"),
        # Amla cluster
        ("organic amla berry", "Amla"),
        ("raw amla", "Amla"),
        ("organic amla berry extract", "Amla"),
        # Kelp/seaweed
        ("organic sea kelp", "Kelp"),
        ("brown seaweed extract", "Kelp"),
        # Flax
        ("flax", "Flaxseed"),
        ("organic flax seed fiber", "Flaxseed"),
        ("flaxseed fermented", "Flaxseed"),
        # Flaxseed oil extract — post-B38 (2026-04-25), the omega_3 parent
        # is metabolite-only; flaxseed (a botanical oil source) routes to the
        # botanical "Flaxseed" instead of the omega-3 umbrella.
        ("flaxseed oil extract", "Flaxseed"),
        # Piperine / Black pepper — "organic black pepper" now routes to botanical
        # (genus contamination fix: bare plant names → botanical, not compound IQM)
        ("organic black pepper", "Black Pepper"),
        ("essence of pure black pepper (fruit) oil", "Piperine"),
        # Strontium
        ("strontium", "Strontium"),
        # Cayenne — post identity_bioactivity_split Phase 2, bare cayenne
        # routes to source botanical (NOT capsaicin marker). Capsaicin
        # Section C credit requires 2%+ standardization declaration.
        ("organic cayenne", "Cayenne"),
        # Other
        ("organic anise", "Anise"),
        ("organic schisandra (schisandra chinensis) berry extract", "Schisandrin"),
        ("wild crafted butterbur extract", "Butterbur"),
        ("organic vitex", "Chasteberry"),
    ],
)
def test_batch46_garden_of_life_fallback_form_aliases_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


# ── Batch 47: Enrichment-unmapped form aliases (2026-04-01) ──────────────
@pytest.mark.parametrize(
    "name,expected_substring",
    [
        # Elderberry — Sports Research (DSLD 268441)
        ("Black Elderberry juice concentrate", "Elderberry"),
        # Lutein — Spring Valley (DSLD 178523)
        ("organic Lutein", "Lutein"),
        # Zeaxanthin — Pure Encapsulations (DSLD 293949)
        ("Optisharp Zeaxanthin", "Zeaxanthin"),
        # Oat Straw — Nutricost
        ("Avena sativa 10:1 extract", "Oat"),
        ("Oats Straw", "Oat"),
        # Ginseng — Transparent Labs
        ("Seneactiv", "Ginseng"),
        # GOS prebiotic — Pure Encapsulations
        ("BiMuno B-Galactooligosaccharides", "Prebiotics"),
    ],
)
def test_batch47_enrichment_unmapped_form_aliases_map(normalizer, name, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(name, [])

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


# ── Batch 48: Form-fallback alias gaps (2026-04-16) ──────────────────────
# Fixes Surface C form_fallback_audit `action_needed_differs` entries where the
# form text did not match any IQM form alias, forcing parent-fallback to an
# unspecified form. Source: fresh pipeline on 15 brands / 7,942 products.
#
# Boron inorganic borate forms: "Sodium Borate" and "Boric Acid, Sodium Borate"
# appear as DSLD forms[].name for CVS Spectravite and Nature Made multivitamins.
# Legitimate trace boron mineral sources — chemically equivalent in vivo to
# boric acid (already aliased under boron (unspecified)).
# Note: "Sodium Tetraborate" is NOT added — the banned-overlap test
# (test_iqm_banned_overlap_set_is_only_intentional_high_risk_dual_classification)
# restricts IQM↔banned overlaps to a strict whitelist. Pure sodium tetraborate
# continues to route to banned_recalled.ADD_SODIUM_TETRABORATE as intended.
# Evidence: EFSA Journal 2013;11(10):3407; NIH ODS Boron Fact Sheet; GSRS shows
# all three compounds share active moiety BORATE ION (UNII 44OAE30D22).
@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Sodium Borate", "Boron", "Boron"),
        ("Boric Acid, Sodium Borate", "Boron", "Boron"),
    ],
)
def test_batch48_boron_inorganic_borate_form_aliases_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


# Brown Rice Chelate systematic gap — 8 minerals, all Garden of Life (295+
# products). Precedent: zinc brown rice chelate (bio=11) and manganese brown
# rice chelate (bio=11) already in IQM; "positioned within the amino acid
# chelate class" per Anderson (1995). Rice protein hydrolysate = organic amino
# acid chelate class; bioavailability estimated 60-70% (better than inorganic
# oxide/sulfate, below dedicated bisglycinates).
@pytest.mark.parametrize(
    "name,ingredient_group,expected_substring",
    [
        ("Brown Rice Chelate", "Chromium", "Chromium"),
        ("Brown Rice Chelate", "Iron", "Iron"),
        ("Brown Rice Chelate", "Molybdenum", "Molybdenum"),
        ("Brown Rice Chelate", "Boron", "Boron"),
        ("Brown Rice Chelate", "Magnesium", "Magnesium"),
        ("Brown Rice Chelate", "Selenium", "Selenium"),
        ("Brown Rice Chelate", "Copper", "Copper"),
        ("Brown Rice Chelate", "Potassium", "Potassium"),
    ],
)
def test_batch48_brown_rice_chelate_mineral_forms_map(normalizer, name, ingredient_group, expected_substring):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        name, [], ingredient_group=ingredient_group
    )

    assert mapped is True, f"{name!r} should map but did not"
    assert expected_substring.lower() in str(standard_name).lower()


@pytest.mark.parametrize(
    "mineral_key,form_name,expected_bio",
    [
        # Dr Pham C4 (2026-04-25) downgraded most BRC forms to mineral-specific bio_scores
        # because BRC class F is determined by mineral, not by chelate form.
        # Molybdenum/copper retain bio=11 (intrinsic high bioavailability).
        ("chromium",   "chromium brown rice chelate",    6),
        ("iron",       "iron brown rice chelate",        6),
        ("molybdenum", "molybdenum brown rice chelate", 11),
        ("boron",      "boron brown rice chelate",       9),
        ("magnesium",  "magnesium brown rice chelate",   6),
        ("selenium",   "selenium brown rice chelate",    8),
        ("copper",     "copper brown rice chelate",     11),
        ("potassium",  "potassium brown rice chelate",   9),
    ],
)
def test_batch48_brown_rice_chelate_forms_exist_in_iqm(mineral_key, form_name, expected_bio):
    import json as _json
    from pathlib import Path

    iqm_path = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"
    iqm = _json.loads(iqm_path.read_text())

    entry = iqm.get(mineral_key)
    assert entry is not None, f"IQM parent {mineral_key!r} missing"
    forms = entry.get("forms") or {}
    assert form_name in forms, f"IQM form {form_name!r} missing from {mineral_key!r}"

    form = forms[form_name]
    # Bio score is mineral-specific per Dr Pham C4 sign-off (2026-04-25):
    # BRC chelate confers no extra absorption beyond the mineral's own class F.
    assert form.get("bio_score") == expected_bio, (
        f"{form_name} bio_score must be {expected_bio} per Dr Pham C4 BRC review."
    )
    assert form.get("score") == expected_bio  # natural=False so score == bio
    assert form.get("natural") is False
    assert isinstance(form.get("aliases"), list) and len(form["aliases"]) >= 3
    struct = form.get("absorption_structured") or {}
    valid_qualities = {"excellent", "very_good", "good", "moderate", "low", "poor", "variable", "unknown"}
    assert struct.get("quality") in valid_qualities, (
        f"{form_name} absorption.quality must be in canonical IQM enum {sorted(valid_qualities)} "
        f"(BRC class varies by mineral: zinc=moderate, manganese=low, iron=low, selenium=moderate, "
        f"molybdenum/boron/potassium=very_good — class F absorption is form-independent)"
    )


@pytest.mark.parametrize("mineral_key,form_name", [
    ("chromium", "chromium brown rice chelate"),
    ("iron", "iron brown rice chelate"),
    ("molybdenum", "molybdenum brown rice chelate"),
    ("boron", "boron brown rice chelate"),
    ("magnesium", "magnesium brown rice chelate"),
    ("selenium", "selenium brown rice chelate"),
    ("copper", "copper brown rice chelate"),
    ("potassium", "potassium brown rice chelate"),
])
def test_batch48_brown_rice_protein_mineral_middle_alias_present(mineral_key, form_name):
    """Pin that 'brown rice protein {mineral} chelate' alias is present.
    Covers DSLD labels like 'Brown Rice Protein Magnesium Chelate' where mineral is in the middle.
    """
    import json as _json
    from pathlib import Path

    iqm_path = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"
    iqm = _json.loads(iqm_path.read_text())

    mineral = mineral_key
    form = iqm[mineral]["forms"][form_name]
    aliases_lc = [a.lower() for a in form.get("aliases", [])]
    expected = f"brown rice protein {mineral} chelate"
    assert expected in aliases_lc, (
        f"Missing alias '{expected}' in {form_name} — "
        f"needed for DSLD labels like 'Brown Rice Protein {mineral.title()} Chelate'"
    )


def test_batch48_boron_unspecified_has_inorganic_borate_aliases():
    """Pin that the new sodium borate + combo aliases land on boron (unspecified)."""
    import json as _json
    from pathlib import Path

    iqm_path = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"
    iqm = _json.loads(iqm_path.read_text())

    form = iqm["boron"]["forms"]["boron (unspecified)"]
    aliases_lc = [a.lower() for a in form.get("aliases", [])]

    assert "sodium borate" in aliases_lc, "sodium borate alias missing from boron (unspecified)"
    assert "boric acid, sodium borate" in aliases_lc, (
        "combo 'boric acid, sodium borate' alias missing from boron (unspecified)"
    )
    # Safety: sodium tetraborate must NOT be added here (banned-overlap test)
    assert "sodium tetraborate" not in aliases_lc, (
        "sodium tetraborate must NOT be in IQM aliases — would collide with banned_recalled"
    )


def test_bug10_green_tea_phytosome_extract_alias_present():
    """BUG-10: 'Green Tea Phytosome extract' ingredient label (Thorne) must resolve
    to green tea phytosome form (bio=10), not unspecified (bio=5).
    Fix: 'green tea phytosome extract' alias added to green_tea_extract/green tea phytosome."""
    import json as _json
    from pathlib import Path

    iqm_path = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"
    iqm = _json.loads(iqm_path.read_text())

    form = iqm["green_tea_extract"]["forms"]["green tea phytosome"]
    aliases_lc = [a.lower() for a in form.get("aliases", [])]

    assert "green tea phytosome extract" in aliases_lc, (
        "green tea phytosome extract alias missing — Thorne 'Green Tea Phytosome extract' products would fall back to bio=5"
    )


def test_bug10_green_tea_phytosome_standalone_phospholipid_complex_removed():
    """BUG-10 / alias-collision fix: standalone 'Phospholipid complex' must NOT
    be an alias for green tea phytosome — it is far too generic and causes
    cross-ingredient collisions (e.g., Meriva turmeric phytosome matching green
    tea).  Compound aliases that include Camellia sinensis terms are still
    permitted and are verified separately."""
    import json as _json
    from pathlib import Path

    iqm_path = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"
    iqm = _json.loads(iqm_path.read_text())

    form = iqm["green_tea_extract"]["forms"]["green tea phytosome"]
    aliases_lc = [a.lower() for a in form.get("aliases", [])]

    assert "phospholipid complex" not in aliases_lc, (
        "standalone 'phospholipid complex' alias must be absent from green tea phytosome — "
        "it is too generic and causes cross-ingredient form collisions"
    )

    # Compound aliases that include Camellia sinensis terms must still be present
    camellia_aliases = [a for a in aliases_lc if "camellia sinensis" in a and "phospholipid" in a]
    assert camellia_aliases, (
        "at least one 'Camellia sinensis … Phospholipid complex' compound alias must remain "
        "in green tea phytosome — these are specific enough to be safe"
    )


def test_bug10_phospholipid_complex_not_in_grape_seed_phytosome():
    """BUG-10 uniqueness guard: standalone 'phospholipid complex' must not appear in
    grape_seed_extract phytosome aliases."""
    import json as _json
    from pathlib import Path

    iqm_path = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"
    iqm = _json.loads(iqm_path.read_text())

    form = iqm["grape_seed_extract"]["forms"]["grape seed phytosome"]
    aliases_lc = [a.lower() for a in form.get("aliases", [])]

    assert "phospholipid complex" not in aliases_lc, (
        "phospholipid complex must not be in grape_seed phytosome — generic alias would cause cross-ingredient collisions"
    )


@pytest.mark.parametrize("parent_key", [
    "vitamin_b1_thiamine",
    "vitamin_b2_riboflavin",
    "vitamin_b9_folate",
    "vitamin_b6_pyridoxine",
    "vitamin_c",
])
def test_bug11_cerevisiae_alias_absent_cross_parent_constraint(parent_key):
    """BUG-11 CONSTRAINT guard: 'S. cerevisiae culture' MUST NOT be added as a
    form alias in any vitamin parent. It appears in 5 parents (B1, B2, B9, B6, C)
    which violates the cross-ingredient alias uniqueness invariant enforced by
    test_no_cross_ingredient_duplicate_aliases. Resolution requires an enricher
    code fix (not an IQM alias fix) to handle this processing-method form text."""
    import json as _json
    from pathlib import Path

    iqm_path = Path(__file__).resolve().parent.parent / "data" / "ingredient_quality_map.json"
    iqm = _json.loads(iqm_path.read_text())

    all_aliases_lc = []
    for form_data in iqm[parent_key]["forms"].values():
        all_aliases_lc.extend(a.lower() for a in form_data.get("aliases", []))

    assert "s. cerevisiae culture" not in all_aliases_lc, (
        f"'S. cerevisiae culture' must NOT be in {parent_key} form aliases — "
        f"cross-parent uniqueness invariant: alias appears in 5 vitamin parents"
    )
