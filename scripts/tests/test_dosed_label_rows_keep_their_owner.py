"""A dosed Supplement Facts row keeps the owner its raw label gives it.

Two cleaner rules dropped a dosed row into no ledger (audit RR-09/RR-10,
reproduced by Codex):

- Nutricost BCAA 1000 mg (269317) prints "2:1:1 BCAA 1,000 mg" over L-Leucine,
  L-Isoleucine and L-Valine. DSLD filed that total as `category=other,
  group=Header`, and every Header is label context, so the total and its ratio
  vanished; the same label filed as `blend` (270253) kept both. An explicitly
  named BCAA total over printed children is a structural dose owner, like the
  EAA total (5e000975).
- Nutricost Intra (311733) prints "Chloride 335 mg" (DSLD category `mineral`,
  no source form). Unsourced Chloride was treated as a Nutrition Facts line,
  but the Nutrition Facts ledger has no chloride field, so the row reached
  neither the actives nor nutritionalInfo. DSLD's `mineral` owns it: an active
  row that reaches the enricher like a sourced Chloride row ("Chloride (as
  Potassium Chloride)", 67309), which records it as `excluded_nutrition_fact`.
  Whether chloride earns Dose is that list's policy, unchanged here.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def normalizer():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer()


def _clean(normalizer, label):
    return normalizer.normalize_product(json.loads((FIXTURES / label).read_text()))


def test_a_dosed_bcaa_header_is_a_blend_total_like_its_blend_twin(normalizer):
    header = next(r for r in _clean(normalizer, "bcaa_269317_raw.json")["activeIngredients"]
                  if r.get("name") == "2:1:1 BCAA")
    twin = next(r for r in _clean(normalizer, "bcaa_270253_raw.json")["activeIngredients"]
                if r.get("name") == "2:1:1 BCAA")
    assert header.get("cleaner_row_role") == twin.get("cleaner_row_role") == "blend_header_total"
    assert header.get("quantity") == 1000


def test_a_bcaa_name_alone_stays_an_ordinary_active(normalizer):
    """GNC 1063 lists "Branched-Chain Amino Acids" with its own amount and no
    printed children: an ordinary active, not a total."""
    row = next(r for r in _clean(normalizer, "bcaa_1063_raw.json")["activeIngredients"]
               if r.get("name") == "Branched-Chain Amino Acids")
    assert row.get("cleaner_row_role") == "active_scorable"


def test_an_unsourced_chloride_mineral_is_an_active(normalizer):
    cleaned = _clean(normalizer, "bcaa_311733_raw.json")
    chloride = [r for r in cleaned["activeIngredients"] if r.get("name") == "Chloride"]
    assert len(chloride) == 1 and chloride[0].get("quantity") == 335


def test_the_chloride_row_is_accounted_like_a_sourced_one(normalizer):
    from enrich_supplements_v3 import SupplementEnricherV3

    enriched, _ = SupplementEnricherV3().enrich_product(_clean(normalizer, "bcaa_311733_raw.json"))
    rows = [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("name") == "Chloride"]
    assert [(r.get("canonical_id"), r.get("skip_reason")) for r in rows] == [
        ("chloride", "excluded_nutrition_fact")]


def test_a_printed_nutrition_fact_row_is_not_a_missing_active(normalizer):
    """311733 prints every active with its amount, plus Chloride 335 mg. The
    Chloride line is disclosed but not an active (excluded_nutrition_fact), so
    it must not count against complete active disclosure: before, the declared
    count (14 cleaned rows) exceeded the 13 active rows and the product lost
    the 6-point disclosure credit it had earned."""
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched, _ = SupplementEnricherV3().enrich_product(_clean(normalizer, "bcaa_311733_raw.json"))
    scored = build_scored_artifact(enriched)
    disclosure = (scored["_v4_module_breakdown"]["dimensions"]["transparency"]["metadata"]
                  ["complete_active_disclosure"])
    assert disclosure["qualifies"] is True
    assert disclosure["declared_active_count"] == disclosure["active_row_count"] == 13
