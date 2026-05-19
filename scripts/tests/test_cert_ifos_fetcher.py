"""IFOS / Nutrasource registry fetcher tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit import verify_certifications as vc  # noqa: E402


IFOS_PRODUCTS_PAYLOAD = {
    "success": True,
    "totalCount": 2,
    "list": [
        {
            "ProductNum": "PLLF0001",
            "ProductName": "+Life Omega 3 Complete",
            "IsIfos": True,
            "CatOmegaFAs": True,
            "ProductImage1": "PLLF0001_1.jpg",
        },
        {
            "ProductNum": "GLIF0039",
            "ProductName": "Dr. Formulated Probiotic Once Daily Prenatal",
            "IsIfos": False,
            "CatOmegaFAs": False,
            "ProductImage1": "GLIF0039_1.jpg",
        },
    ],
}


IFOS_DETAIL_HTML = """
<html>
  <head>
    <title>+Life Omega 3 Complete | +LIFE | Certifications by Nutrasource</title>
  </head>
  <body>
    <a class"jumbotron--banner--link" href="/certified-products/brand?id=PLLF">
      <img class="jumbotron--banner-logo" src="https://andi.nutrasource.ca/CompanyImages/PLLF_Logo.jpg">
    </a>
    <h2>+Life Omega 3 Complete</h2>
    <p><strong>Product Type:</strong> Softgels</p>
    <h2 class="h2--lg">IFOS™ Testing Results</h2>
  </body>
</html>
"""


def test_parse_nutrasource_products_payload_keeps_ifos_rows_only() -> None:
    rows, total_count = vc.parse_nutrasource_products_payload(IFOS_PRODUCTS_PAYLOAD)

    assert total_count == 2
    assert rows == [
        {
            "product_num": "PLLF0001",
            "product": "+Life Omega 3 Complete",
            "thumbnail_url": "https://andi.nutrasource.ca/ProductImages/PLLF0001_1.jpg",
        }
    ]


def test_parse_nutrasource_product_detail_page_extracts_brand_and_certification() -> None:
    detail = vc.parse_nutrasource_product_detail_page(IFOS_DETAIL_HTML, "PLLF0001")

    assert detail == {
        "brand": "+LIFE",
        "product": "+Life Omega 3 Complete",
        "brand_id": "PLLF",
        "certifications": ["IFOS"],
        "product_type": "Softgels",
        "source_url": "https://certifications.nutrasource.ca/certified-products/product?id=PLLF0001",
    }


def test_parse_nutrasource_product_detail_page_requires_title_brand() -> None:
    detail = vc.parse_nutrasource_product_detail_page("<html><title>Product</title></html>", "BAD0001")

    assert detail == {}
