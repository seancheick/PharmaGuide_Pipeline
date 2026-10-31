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


def _named(name, canonical, text):
    from scoring_input_contract import _named_in_title
    return _named_in_title({"name": name, "canonical_id": canonical}, text)


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
