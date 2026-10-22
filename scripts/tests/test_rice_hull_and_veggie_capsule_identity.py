"""Rice-derived inactives map to the part they name; an explicitly hypromellose capsule is HPMC.

Found 2026-10-22 on approved submissions: "organic rice hulls" (Sports Research
Magnesium Glycinate) resolved to Rice Bran Extract, and "Veggie capsule
(hypromellose)" stayed unmapped. The Rice Bran Extract entry also carried rice
flour, rice starch, rice hull and Nu-FLOW (RIBUS's ground rice hulls) aliases.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

_PRODUCT = {
    "id": "identity-probe", "fullName": "Probe", "brandName": "Probe",
    "productType": {"langualCodeDescription": "Mineral"},
    "physicalState": {"langualCodeDescription": "Capsule"},
    "servingSizes": [{"minQuantity": 1, "maxQuantity": 1, "unit": "Capsule", "order": 1}],
    "servingsPerContainer": 60, "statements": [], "claims": [],
    "ingredientRows": [{
        "order": 1, "name": "Magnesium", "ingredientGroup": "Magnesium", "category": "mineral",
        "forms": [], "nestedRows": [],
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=",
                      "quantity": 100, "unit": "mg", "dailyValueTargetGroup": []}],
    }],
}

_EXPECTED = {
    "organic rice hulls": "OI_RICE_HUSK",
    "Nu-FLOW": "OI_RICE_HUSK",
    "rice hull extract": "OI_RICE_HUSK",  # existing part-aware fallback, no bran alias
    "certified organic rice flour": "PII_RICE_FLOUR",
    "pregelatinized rice starch": "PII_RICE_STARCH",
    "Veggie capsule (hypromellose)": "PII_HPMC",
    "rice flower": None,
    "organic pea starch": "PII_PEA_STARCH",
    "organic oat fiber": "PII_OAT_FIBER",
    "veggie capsule": None,
    "rice bran": "NHA_RICE_BRAN_EXTRACT",  # control: the true bran alias stays
}


@pytest.fixture(scope="module")
def mapped() -> dict[str, str | None]:
    product = copy.deepcopy(_PRODUCT)
    product["otheringredients"] = {"ingredients": [
        {"order": i + 1, "name": name, "category": "other", "forms": []}
        for i, name in enumerate(_EXPECTED)
    ]}
    cleaned = EnhancedDSLDNormalizer().normalize_product(product)
    return {row["name"]: row.get("canonical_id") for row in cleaned["inactiveIngredients"]}


@pytest.mark.parametrize("name,expected", sorted(_EXPECTED.items()))
def test_inactive_identity(mapped, name, expected) -> None:
    assert mapped.get(name) == expected


@pytest.mark.parametrize("text,expected", [
    ("Citric Acid and Microcrystalline Cellulose", ["Citric Acid", "Microcrystalline Cellulose"]),
    ("Purified Water and Glycerin", ["Purified Water", "Glycerin"]),
    ("Veggie capsule (hypromellose) and Water", ["Veggie capsule (hypromellose)", "Water"]),
    ("organic flow agent blend (organic oat fiber, organic pea starch, organic bamboo extract, organic gum arabic, organic sunflower oil, organic sunflower lecithin)",
     ["organic oat fiber", "organic pea starch", "organic bamboo extract", "organic gum arabic", "organic sunflower oil", "organic sunflower lecithin"]),
    ("Mono- and Diglycerides", ["Mono- and Diglycerides"]),
    ("Water and mystery material", ["Water and mystery material"]),
    ("Water (spring and mineral)", ["Water (spring and mineral)"]),
    ("Botanical blend (unknown plant, water)", ["unknown plant", "water"]),
    ("Blend (Water and Glycerin)", ["Water", "Glycerin"]),
    ("Water (] and Glycerin", ["Water (] and Glycerin"]),
    ("Rice extract (bran, hull)", ["Rice extract (bran, hull)"]),
])
def test_disclosure_expansion(text, expected):
    product = copy.deepcopy(_PRODUCT)
    product["otherIngredients"] = {"ingredients": [{"name": text}]}
    cleaned = EnhancedDSLDNormalizer().normalize_product(product)
    assert [row["name"] for row in cleaned["inactiveIngredients"]] == expected
    if text.startswith("organic flow agent blend"):
        assert all(row.get("canonical_id") for row in cleaned["inactiveIngredients"])


def test_expanded_children_keep_display_identity_and_parent_provenance():
    product = copy.deepcopy(_PRODUCT)
    text = "Purified Water and Glycerin"
    product["otherIngredients"] = {"ingredients": [{"name": text}]}
    cleaned = EnhancedDSLDNormalizer().normalize_product(product)
    children = cleaned["inactiveIngredients"]
    displayed = cleaned["display_ingredients"]
    for child in children:
        assert any(row.get("raw_source_path") == child["raw_source_path"]
                   and row.get("canonical_id") == child["canonical_id"] for row in displayed)
    assert len({child["raw_source_path"] for child in children}) == 2
    parent = next(row for row in displayed if row.get("raw_source_text") == text)
    assert parent["raw_source_path"] == "otheringredients.ingredients[0]"
    assert all(child["parent_source_path"] == parent["raw_source_path"] for child in children)


@pytest.mark.parametrize("structured", [
    {"forms": [{"name": "Hypromellose"}]},
    {"quantity": [{"quantity": 100, "unit": "mg"}]},
    {"amount": 100},
    {"nestedRows": [{"name": "Hypromellose"}]},
])
def test_expansion_does_not_duplicate_structured_source_fields(structured):
    product = copy.deepcopy(_PRODUCT)
    product["otherIngredients"] = {"ingredients": [{"name": "Water and Glycerin", **structured}]}
    cleaned = EnhancedDSLDNormalizer().normalize_product(product)
    assert not any(row["name"] == "Glycerin" for row in cleaned["inactiveIngredients"])
