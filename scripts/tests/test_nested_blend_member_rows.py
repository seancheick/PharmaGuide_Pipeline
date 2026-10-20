"""Members of a blend are label rows, at any depth (D1: blend children are
interaction subjects).

Two Clean-stage drops found in the frozen corpus (2026-10-18 baseline):

1. A skip-listed blend ("Proprietary Blend", "Fast-Acting Proprietary Blend")
   nested inside a DSLD group-blend container. The container branch skipped
   it with its members, unlike the default branch, which rescues them.
   GNC Re-Built Mass 42235/42236/42237/36992 lost Astragalus, Panax
   notoginseng and Chinese skullcap, so their interaction rules never ran.
2. A salt-named member of a DSLD blend ("Potassium Chloride", "Glucosamine
   Sulfate", "Creatine HCl", "Betaine HCl") read as a counter-ion descriptor
   of a parent compound and was dropped. A blend is not a compound: its
   members are ingredients. 29207 lost glucosamine and chondroitin (warfarin
   rules); 228714 lost Potassium Chloride under Water Balance Blend.

Fixtures are the real DSLD rows, trimmed to the fields the cleaner reads.
"""
from __future__ import annotations

import copy
import logging
import os
import sys
from typing import Any, Dict, List

import pytest

_SCRIPTS = os.path.join(os.path.dirname(__file__), "..")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

logging.disable(logging.CRITICAL)

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


def _q(quantity, unit, size=200, size_unit="Gram(s)"):
    return [{"quantity": quantity, "unit": unit, "servingSizeOrder": 1,
             "servingSizeQuantity": size, "servingSizeUnit": size_unit}]


def _row(name, category, group, quantity, unit, order, nested=None, **extra):
    row = {"name": name, "category": category, "ingredientGroup": group,
           "quantity": _q(quantity, unit, **extra), "order": order, "ingredientId": 9000 + order}
    if nested:
        row["nestedRows"] = nested
    return row


# DSLD 42235 ingredientRows[9] (GNC Re-Built Mass), verbatim structure.
RE_BUILT_MASS_RAW: Dict[str, Any] = {
    "id": 42235,
    "fullName": "Re-Built Mass Triple Chocolate Cake",
    "brandName": "GNC",
    "servingSizes": [{"order": 1, "minQuantity": 200, "maxQuantity": 200,
                      "minDailyServings": 1, "maxDailyServings": 1, "unit": "Gram(s)"}],
    "ingredientRows": [
        _row("Testosterone Support Matrix", "blend", "Blend (Combination)", 0, "NP", 33, [
            _row("Prickly Pear fruit & pad extract", "botanical", "Prickly Pear Cactus", 1, "Gram(s)", 34),
            _row("Testofen(R) Fenugreek seed extract", "botanical", "Fenugreek", 600, "mg", 35),
            _row("Fast-Acting Proprietary Blend (Herb/Botanical)", "blend",
                 "Proprietary Blend (Herb/Botanical)", 62.5, "mg", 37, [
                     _row("Chinese Skullcap root extract", "botanical", "Baikal Skullcap ", 0, "NP", 38),
                     _row("Cutch Tree bark extract", "botanical", "Catechu", 0, "NP", 39),
                 ]),
            _row("Proprietary Blend", "blend", "Proprietary Blend (Herb/Botanical)", 50, "mg", 40, [
                _row("Astragalus membranaceus root extract", "botanical", "Astragalus", 0, "NP", 41),
                _row("Panax notoginseng root extract", "botanical", "San-Qi Ginseng", 0, "NP", 42),
            ]),
        ]),
    ],
    "otheringredients": {"text": None, "ingredients": []},
}

# DSLD 29207 ingredientRows[5] (Extra Strength Glucosamine Chondroitin Complex).
GLUCOSAMINE_COMPLEX_RAW: Dict[str, Any] = {
    "id": 29207,
    "fullName": "Extra Strength Glucosamine Chondroitin Complex",
    "brandName": "Test",
    "servingSizes": [{"order": 1, "minQuantity": 3, "maxQuantity": 3,
                      "minDailyServings": 1, "maxDailyServings": 1, "unit": "Tablet(s)"}],
    "ingredientRows": [
        _row("Glucosamine Chondroitin Complex", "blend", "Blend (non-nutrient/non-botanical)",
             3000, "mg", 6, [
                 _row("Glucosamine Sulfate", "non-nutrient/non-botanical", "Glucosamine Sulfate",
                      0, "NP", 7, size=3, size_unit="Tablet(s)"),
                 _row("Chondroitin Sulfate", "non-nutrient/non-botanical", "Chondroitin Sulfate",
                      0, "NP", 8, size=3, size_unit="Tablet(s)"),
             ], size=3, size_unit="Tablet(s)"),
    ],
    "otheringredients": {"text": None, "ingredients": []},
}

# DSLD 228714 ingredientRows[14] shape: a blend inside a blend with a salt member.
WATER_BALANCE_RAW: Dict[str, Any] = {
    "id": 228714,
    "fullName": "Thermo Ripped",
    "brandName": "Test",
    "servingSizes": [{"order": 1, "minQuantity": 200, "maxQuantity": 200,
                      "minDailyServings": 1, "maxDailyServings": 1, "unit": "Gram(s)"}],
    "ingredientRows": [
        _row("Thermo Ripped Matrix", "blend", "Blend (Combination)", 568, "mg", 20, [
            _row("Caffeine Anhydrous", "non-nutrient/non-botanical", "Caffeine", 75, "mg", 21),
            _row("Water Balance Blend", "blend", "Blend (Herb/Botanical)", 160, "mg", 22, [
                _row("Dandelion extract", "botanical", "Dandelion", 0, "NP", 23),
                _row("Potassium Chloride", "non-nutrient/non-botanical", "Potassium Chloride", 0, "NP", 24),
            ]),
        ]),
    ],
    "otheringredients": {"text": None, "ingredients": []},
}


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _actives_by_path(cleaned: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {row.get("raw_source_path"): row for row in cleaned.get("activeIngredients") or []}


def _rule_ids(enriched: Dict[str, Any]) -> List[str]:
    return sorted({a["rule_id"] for a in enriched["interaction_profile"]["ingredient_alerts"]})


def test_members_of_skip_listed_blend_inside_group_container_are_rows(normalizer):
    actives = _actives_by_path(normalizer.normalize_product(copy.deepcopy(RE_BUILT_MASS_RAW)))
    expected = {
        "ingredientRows[0].nestedRows[2].nestedRows[0]": ("Chinese Skullcap root extract",
                                                          "Fast-Acting Proprietary Blend (Herb/Botanical)", 62.5),
        "ingredientRows[0].nestedRows[2].nestedRows[1]": ("Cutch Tree bark extract",
                                                          "Fast-Acting Proprietary Blend (Herb/Botanical)", 62.5),
        "ingredientRows[0].nestedRows[3].nestedRows[0]": ("Astragalus membranaceus root extract",
                                                          "Proprietary Blend", 50.0),
        "ingredientRows[0].nestedRows[3].nestedRows[1]": ("Panax notoginseng root extract",
                                                          "Proprietary Blend", 50.0),
    }
    for path, (name, parent, parent_mass) in expected.items():
        row = actives.get(path)
        assert row is not None, f"{name} at {path} must be an active row"
        assert row["name"] == name
        assert row["parentBlend"] == parent
        assert row["isNestedIngredient"] is True
        assert row["parent_source_path"] == path.rsplit(".nestedRows", 1)[0]
        assert row["parentBlendMass"] == parent_mass
        # The member's own amount is "not provided"; it never borrows the blend's.
        assert row["quantity"] in (0, 0.0, None)
    # The dosed siblings keep their own rows unchanged.
    assert actives["ingredientRows[0].nestedRows[0]"]["quantity"] == 1.0
    assert actives["ingredientRows[0].nestedRows[1]"]["quantity"] == 600.0


def test_members_of_skipped_nested_blend_reach_their_interaction_rules(normalizer, enricher):
    cleaned = normalizer.normalize_product(copy.deepcopy(RE_BUILT_MASS_RAW))
    enriched, _ = enricher.enrich_product(cleaned)
    rules = _rule_ids(enriched)
    assert "RULE_INGREDIENT_ASTRAGALUS__AUTOIMMUNE" in rules
    assert "RULE_IQM_CHINESE_SKULLCAP_LIVER" in rules


@pytest.mark.parametrize("path,name", [
    ("ingredientRows[0].nestedRows[0]", "Glucosamine Sulfate"),
    ("ingredientRows[0].nestedRows[1]", "Chondroitin Sulfate"),
])
def test_salt_named_blend_members_are_rows(normalizer, path, name):
    row = _actives_by_path(normalizer.normalize_product(copy.deepcopy(GLUCOSAMINE_COMPLEX_RAW))).get(path)
    assert row is not None, f"{name} is a blend member, not a counter-ion of a parent compound"
    assert row["name"] == name
    assert row["parentBlend"] == "Glucosamine Chondroitin Complex"
    # An undosed named blend member stays reviewable by Evidence.
    assert row["cleaner_row_role"] == "nested_display_only"


def test_salt_named_blend_members_reach_their_interaction_rules(normalizer, enricher):
    cleaned = normalizer.normalize_product(copy.deepcopy(GLUCOSAMINE_COMPLEX_RAW))
    enriched, _ = enricher.enrich_product(cleaned)
    rules = _rule_ids(enriched)
    assert "RULE_INGREDIENT_GLUCOSAMINE" in rules
    assert "RULE_IQM_CHONDROITIN" in rules


def test_salt_member_of_blend_inside_blend_is_a_row(normalizer):
    actives = _actives_by_path(normalizer.normalize_product(copy.deepcopy(WATER_BALANCE_RAW)))
    row = actives.get("ingredientRows[0].nestedRows[1].nestedRows[1]")
    assert row is not None and row["name"] == "Potassium Chloride"
    assert row["parentBlend"] == "Water Balance Blend"
    assert actives["ingredientRows[0].nestedRows[0]"]["name"] == "Caffeine Anhydrous"


def test_counter_ion_under_a_compound_parent_is_still_a_descriptor():
    """The Quatrefolic shape stays a descriptor; only a blend parent changes it."""
    leaf = {"name": "Glucosamine Salt", "category": "non-nutrient/non-botanical",
            "quantity": [{"quantity": 0, "unit": "NP"}]}
    assert EnhancedDSLDNormalizer._is_chemical_decomposition_leaf(leaf) is True
    assert EnhancedDSLDNormalizer._is_chemical_decomposition_leaf(
        {**leaf, "_raw_parent_category": "vitamin"}) is True
    assert EnhancedDSLDNormalizer._is_chemical_decomposition_leaf(
        {**leaf, "_raw_parent_category": "blend"}) is False


def test_flavonoid_class_label_in_a_blend_is_still_composition():
    """A class label names no single identity, whatever its parent."""
    leaf = {"name": "Flavones", "category": "non-nutrient/non-botanical",
            "quantity": [{"quantity": 0, "unit": "NP"}], "_raw_parent_category": "blend"}
    assert EnhancedDSLDNormalizer._is_chemical_decomposition_leaf(leaf) is True


def _protease_product(protease_row: Dict[str, Any]) -> Dict[str, Any]:
    """DSLD 63367 / 221095 shape: a skip-listed protease blend in a group blend."""
    return {
        "id": 63367,
        "fullName": "Active Chocolate",
        "brandName": "Test",
        "servingSizes": [{"order": 1, "minQuantity": 34, "maxQuantity": 34,
                          "minDailyServings": 1, "maxDailyServings": 1, "unit": "Gram(s)"}],
        "ingredientRows": [
            _row("Digestion Complex", "blend", "Blend", 0, "NP", 60, [
                _row("Ginger extract", "botanical", "Ginger ", 5, "mg", 61, size=34),
                protease_row,
            ], size=34),
        ],
        "otheringredients": {"text": None, "ingredients": []},
    }


PROTEASE_NESTED = _row(
    "Proprietary Blend of Proteases", "blend", "Proprietary Blend (non-nutrient/non-botanical)",
    0, "NP", 62, [
        _row("Bacillus subtilis", "bacteria", "Bacillus Subtilis", 0, "NP", 63, size=34),
        _row("Ananas comosus", "botanical", "Pineapple", 0, "NP", 64, size=34),
    ], size=34)
PROTEASE_NESTED["notes"] = "Proprietary Blend of Proteases Note: 3,500 HUT "

PROTEASE_FORMS = _row(
    "Proprietary Blend of Proteases", "blend", "Proprietary Blend (non-nutrient/non-botanical)",
    0, "NP", 62, size=34)
PROTEASE_FORMS["notes"] = ("Proprietary Blend of Proteases (Form: from Bacillus subtilis Genus: Bacillus "
                           "Species: subtilis, and Ananas comosus Genus: Ananas Species: comosus) Note: 3500 HUT ")
PROTEASE_FORMS["forms"] = [
    {"order": 1, "ingredientId": 102360, "prefix": "and", "name": "Ananas comosus",
     "category": "botanical", "ingredientGroup": "Pineapple"},
    {"order": 2, "ingredientId": 109415, "prefix": "from", "name": "Bacillus subtilis",
     "category": "bacteria", "ingredientGroup": "Bacillus Subtilis"},
]


@pytest.mark.parametrize("protease_row", [PROTEASE_NESTED, PROTEASE_FORMS], ids=["nested", "forms"])
def test_protease_source_organisms_are_provenance_not_probiotics(normalizer, enricher, protease_row):
    """The protease is derived from B. subtilis and pineapple: no live culture, no probiotic warning."""
    cleaned = normalizer.normalize_product(copy.deepcopy(_protease_product(protease_row)))
    sources = {row["name"]: row for row in cleaned["activeIngredients"]
               if row["name"] in {"Bacillus subtilis", "Ananas comosus"}}
    assert set(sources) == {"Bacillus subtilis", "Ananas comosus"}
    assert {row["cleaner_row_role"] for row in sources.values()} == {"source_descriptor"}
    enriched, _ = enricher.enrich_product(cleaned)
    assert "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED" not in _rule_ids(enriched)


def test_probiotic_and_enzyme_blend_keeps_its_live_cultures(normalizer, enricher):
    """Control: an "Enzyme" name alone never turns a culture into provenance (288344 shape)."""
    raw = _protease_product(_row("Raw Probiotic & Enzyme Blend", "blend", "Proprietary Blend", 0, "NP", 62, [
        _row("Lactobacillus plantarum", "bacteria", "Lactobacillus Plantarum", 0, "NP", 63, size=34),
    ], size=34))
    cleaned = normalizer.normalize_product(raw)
    [culture] = [row for row in cleaned["activeIngredients"] if row["name"] == "Lactobacillus plantarum"]
    assert culture["cleaner_row_role"] == "nested_display_only"
    enriched, _ = enricher.enrich_product(cleaned)
    assert "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED" in _rule_ids(enriched)


def test_parent_category_working_state_never_reaches_output(normalizer):
    import json

    for raw in (RE_BUILT_MASS_RAW, GLUCOSAMINE_COMPLEX_RAW, WATER_BALANCE_RAW):
        cleaned = normalizer.normalize_product(copy.deepcopy(raw))
        assert "_raw_parent_category" not in json.dumps(cleaned, default=str)
