"""Three disclosed forms held from release that are known identities.

- "Cerasus avium Fruit Extract" (BulkSupplements 311881-311884; 311881 is pinned in test_unknown_form_quality): Cerasus avium
  (L.) Moench is a synonym of Prunus avium (GBIF usage 3020791, 2026-09-29), the
  species the dark sweet cherry form already names.
- "Vanadyl Sulfate Hydrate" under a Vanadium row (GNC 315319): the hydrate of the
  vanadyl sulfate the parent-scoped source form already reads.
- "Potassium Iodate" under an Iodine row (GNC 33535): PubChem CID 23665710; the
  compound form lives under potassium, so iodine gains a parent-scoped source form
  at its unspecified baseline plus one (no premium).
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("pid, canonical, form", [
    ("311882", "dark_sweet_cherry", "dark sweet cherry powder"),
    ("315319", "vanadium", "vanadyl sulfate (as vanadium source)"),
    ("33535", "iodine", "potassium iodate (as iodine source)"),
])
def test_a_known_identity_is_read_not_held(pid, canonical, form):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import get_scoring_ingredients
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"held_form_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    rows = [r for r in get_scoring_ingredients(enriched, strict=True).rows if r.get("canonical_id") == canonical]
    assert [(r.get("matched_form"), r.get("form_match_status")) for r in rows] == [(form, "mapped")]
    assert build_scored_artifact(enriched)["quality_score_status"] == "scored"


def test_iodate_takes_the_iodine_baseline_and_keeps_unspecified_one_lower():
    from scoring_reference_resolver import unknown_floor

    iodine = json.loads((Path(__file__).resolve().parents[1] / "data" / "ingredient_quality_map.json").read_text())["iodine"]
    assert iodine["forms"]["potassium iodate (as iodine source)"]["bio_score"] == 10
    assert iodine["forms"]["iodine (unspecified)"]["bio_score"] == unknown_floor(iodine)[0] == 9
