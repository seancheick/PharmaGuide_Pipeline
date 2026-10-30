"""The existing watermelon juice-powder Dose review binds original label rows."""

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("product_id", ["294323", "294324"])
def test_source_labelled_watermelon_juice_powder_uses_approved_dose_review(product_id):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import _route_scoring_rows
    from scoring_v4.modules.botanical_profile import _botanical_benchmark

    path = Path(__file__).parent / "fixtures" / f"raw_watermelon_{product_id}.json"
    product = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(json.loads(path.read_text())))[0]
    row = next(r for r in _route_scoring_rows(product)
               if str(r.get("canonical_id") or "").lower() == "nha_juice_concentrates")
    assert row["raw_source_text"] == "Watermelon Juice, Powder"
    assert _botanical_benchmark(row, product=product) == "absent"
