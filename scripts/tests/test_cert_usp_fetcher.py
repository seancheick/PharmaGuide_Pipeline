"""USP Verified registry fetcher tests.

These tests keep the parser and registry merge behavior deterministic without
calling the live Quality-Supplements site.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit import verify_certifications as vc  # noqa: E402


USP_SAMPLE_HTML = """
<div class="view-content">
  <div class="views-view-grid horizontal cols-3 clearfix">
    <div class="views-row clearfix row-1">
      <div class="views-col col-1" style="width: 33.333333333333%;">
        <div class="views-field views-field-url"><span class="field-content">
          <img src="/sites/default/files/2023-07/Nature-Made.png" alt="Nature Made logo" width="100">
        </span></div>
        <div class="views-field views-field-title"><span class="field-content">
          <a href="https://www.naturemade.com/products/omega-3-softgels" target="_blank">
            Omega-3 from Fish &amp; Algae Oil 1200 mg Softgels
          </a>
        </span></div>
      </div>
      <div class="views-col col-2" style="width: 33.333333333333%;">
        <div class="views-field views-field-url"><span class="field-content">
          <img src="/sites/default/files/2023-07/Culturelle.png" alt="Culturelle logo" width="100">
        </span></div>
        <div class="views-field views-field-title"><span class="field-content">
          <a href="https://www.costco.com/culturelle.product.html" target="_blank">
            Culturelle Digestive Daily Probiotic Vegetarian Capsules
          </a>
        </span></div>
      </div>
    </div>
  </div>
</div>
<nav class="pager" role="navigation" aria-labelledby="pagination-heading">
  <a href="/usp_verified_products?page=1" title="Go to next page" rel="next">
    <span class="visually-hidden">Next page</span><span aria-hidden="true">››</span>
  </a>
</nav>
"""


def test_parse_usp_verified_listing_page_extracts_product_cards_and_next_page() -> None:
    products, next_url = vc.parse_usp_verified_listing_page(
        USP_SAMPLE_HTML,
        "https://www.quality-supplements.org/usp_verified_products",
    )

    assert next_url == "https://www.quality-supplements.org/usp_verified_products?page=1"
    assert products == [
        {
            "source_page_url": "https://www.quality-supplements.org/usp_verified_products",
            "brand": "Nature Made",
            "thumbnail_url": "https://www.quality-supplements.org/sites/default/files/2023-07/Nature-Made.png",
            "product_url": "https://www.naturemade.com/products/omega-3-softgels",
            "product": "Omega-3 from Fish & Algae Oil 1200 mg Softgels",
        },
        {
            "source_page_url": "https://www.quality-supplements.org/usp_verified_products",
            "brand": "Culturelle",
            "thumbnail_url": "https://www.quality-supplements.org/sites/default/files/2023-07/Culturelle.png",
            "product_url": "https://www.costco.com/culturelle.product.html",
            "product": "Culturelle Digestive Daily Probiotic Vegetarian Capsules",
        },
    ]


def test_write_registry_merge_existing_preserves_other_programs(tmp_path: Path, monkeypatch) -> None:
    registry_path = tmp_path / "cert_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "_metadata": {
                    "registry_sources": [
                        {
                            "program": "NSF Sport",
                            "url": "https://nsfsport.example/list",
                            "snapshot_date": "2026-05-18",
                            "entry_count": 1,
                        }
                    ],
                    "total_verified_records": 1,
                },
                "verified_records": [
                    {
                        "record_id": "NSF_EXISTING",
                        "program": "NSF Sport",
                        "brand": "Thorne",
                        "product": "Magnesium Bisglycinate",
                        "verified_at": "2026-05-18",
                        "source_url": "https://nsfsport.example/list",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vc, "REGISTRY_PATH", registry_path)

    vc.write_registry(
        [
            {
                "program": "USP Verified",
                "url": vc.USP_VERIFIED_URL,
                "snapshot_date": "2026-05-18",
                "records": [
                    {
                        "record_id": "USP_NEW",
                        "program": "USP Verified",
                        "brand": "Nature Made",
                        "product": "Vitamin D3",
                        "verified_at": "2026-05-18",
                        "source_url": vc.USP_VERIFIED_URL,
                    }
                ],
            }
        ],
        merge_existing=True,
    )

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    programs = {record["program"] for record in payload["verified_records"]}
    assert programs == {"NSF Sport", "USP Verified"}
    source_programs = {source["program"] for source in payload["_metadata"]["registry_sources"]}
    assert source_programs == {"NSF Sport", "USP Verified"}


def test_write_registry_merge_existing_replaces_refreshed_program(tmp_path: Path, monkeypatch) -> None:
    registry_path = tmp_path / "cert_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "_metadata": {
                    "registry_sources": [
                        {"program": "USP Verified", "url": "old", "snapshot_date": "2026-01-01", "entry_count": 1}
                    ],
                    "total_verified_records": 1,
                },
                "verified_records": [
                    {"record_id": "USP_OLD", "program": "USP Verified", "brand": "Old", "product": "Old"}
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vc, "REGISTRY_PATH", registry_path)

    vc.write_registry(
        [
            {
                "program": "USP Verified",
                "url": vc.USP_VERIFIED_URL,
                "snapshot_date": "2026-05-18",
                "records": [
                    {"record_id": "USP_NEW", "program": "USP Verified", "brand": "New", "product": "New"}
                ],
            }
        ],
        merge_existing=True,
    )

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert [record["record_id"] for record in payload["verified_records"]] == ["USP_NEW"]
