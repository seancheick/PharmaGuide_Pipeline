"""ConsumerLab CL Certified registry fetcher tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit import verify_certifications as vc  # noqa: E402


SNAPSHOT = "2026-06-15"

CONSUMERLAB_SAMPLE_HTML = """
<table>
  <thead>
    <tr><th>Product</th><th>Review Category</th><th>Brand</th><th>Certified Year</th></tr>
  </thead>
  <tbody>
    <tr>
      <td class="fw-bold sorting_1">GNC Amp Wheybolic - Chocolate Fudge</td>
      <td>Protein Powders</td>
      <td>GNC</td>
      <td class="fw-bold">2026</td>
    </tr>
    <tr>
      <td>Beyond Raw Chemistry Labs Electrolytes</td>
      <td>Electrolytes</td>
      <td>Beyond Raw Chemistry Labs</td>
      <td>2022</td>
    </tr>
  </tbody>
</table>
"""


def test_parse_consumerlab_keeps_current_rows_by_default() -> None:
    records = vc.parse_consumerlab_certified_products(CONSUMERLAB_SAMPLE_HTML, SNAPSHOT)

    assert len(records) == 1
    assert records[0]["program"] == "ConsumerLab"
    assert records[0]["brand"] == "GNC"
    assert records[0]["brand_normalized"] == "gnc"
    assert records[0]["product"] == "GNC Amp Wheybolic - Chocolate Fudge"
    assert records[0]["product_normalized"] == "gnc amp wheybolic chocolate fudge"
    assert records[0]["scope"] == "sku"
    assert records[0]["certified_year"] == 2026
    assert records[0]["current_certification"] is True
    assert records[0]["verified_at"] == SNAPSHOT
    assert records[0]["source_url"] == vc.CONSUMERLAB_CERTIFIED_PRODUCTS_URL


def test_parse_consumerlab_can_include_historical_rows_for_audit() -> None:
    records = vc.parse_consumerlab_certified_products(
        CONSUMERLAB_SAMPLE_HTML,
        SNAPSHOT,
        current_only=False,
    )

    assert [record["product"] for record in records] == [
        "GNC Amp Wheybolic - Chocolate Fudge",
        "Beyond Raw Chemistry Labs Electrolytes",
    ]
    assert [record["current_certification"] for record in records] == [True, False]
