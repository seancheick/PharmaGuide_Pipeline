from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


def test_root_label_claims_are_present_in_the_audit_ledger() -> None:
    enricher = SupplementEnricherV3()
    product = {
        "claims": [
            {"langualCodeDescription": "Supports immune health"},
            {"text": "Gluten free"},
        ],
        "activeIngredients": [],
        "brandName": "",
    }
    enriched = {
        "ingredient_quality_data": {"ingredients": []},
        "contaminant_data": {},
        "compliance_data": {},
        "manufacturer_data": {},
        "delivery_data": {},
    }

    ledger = enricher._build_match_ledger(product, enriched)["match_ledger"]
    claims = ledger["domains"]["claims"]

    assert claims["total_raw"] == 2
    assert claims["recognized_non_scorable"] == 2
    assert [entry["raw_source_path"] for entry in claims["entries"]] == [
        "claims[0]",
        "claims[1]",
    ]
