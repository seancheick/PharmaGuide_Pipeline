"""Branded single extracts that DSLD files as blends keep their real IQM form.

Follow-ups to golden-set finding F2 (Prosterol, 269286). Once a one-constituent
DSLD blend row is read as its ingredient, the IQM form it reaches is what
Formulation scores:

- Pure Encapsulations Joint Complex (293989) prints "Mervia" / Turmeric
  Phytosome. A phytosome is a phospholipid complex (Meriva), not a liposome.
- Life Extension Blueberry Extract (328293) prints "AuroraBlue" / Wildcrafted
  Blueberry Complex, a wild blueberry extract. Its form was unmapped, so the
  label was held as not scored.
- Doctor's Best Celadrin 500 mg (302646) prints "Celadrin" / Esterified Fatty
  Acid Carbons, the cetylated fatty acid material itself. Read as a blend, the
  label had nothing to assess.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _run(pipeline, label):
    from scoring_v4.scored_artifact import build_scored_artifact

    normalizer, enricher = pipeline
    cleaned = normalizer.normalize_product(json.loads((FIXTURES / label).read_text()))
    enriched, _ = enricher.enrich_product(cleaned)
    return enriched, build_scored_artifact(enriched)


def _iqd(enriched, name):
    [row] = [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("name") == name]
    return row


def test_turmeric_phytosome_is_meriva_not_liposomal():
    iqm = json.loads((Path(__file__).parents[1] / "data" / "ingredient_quality_map.json").read_text())
    forms = iqm["curcumin"]["forms"]
    assert "turmeric phytosome" in [a.casefold() for a in forms["meriva curcumin"]["aliases"]]
    assert "turmeric phytosome" not in [a.casefold() for a in forms["liposomal curcumin"]["aliases"]]


def test_mervia_turmeric_phytosome_reaches_meriva(pipeline):
    enriched, _ = _run(pipeline, "mervia_turmeric_phytosome_293989_raw.json")
    row = _iqd(enriched, "Mervia")
    assert (row["canonical_id"], row.get("matched_form")) == ("curcumin", "meriva curcumin")


def test_aurorablue_is_scored_wild_blueberry(pipeline):
    enriched, scored = _run(pipeline, "aurorablue_328293_raw.json")
    row = _iqd(enriched, "AuroraBlue")
    assert (row["canonical_id"], row.get("matched_form")) == ("blueberry", "blueberry extract")
    assert row.get("cleaner_row_role") == "active_scorable"
    assert scored["quality_score_status"] == "scored"


def test_celadrin_is_one_assessable_active(pipeline):
    enriched, scored = _run(pipeline, "celadrin_302646_raw.json")
    row = _iqd(enriched, "Celadrin")
    assert row["canonical_id"] == "celadrin" and row.get("cleaner_row_role") == "active_scorable"
    assert scored["quality_pillars_v4"]["evidence"].get("evidence_result_state") != "no_assessable_actives"


def test_prosterol_reaches_the_supercritical_co2_form(pipeline):
    """Prosterol is Euromed's supercritical CO2 saw palmetto extract
    (DSLD 269589 "With Prosterol Euromed"; PMID 27186566)."""
    enriched, _ = _run(pipeline, "saw_palmetto_prosterol_269286_raw.json")
    row = _iqd(enriched, "Prosterol")
    assert (row["canonical_id"], row.get("matched_form")) == (
        "saw_palmetto", "supercritical CO₂ saw palmetto extract")


def test_recovered_coq10_does_not_revive_a_rejected_nutritional_anchor(pipeline):
    """294034: the real MicroActive row is assessable, but 30mg is not an RDA."""
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    enriched, scored = _run(pipeline, "one_multivitamin_294034_raw.json")
    dose = score_dose(enriched)
    coverage = dose["metadata"]["coverage_nutrient_scores"]
    assert "vitamin_d" in coverage  # real nutritional contributions survive
    for key in ("coenzyme_q10", "inositol", "alpha_lipoic_acid", "lutein", "zeaxanthin", "lycopene"):
        assert key not in coverage
    assert scored["quality_score_status"] == "scored"
