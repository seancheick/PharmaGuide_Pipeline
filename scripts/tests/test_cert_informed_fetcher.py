"""Informed Choice / Informed Sport registry fetcher tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.verify_certifications import parse_informed_certified_products_page  # noqa: E402


INFORMED_SAMPLE_HTML = """
<div class="grid-3-column-product-list js-view-dom-id-example">
  <header><h3 class="medium-bottom-margin">May-2026</h3></header>
  <div class="grid-item-wrapper">
    <h3><h4 class='small-bottom-margin'>1st Phorm</h4></h3>
    <div class="views-view-grid horizontal cols-1 clearfix">
      <div class="views-row clearfix row-1">
        <div class="views-col col-1"><div class="views-field views-field-title">
          <span class="field-content">Creatine Monohydrate</span>
        </div></div>
      </div>
      <div class="views-row clearfix row-2">
        <div class="views-col col-1"><div class="views-field views-field-title">
          <span class="field-content">Phormula-1 Clear</span>
        </div></div>
      </div>
    </div>
  </div>
  <div class="grid-item-wrapper">
    <h3><h4 class='small-bottom-margin'>Anea Nutrition</h4></h3>
    <div class="views-view-grid horizontal cols-1 clearfix">
      <div class="views-row clearfix row-1">
        <div class="views-col col-1"><div class="views-field views-field-title">
          <span class="field-content">Anea Nutrition - Whey Protein Powder</span>
        </div></div>
      </div>
    </div>
  </div>
</div>
"""


def test_parse_informed_certified_products_page_extracts_brand_grouped_products() -> None:
    products, listing_month = parse_informed_certified_products_page(INFORMED_SAMPLE_HTML)

    assert listing_month == "May-2026"
    assert products == [
        {"brand": "1st Phorm", "product": "Creatine Monohydrate"},
        {"brand": "1st Phorm", "product": "Phormula-1 Clear"},
        {"brand": "Anea Nutrition", "product": "Anea Nutrition - Whey Protein Powder"},
    ]
