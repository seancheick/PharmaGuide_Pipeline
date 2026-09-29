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



def test_chloride_mass_is_not_label_active_mass(enriched):
    """The blend-opacity share divides hidden blend mass by the label's active
    mass. Sodium never enters that total (the cleaner files it as Nutrition
    Facts); Chloride must not either: the total equals the same label's
    total with no Chloride amount. (DSLD nests 25 unrelated rows under this
    Chloride row, so the twin keeps the row and drops only its amount.)"""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((FIXTURES / "multi_chloride_69770_raw.json").read_text())
    for row in raw["ingredientRows"]:
        if row.get("name") == "Chloride":
            row["quantity"] = []
    without, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))

    def total(product):
        return (product.get("proprietary_data") or {}).get("total_active_mg")

    assert total(enriched["69770"]) == pytest.approx(total(without))
