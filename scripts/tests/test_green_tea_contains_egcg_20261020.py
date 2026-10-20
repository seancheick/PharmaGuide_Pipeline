"""EGCG under a green tea extract row is a component, not an unknown form.

30 green_tea_extract rows were held as disclosed_form_unmapped because their
DSLD form named the extract's marker ("Epigallocatechin Gallate" or "EGCG",
labels standardized to 23-94% EGCG). IQM now records green_tea_extract contains
egcg, as turmeric contains curcumin and ginseng contains ginsenosides, so the
classifier reads the token as a component. Standardization credit is not
touched: the row reads green tea extract's existing form from its own label
words, and a 45% EGCG label never reaches the 'green tea extract (50% EGCG)'
form.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


@pytest.mark.parametrize("pid, name, form", [
    ("59208", "Green Tea decaffeinated extract", "green tea extract (unspecified)"),   # 45% EGCG, 98% polyphenols
    ("293955", "Green Tea Leaf Extract", "green tea extract (unspecified)"),          # 23% EGCG
    ("312587", "Green Tea Leaf Extract", "green tea extract (unspecified)"),          # >= 50% EGCG
    ("331495", "Green Tea Leaf Extract", "green tea extract (unspecified)"),          # "standardized to EGCG", no %
    ("33233", "Green Tea extract", "green tea extract (unspecified)"),               # form "EGCG", 94%
    ("317967", "Green Tea Leaf Extract, Decaffeinated", "green tea catechins"),      # its own "total Tea Catechins"
])
def test_an_egcg_marker_token_does_not_hold_the_green_tea_extract_row(enricher, pid, name, form):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from score_supplements_v4 import score_product_v4
    raw = json.loads((FIXTURES / f"green_tea_egcg_{pid}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    row = next(r for r in enriched["ingredient_quality_data"]["ingredients"] if r["name"] == name)
    assert (row["canonical_id"], row["form_id"]) == ("green_tea_extract", form)
    assert row["unmapped_forms"] == []
    readiness = score_product_v4(enriched)["v4_breakdown"]["assessment_readiness"]
    assert "disclosed_form_unmapped" not in readiness["identity"]["blocking_contract_findings"]


def test_green_tea_extract_records_egcg_as_a_component():
    iqm = json.loads((Path(__file__).resolve().parents[1] / "data" / "ingredient_quality_map.json").read_text())
    assert {"type": "contains", "target_id": "egcg"} in [
        {k: rel[k] for k in ("type", "target_id")} for rel in iqm["green_tea_extract"].get("relationships") or []]
