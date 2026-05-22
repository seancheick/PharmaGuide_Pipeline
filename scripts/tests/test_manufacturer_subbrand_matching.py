import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


def _enricher_with_gnc():
    enricher = SupplementEnricherV3()
    enricher.databases["top_manufacturers_data"] = {
        "top_manufacturers": [
            {
                "id": "MANUF_GENERAL_NUTRITION_CENTERS",
                "standard_name": "GNC",
                "aliases": ["General Nutrition Centers"],
            }
        ]
    }
    return enricher


def test_gnc_subbrand_prefix_counts_as_exact_trusted_family_match():
    enricher = _enricher_with_gnc()

    result = enricher._check_top_manufacturer("GNC Beyond Raw", "")

    assert result["found"] is True
    assert result["manufacturer_id"] == "MANUF_GENERAL_NUTRITION_CENTERS"
    assert result["match_type"] == "exact"
    assert result["match_detail"] == "brand_family_prefix"
    assert result["source_path"] == "brandName"


def test_gnc_pro_performance_counts_as_exact_trusted_family_match():
    enricher = _enricher_with_gnc()

    result = enricher._check_top_manufacturer("GNC Pro Performance", "")

    assert result["found"] is True
    assert result["match_type"] == "exact"
    assert result["product_manufacturer_raw"] == "GNC Pro Performance"


def test_embedded_gnc_text_does_not_count_as_brand_family_match():
    enricher = _enricher_with_gnc()

    result = enricher._check_top_manufacturer("AGNC Labs", "")

    assert result.get("match_type") != "exact"
    assert result.get("match_detail") != "brand_family_prefix"
