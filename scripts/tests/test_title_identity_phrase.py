"""A title names an ingredient by its identity phrase, never by one shared word.

`scoring_input_contract._named_in_title` is the one title/positioning identity
matcher (role prominence, clinical positioning). It used to accept any single
word of four or more letters from a multi-word ingredient name, so "Green" in
"Ultra Mega Green Men's Energy & Metabolism" (67032) made Green Tea extract
claim-prominent, and "Alpha"/"Beta" did the same for alpha-lipoic acid and
beta-cryptoxanthin. A single word now counts only when it is the whole name,
the name with descriptor words removed, or a registered IQM/botanical name of
that same ingredient.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _named(name, canonical, text, path="ingredientRows[0]", others=()):
    from scoring_input_contract import _named_in_title
    row = {"name": name, "canonical_id": canonical, "raw_source_path": path}
    return _named_in_title(row, text, label_rows=[row, *others])


@pytest.mark.parametrize("name,canonical,text", [
    ("Green Tea extract", "green_tea_extract", "ultra mega green men's energy & metabolism"),
    ("Green Coffee extract", "green_coffee_bean", "ultra mega green men's multivitamin"),
    ("organic Green Onion", "onion", "raw organic perfect food green superfood"),
    ("Alpha-Lipoic Acid", "alpha_lipoic_acid", "alpha betic"),
    ("Beta-Cryptoxanthin", "cryptoxanthin", "women's ultra mega beta complex"),
    ("Fish Oil", "fish_oil", "oil of oregano"),
    ("Green Tea extract", "green_tea_extract", "black tea extract 500 mg"),
    ("Branched Chain Amino Acids", "branched_chain_amino_acids", "essential amino acid complete"),
    ("hydrolyzed Whey Peptide Complex", "whey_protein", "citrulline complex"),
    ("organic Quinoa", "quinoa", "raw organic perfect food"),
    # The active_in source names the row only when the row's own name says it.
    ("Curcumin", "curcumin", "turmeric extract 500 mg"),
    # A registry alias names the row only whole, never by two of its words.
    ("Milk Thistle seed extract", "milk_thistle", "liver health"),
    ("Lactase", "lactase", "digestive enzymes"),
    # A registered descriptor-only name ("leaf and root extract") names nothing.
    ("Ashwagandha Leaf, Root Extract", "ashwagandha", "stress & gut health"),
    ("Sensoril", "ashwagandha", "carbcrave complex"),
    # A registry alias cut to one generic word names nothing (review, Oct 31).
    ("Fish Oil", "fish_oil", "marine collagen peptides"),
    ("Fish Oil", "fish_oil", "omega joint"),
    ("Wheatgrass", "wheatgrass", "wheat germ oil"),
    ("Black Seed Oil", "black_seed_oil", "black cohosh 40 mg"),
    # A genus one registry gives to several species names none of them.
    ("Yuzu", "yuzu", "citrus bergamot 500"),
    ("Wormwood", "wormwood", "artemisia annua"),
    # Connectors are never identity words.
    ("Selenium (as L-selenomethionine)", "selenium", "as l-theanine for calm"),
    ("Vitamin E (as d-alpha tocopheryl acetate)", "vitamin_e", "supports immunity with nutrients such as d and k"),
    ("organic sprouted Brown Rice Protein", "rice_protein", "raw protein vanilla spiced chai"),
    # A head word qualified by another identity, or one that is an identity itself.
    ("Maitake Mushroom powder", "maitake", "reishi mushroom extract"),
    ("Pumpkin Seed Protein", "pumpkin", "grass fed collagen protein fair trade chocolate"),
    ("Lactobacillus paracasei DSM-16105", "lactobacillus_paracasei", "lactobacillus acidophilus cul-21"),
    ("Chaga Mushroom", "chaga", "lion's mane mushroom coffee"),
    ("Fast-Acting Comfort Blend", "fast_acting_comfort_blend", "comfort"),
])
def test_one_shared_word_does_not_name_the_ingredient(name, canonical, text):
    assert not _named(name, canonical, text)


@pytest.mark.parametrize("name,canonical,text", [
    ("Green Tea (leaf) extract", "green_tea_extract", "green tea 250 mg"),
    ("Green Tea extract", "green_tea_extract", "camellia sinensis 500 mg"),
    ("Ginkgo biloba leaf extract", "ginkgo", "ginkgo 120 mg"),
    ("Ashwagandha root extract", "ashwagandha", "ashwagandha 600"),
    ("Magnolia Bark Extract", "magnolia_bark", "magnolia extract"),
    ("Devil's Claw root extract", "devils_claw", "devil's claw 700 mg"),
    ("Blood Orange Fruit Extract", "sweet_orange", "blood orange extract"),
    ("Alpha-Lipoic Acid", "alpha_lipoic_acid", "alpha lipoic sustain with biotin"),
    ("L-Carnitine", "l_carnitine", "best carnitine energy"),
    ("Vitamin B7", "vitamin_b7_biotin", "biotin 5000 mcg"),
    ("Omega-3 Fatty Acids", "fish_oil", "100% pure omega-3 krill oil 500 mg"),
    ("Coenzyme Q-10", "coq10", "coq10 100 mg"),
    ("MSM", "msm", "glucosamine msm"),
    ("Vitamin D3", "vitamin_d", "d3 5000 iu"),
    ("Vitamin C", "vitamin_c", "vitamin c 1000"),
    ("CoffeeGenic Green Coffee extract", "green_coffee_bean", "green coffee extract coffeegenic 400 mg"),
    ("Energy & Metabolism Blend", "energy_metabolism_blend", "energy and metabolism"),
    ("Vitamin E (Mixed Tocopherols and Tocotrienols)", "vitamin_e", "gamma e mixed tocopherols & tocotrienols"),
    ("Apple Cider Vinegar", "apple_cider_vinegar", "apple cider complete"),
    ("Kelp Thallus Extract", "kombu", "kelp"),
    ("Waterex Herbal Blend", "waterex_herbal_blend", "waterex"),
    ("Citrus Bioflavonoid Complex", "citrus_bioflavonoids", "vitamin c with bioflavonoids 1,000 mg"),
    ("Curcumin C3 Complex Turmeric Extract", "curcumin", "extra strength turmeric extract 1400 mg"),
    ("Relora Proprietary Patented Blend", "relora_proprietary_patented_blend", "relora"),
    ("Tinofend (Tinospora cordifolia) extract", "tinospora_cordifolia", "immune modulator with tinofend"),
    ("Micronized Creatine Matrix Blend", "creatine_blend", "amplified creatine xxx blue raspberry"),
    # The label's own word that a registry lists as a whole name, even one
    # a registry gives to more than one identity.
    ("Total Probiotic CFU", "probiotic_cfu_total", "probiotic pearls adult 50+"),
    ("Probiotic", "probiotics", "probiotic tropical mango"),
    # Only a preparation word was dropped: the label's word names the row.
    ("Hemp extract", "nha_hemp_extract", "hemp+ stress relief"),
    # A non-plural -s word keeps itself while a plural title word is read singular.
    ("Citrus Bioflavonoid", None, "citrus bioflavonoids 1000 mg"),
    # The label name's head word, unqualified in the title (220046).
    ("Maitake Mushroom powder", "maitake", "mushroom complex"),
    ("Lion's Mane Mushroom", "lions_mane", "lion's mane mushroom coffee"),
])
def test_identity_phrase_or_registered_name_names_the_ingredient(name, canonical, text):
    assert _named(name, canonical, text)


def _roles(fixture):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import classify_ingredient_roles, get_scoring_ingredients

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / fixture).read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    rows = get_scoring_ingredients(enriched, strict=True).rows
    return {r.get("name"): role for r, role in zip(rows, classify_ingredient_roles(enriched, rows=rows))}


def test_mega_green_title_does_not_make_green_tea_claim_prominent():
    mega_green = _roles("raw_title_green_67032.json")["Green Tea extract"]
    plain_title = _roles("raw_blend_grapefruit_176190.json")["Green Tea extract"]
    assert mega_green["role_reason"] != "named_in_product_title"
    # Same ingredients and amounts, different title words: one role decision.
    assert (mega_green["role"], mega_green["role_reason"]) == (plain_title["role"], plain_title["role_reason"])


# A row the cleaner left without an identity has no registry names of its own.
# Its label name can still spell a registered identity ("fish oil"), and the
# title names that row when it spells a registered name of the same identity
# ("Omega-3" is IQM fish_oil's). CVS Omega-3 100 mg (18141) lost its purpose
# ingredient to the one-word rule and was graded on its trace vitamins.
_OMEGA_BLEND = "Flaxseed oil extract (plant based) and purified fish oil concentrate omega fatty acid blend"


def test_title_names_an_unmapped_row_by_an_identity_its_own_name_spells():
    assert _named(_OMEGA_BLEND, None, "omega-3 100 mg")


@pytest.mark.parametrize("name,canonical,text", [
    # One shared word is still no identity, with or without a canonical.
    (_OMEGA_BLEND, None, "omega joint"),
    ("Green Superfood Blend", None, "green tea 500 mg"),
    # The title must name the same identity the row's name spells.
    (_OMEGA_BLEND, None, "krill oil 500 mg"),
    # A mapped row keeps its own identity: the source it came from is not it.
    ("Vitamin D3 (from fish oil)", "vitamin_d", "omega-3 100 mg"),
])
def test_identity_spelled_inside_a_name_needs_the_same_identity_in_the_title(name, canonical, text):
    assert not _named(name, canonical, text)


def test_identity_another_row_carries_does_not_name_an_unmapped_row():
    # 259814: a mapped Fish Oil member already carries the identity.
    blend = "Total Fish Oil and Superba Boost Krill Oil Blend"
    assert _named(blend, None, "triple strength fish oil plus krill oil")
    assert not _named(blend, None, "triple strength fish oil plus krill oil",
                      others=[{"canonical_id": "fish_oil", "raw_source_path": "ingredientRows[0].nestedRows[2].forms[0]"},
                              {"canonical_id": "krill_oil", "raw_source_path": "ingredientRows[0].nestedRows[1]"}])


@pytest.mark.parametrize("name,text,path", [
    # A nested member's title role is its parent's (286147, 47225).
    ("Bergamonte Full Spectrum Citrus Bergamia Risso Fruit Extract Complex",
     "citrus bergamot extract 1000 mg", "ingredientRows[0].nestedRows[0]"),
    ("Milk Protein Hydrolysate", "amplified wheybolic extreme 60 casein vanilla", "ingredientRows[12].nestedRows[1]"),
])
def test_a_nested_unmapped_member_is_not_named_by_a_spelled_identity(name, text, path):
    assert not _named(name, None, text, path=path)


def test_a_blend_its_own_projection_resolves_is_not_named_again():
    # 176071: the 10 mg CereCalase blend is scored as its hemicellulase
    # projection (same source row), not as a second digestive-enzyme subject.
    projection = {"canonical_id": "hemicellulase", "raw_source_path": "ingredientRows[1]"}
    assert _named("CereCalase Proprietary Blend", None, "super digestive enzymes", path="ingredientRows[1]")
    assert not _named("CereCalase Proprietary Blend", None, "super digestive enzymes",
                      path="ingredientRows[1]", others=[projection])

def test_omega_title_keeps_its_fatty_acid_blend_as_the_dose_purpose():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / "raw_title_omega_18141.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assessment = build_scored_artifact(enriched)["quality_pillars_v4"]["dose"]["explanation"]["assessment"]
    assert assessment["dose_participation_basis"] == "declared_purpose_equal_weight"
    assert any("fish_oil" in subject for subject in assessment["unbenchmarked_purpose_ingredients"])


@pytest.mark.parametrize('name,title', [
    ('Plant oil blend (no fish oil)', 'omega-3 100 mg'),
    ('Plant oil blend without fish oil', 'omega-3 100 mg'),
    ('Plant oil blend (fish oil-free)', 'omega-3 100 mg'),
    ('Purified fish oil concentrate', 'omega-3-free'),
])
def test_unmapped_identity_fallback_requires_affirmative_source_and_title(name, title):
    assert not _named(name, None, title)


@pytest.mark.parametrize('name,title', [
    ('Plant oil blend without (fish oil)', 'omega-3 100 mg'),
    ('Plant oil blend (fish oil free)', 'omega-3 100 mg'),
    ('Purified fish oil concentrate', 'omega-3 free'),
])
def test_unknown_title_identity_keeps_original_negation_context(name, title):
    assert not _named(name, None, title)


def test_unknown_title_identity_preserves_free_base_chemistry():
    assert _named('Amino acid blend with L-Arginine free base', None, 'l-arginine 500 mg')
