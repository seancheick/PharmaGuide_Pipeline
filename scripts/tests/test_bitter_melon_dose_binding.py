"""The approved general extract Dose decision reaches source-labelled fruit extracts."""

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("product_id", ["310697", "330419", "306188"])
def test_exact_bitter_melon_fruit_extract_reuses_existing_general_dose_review(product_id):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.modules.botanical_profile import _botanical_benchmark

    path = Path(__file__).parent / "fixtures" / f"raw_bitter_melon_{product_id}.json"
    product = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(json.loads(path.read_text())))[0]
    row = next(r for r in product["ingredient_quality_data"]["ingredients_scorable"]
               if r.get("canonical_id") == "bitter_melon")
    assert row["raw_source_text"] == "Bitter Melon Fruit Extract"
    assert _botanical_benchmark(row, product=product) == "absent"


def test_bitter_melon_review_does_not_transfer_to_unreviewed_whole_powder():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.modules.botanical_profile import _botanical_benchmark

    path = Path(__file__).parent / "fixtures/raw_bitter_melon_310697.json"
    raw = json.loads(path.read_text())
    raw["ingredientRows"][0]["name"] = "Bitter Melon Whole Fruit Powder"
    changed = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(raw))[0]
    row = next(r for r in changed["ingredient_quality_data"]["ingredients_scorable"]
               if r.get("canonical_id") == "bitter_melon")
    assert _botanical_benchmark(row, product=changed) == "unresolved"
