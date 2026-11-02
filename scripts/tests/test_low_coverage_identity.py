"""Real products that read mapped_coverage 0.0 because of how the label is encoded.

Each case is a label whose identity we do know. The gate stays as it is: the
identity has to reach it through the existing owner.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def run():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from score_supplements_v4 import score_product_v4

    logging.disable(logging.INFO)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    cache = {}

    def _run(pid):
        if pid not in cache:
            raw = json.loads((FIXTURES / f"low_coverage_{pid}_raw.json").read_text())
            enriched, _ = enricher.enrich_product(normalizer.normalize_product(copy.deepcopy(raw)))
            cache[pid] = (enriched, score_product_v4(enriched))
        return cache[pid]

    return _run


def _anchors(enriched):
    from scoring_input_contract import get_scoring_ingredients

    rows = get_scoring_ingredients(enriched, strict=True).rows
    return rows, [r for r in rows if r.get("evidence_type") == "blend_anchor_mass"]


# DSLD lists these members as forms of a dosed blend row. The cleaner flattens
# the forms and drops the header, so the blend mass had no row to stand on,
# while the same label written with nestedRows (74457) keeps its anchor.
@pytest.mark.parametrize(
    "pid,anchor,mass",
    [
        ("855", "oregano", 60),
        ("12300", "blessed_thistle", 860),
        ("19598", "celadrin", 1200),
        ("271115", "fenugreek", 1000),  # both are in the title; label order picks
    ],
)
def test_form_encoded_blend_keeps_its_blend_level_anchor(run, pid, anchor, mass):
    enriched, scored = run(pid)
    rows, anchors = _anchors(enriched)
    assert [(a["canonical_id"], a["dose_value"], a["dose_unit"]) for a in anchors] == [(anchor, mass, "mg")]
    assert anchors[0]["evidence_scope"] == "blend_level"
    assert anchors[0]["raw_source_path"].startswith("ingredientRows[")
    assert ".forms[" not in anchors[0]["raw_source_path"]
    assert scored["v4_breakdown"]["completeness_gate"]["mapped_coverage"] >= 0.3
    # A member's amount is not printed: the blend mass never becomes its dose.
    for row in enriched["ingredient_quality_data"]["ingredients"]:
        if ".forms[" in str(row.get("raw_source_path")):
            assert not row.get("quantity")


def test_nested_row_twin_is_the_same_rule(run):
    _, anchors = _anchors(run("74457")[0])
    assert [(a["canonical_id"], a["dose_value"]) for a in anchors] == [("oregano", 60)]


def test_blend_total_by_volume_stays_without_an_anchor(run):
    # 1 mL has no mass; the anchor owner requires one.
    enriched, scored = run("315586")
    assert _anchors(enriched)[1] == []
    assert scored["v4_breakdown"]["completeness_gate"]["mapped_coverage"] == 0.0
