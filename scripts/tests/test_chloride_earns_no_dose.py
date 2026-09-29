"""Chloride is a Nutrition Facts line on every label: it earns no Dose.

`constants.EXCLUDED_NUTRITION_FACTS` lists chloride with sodium, so a Chloride
row is never a scoring ingredient. Since an unsourced Chloride row reaches the
enricher (RR-10), its RDA/UL row gave the multivitamin panel a 31st nutrient
(GNC 69770, "Chloride 72 mg"), while the sourced twin ("Chloride 72 mg (as
Potassium Chloride)", 67309) earned nothing: two rules for one nutrient
(register D22). Sean chose one rule on 2026-09-28: chloride earns no Dose
anywhere. The UL check stands; only the adequacy credit goes.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enriched():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    out = {}
    for pid in ("69770", "67309"):
        raw = json.loads((FIXTURES / f"multi_chloride_{pid}_raw.json").read_text())
        out[pid], _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return out


def _chloride_rows(product):
    rows = (product.get("rda_ul_data") or {}).get("adequacy_results") or []
    return [r for r in rows if "chloride" in str(r.get("nutrient") or "").lower()]


@pytest.mark.parametrize("pid", ["69770", "67309"])
def test_no_chloride_row_earns_adequacy(enriched, pid):
    assert not [r for r in _chloride_rows(enriched[pid]) if r.get("scoring_eligible") is not False]
    assert not [r for r in _chloride_rows(enriched[pid]) if r.get("pct_rda")]


def test_the_chloride_ul_check_stands(enriched):
    (row,) = _chloride_rows(enriched["69770"])
    assert row.get("ul") == 3600 and row.get("pct_ul") == pytest.approx(2.0)


@pytest.mark.parametrize("pid", ["69770", "67309"])
def test_the_multivitamin_panel_has_no_chloride(enriched, pid):
    from scoring_v4.modules.multi_prenatal_dose import _coverage_scores

    assert "chloride" not in _coverage_scores(enriched[pid])
