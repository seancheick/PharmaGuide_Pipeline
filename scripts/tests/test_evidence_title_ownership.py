"""A product title names an active only when it names the active, not its flavor.

The role owner (scoring_input_contract.classify_ingredient_roles) marks a row
claim_prominent when the product title names it, and Evidence lets title
owners win (evidence_resolver.evidence_owner_canonicals). Real DSLD labels,
audits of PRs #205 and #196 (2026-10-20):
- 293904 "Best-Rest Gummy Natural Raspberry-Tea Flavor": the flavor word made
  a 5 mg berry blend the Evidence owner; L-theanine 150 mg and lemon balm
  40 mg (the dosed actives) were excluded and cranberry earned the points.
- 297665 "Beets Beauty Blackberry Melon Flavor": "Melon" from the flavor named
  the Holimel (French melon) row. The Beauty blend the title names stays.
- 321388 "Raw B-12": "B-12" never matched vitamin B12, so a fruit/vegetable
  blend and an enzyme blend owned Evidence (garlic, ginger, bromelain points).
- 40089 "Kids Gummy Fruit & Veggie": the generic word "Fruit" named the Apple
  row (canonical apple_fruit) and so the whole fruit blend.
- 18551 "Endurance Booster Chew Orange" (2026-11-01 snapshot preflight): the
  flavor variant after the dosage form named the 100 mg Citrus sinensis row
  through its registry alias "Orange", which made that row an unbenchmarked
  Dose purpose and held the product from release.
"""

import json
import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_input_contract import (  # noqa: E402
    ROLE_CLAIM_PROMINENT,
    classify_ingredient_roles,
    get_scoring_ingredients,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def products():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    enricher, normalizer = SupplementEnricherV3(), EnhancedDSLDNormalizer()
    out = {}
    for dsld_id in ("18551", "40089", "293904", "297665", "321388"):
        name = "raw_held_assessment_18551.json" if dsld_id == "18551" else f"evidence_title_{dsld_id}_raw.json"
        raw = json.loads((FIXTURES / name).read_text())
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        out[dsld_id] = (enriched, build_scored_artifact(enriched))
    return out


def _title_roles(enriched):
    rows = get_scoring_ingredients(enriched, strict=True).rows
    return {
        str(row.get("canonical_id")): role["role_reason"]
        for row, role in zip(rows, classify_ingredient_roles(enriched))
        if role["role"] == ROLE_CLAIM_PROMINENT
    }


def _evidence(scored):
    return scored["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"]


def test_a_flavor_word_does_not_make_a_berry_blend_the_evidence_owner(products):
    enriched, scored = products["293904"]
    assert "raspberry_unspecified" not in _title_roles(enriched)
    evidence = _evidence(scored)
    assert set(evidence["evidence_owner_canonicals"]) == {"l_theanine", "lemon_balm"}
    assert "cranberry" not in evidence["ingredient_points"]


def test_a_flavor_word_does_not_name_an_ingredient_but_the_named_blend_stays(products):
    enriched, _ = products["297665"]
    roles = _title_roles(enriched)
    assert roles.get("french_melon") != "named_in_product_title"
    # Control: "Beauty" is the product's name for its Organic Beauty Blend.
    assert roles.get("organic_beauty_blend") == "named_in_product_title"


def test_a_hyphenated_vitamin_name_in_the_title_names_the_vitamin(products):
    enriched, scored = products["321388"]
    assert _title_roles(enriched).get("vitamin_b12_cobalamin") == "named_in_product_title"
    evidence = _evidence(scored)
    assert evidence["evidence_owner_canonicals"] == ["vitamin_b12_cobalamin"]
    assert not {"garlic", "ginger", "bromelain"} & set(evidence["ingredient_points"])
    assert evidence["nutrition_authority_canonical"] == "vitamin_b12_cobalamin"


def test_a_generic_plant_part_word_does_not_name_a_species(products):
    enriched, _ = products["40089"]
    assert "apple_fruit" not in _title_roles(enriched)
    assert "apple" not in _title_roles(enriched)


def test_a_flavor_variant_after_the_dosage_form_names_no_ingredient(products):
    enriched, scored = products["18551"]
    assert "citrus_fruit_extract" not in _title_roles(enriched)
    from scoring_v4.scored_artifact import unfinished_source_assessment

    assert unfinished_source_assessment(enriched, scored["_v4_module_breakdown"]) is None


def _roles(title, rows):
    return {
        row["canonical_id"]: role["role_reason"]
        for row, role in zip(
            rows, classify_ingredient_roles({"product_name": title}, module="generic", rows=rows)
        )
    }


def _row(canonical, name, quantity=None, unit="mg", path="ingredientRows[0]", **extra):
    row = {
        "canonical_id": canonical,
        "name": name,
        "raw_source_path": path,
        "source_section": "active",
        "score_eligible_by_cleaner": True,
        "scoreable_identity": True,
        **extra,
    }
    if quantity is not None:
        row.update(quantity=quantity, unit=unit)
    return row


@pytest.mark.parametrize(
    "title, canonical, name",
    [
        # The active is named apart from the flavor phrase.
        ("Elderberry 50 mg Adult Gummy Natural Elderberry Flavor", "elderberry", "Elderberry"),
        # A dosed active right before the flavor word is never part of it.
        ("Ashwagandha Chocolate Flavor", "ashwagandha", "Ashwagandha"),
        ("Melatonin Max Strength 10 mg Natural Strawberry Flavor", "melatonin", "Melatonin"),
        ("Calcium 600 + Vitamin D-3", "vitamin_d", "Vitamin D3"),
        ("Vitamin B-6 50 mg", "vitamin_b6_pyridoxine", "Vitamin B6"),
    ],
)
def test_a_title_still_names_its_active(title, canonical, name):
    rows = [_row(canonical, name, 50.0), _row("zinc", "Zinc", 300.0, path="ingredientRows[1]")]
    assert _roles(title, rows)[canonical] == "named_in_product_title"


@pytest.mark.parametrize(
    "title",
    [
        "Vitamin C Gummy Natural Sour-Orange Flavor",
        "Multi + Energy Gummy Vitamins Raspberry + Black Tea Flavor",
        "Probiotic Natural Raspberry, Peach & Mango Flavor",
        "Biotin Gummies Natural Raspberry Flavored",
    ],
)
def test_an_undosed_member_named_only_by_the_flavor_is_not_title_named(title):
    rows = [
        _row("vitamin_c", "Vitamin C", 250.0),
        _row("berry_blend", "Berry Blend", 5.0, path="ingredientRows[1]", is_proprietary_blend=True),
        _row("raspberry", "Raspberry", path="ingredientRows[1].nestedRows[0]"),
        _row("orange", "Orange", path="ingredientRows[1].nestedRows[1]"),
    ]
    roles = _roles(title, rows)
    assert roles["raspberry"] != "named_in_product_title"
    assert roles["orange"] != "named_in_product_title"


@pytest.mark.parametrize(
    "title",
    ["Endurance Booster Chew Orange", "Vitamin C Chewable Orange", "Zinc Lozenges Orange Cream"],
)
def test_a_flavor_variant_after_the_dosage_form_names_no_registry_alias(title):
    rows = [
        _row("zinc", "Zinc", 300.0),
        _row("citrus_fruit_extract", "Citrus sinensis", 100.0, path="ingredientRows[1]",
             standard_name="Citrus Fruit Extract"),
    ]
    assert _roles(title, rows)["citrus_fruit_extract"] != "named_in_product_title"


@pytest.mark.parametrize(
    "title, canonical, name",
    [
        # The label's own dosed name after the form word is the active.
        ("Immune Chews Elderberry", "elderberry", "Elderberry"),
        # More than two words after the form are not a variant.
        ("Gummies Ashwagandha 300 mg", "ashwagandha", "Ashwagandha"),
        # Nothing after the form word.
        ("Elderberry Gummies", "elderberry", "Elderberry"),
    ],
)
def test_a_dosed_active_after_the_dosage_form_stays_title_named(title, canonical, name):
    rows = [_row(canonical, name, 50.0), _row("zinc", "Zinc", 300.0, path="ingredientRows[1]")]
    assert _roles(title, rows)[canonical] == "named_in_product_title"


@pytest.mark.parametrize("title", ["Immune Gummies Elderberry", "Liquid Drops Elderberry",
                                   "Organic Liquid Elderberry"])
def test_a_blend_member_named_after_the_dosage_form_stays_title_named(title):
    # The variant words are the label's own name for an undosed blend member.
    rows = [
        _row("herbal_blend", "Proprietary Herbal Blend", 192.0, is_proprietary_blend=True),
        _row("elderberry", "Elderberry", path="ingredientRows[0].nestedRows[0]"),
    ]
    assert _roles(title, rows)["elderberry"] == "named_in_product_title"


@pytest.mark.parametrize("title, canonical, name, standard_name", [
    ("Immune Chews Elderberry", "elderberry", "Sambucus nigra", "Elderberry"),
    ("Kids Gummies Turmeric", "turmeric", "Curcuma longa", "Turmeric"),
    # No standard name: the row's canonical identity is the title's word.
    ("Calm Chews Ashwagandha", "ashwagandha", "Withania somnifera", None),
])
def test_a_binomial_row_after_the_dosage_form_stays_title_named(title, canonical, name, standard_name):
    rows = [_row(canonical, name, 50.0, standard_name=standard_name),
            _row("zinc", "Zinc", 300.0, path="ingredientRows[1]")]
    assert _roles(title, rows)[canonical] == "named_in_product_title"


def test_a_leading_dosage_form_still_lets_the_title_name_a_blend_member():
    # 268432 "Liquid Elderberry": elderberry is an undosed member of the
    # proprietary herbal blend, and the title names it.
    rows = [
        _row("herbal_blend", "Proprietary Herbal Blend", 192.0, is_proprietary_blend=True),
        _row("elderberry", "Elderberry", path="ingredientRows[0].nestedRows[0]"),
    ]
    assert _roles("Liquid Elderberry", rows)["elderberry"] == "named_in_product_title"


def test_natural_opens_the_flavor_phrase():
    rows = [
        _row("hair_skin_nails_blend", "Hair, Skin & Nails Blend", 50.0, is_proprietary_blend=True),
        _row("strawberry", "Strawberry", path="ingredientRows[0].nestedRows[0]"),
    ]
    roles = _roles("Hair, Skin & Nails Natural Strawberry Flavor", rows)
    assert roles["hair_skin_nails_blend"] == "named_in_product_title"
    assert roles["strawberry"] != "named_in_product_title"


def test_unflavored_is_not_a_flavor_phrase():
    rows = [_row("creatine_monohydrate", "Creatine Monohydrate", 5000.0)]
    assert _roles("Creatine Monohydrate Unflavored", rows)["creatine_monohydrate"] == "named_in_product_title"
