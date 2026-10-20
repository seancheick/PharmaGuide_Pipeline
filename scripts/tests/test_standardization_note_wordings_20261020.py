"""Label wordings of real standardization claims the note did not recognize.

From the 25 products whose label stated the percentage in other words (PR201
measurement), each class verified as a real standardization claim:
- "95% Curcumin" (turmeric rows 16374, 1851, 228978, 3514, 69625, 82607): the
  label's own claim, shown as written (curcumin, not curcuminoids).
- Sensoril "10% (Withanolide) Glycoside Conjugates" (182627, 232923, 328399,
  328514, ...): Sensoril is standardized to >=10% withanolide glycoside
  conjugates and >=32% oligosaccharides.
- "3% Salidrosides" (241941): a Rhodiola standardization marker.
- A bare "80%" whose row name is the compound "Silymarin" (328072, 328076,
  332136).
A percentage that names no compound stays unrecognized.
"""
import pytest


@pytest.mark.parametrize("notes, raw, note", [
    ("Turmeric root extract (Form: 95% Curcumin Note: 150 mg) PlantPart: root", "Turmeric root extract", "95% curcumin"),
    ("std. to 32% oligosaccharides, 10% glycoside conjugates", "Sensoril", "10% glycoside conjugates"),
    ("std. to 10% withanolide glycoside conjugates", "Sensoril", "10% withanolide glycoside conjugates"),
    ("Rhodiola rosea root extract (Form: 3% Salidrosides) PlantPart: root", "Rhodiola rosea root extract", "3% salidrosides"),
    ("80%", "Silymarin", "80% silymarin"),
    # Not verifiable: no compound named, a brand name, or a typo naming another marker.
    ("min. 95%", "Bioperine", None),
    ("95%, 25:1, equivalent to 3,750mg of turmeric", "Turmeric Rhizome Extract", None),
    ("std. to 32% oligosaccharides, 10% Oligosaccharides", "Sensoril", None),
    ("80%", "Milk Thistle extract", None),
])
def test_a_verified_label_wording_is_recognized(notes, raw, note):
    from build_final_db import _compute_standardization_note
    assert _compute_standardization_note({"notes": notes, "raw_source_text": raw}) == note


def _blob_note(pid, name):
    import copy, json, logging
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from build_final_db import build_detail_blob
    from scoring_v4.scored_artifact import build_scored_artifact
    logging.disable(logging.INFO)
    raw = json.loads((Path(__file__).parent / "fixtures" / f"std_note_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    blob = build_detail_blob(copy.deepcopy(enriched), build_scored_artifact(copy.deepcopy(enriched)))
    return next(r for r in blob["ingredients"] if r["name"] == name)["standardization_note"]


def test_a_bare_percent_must_match_the_rows_share_of_its_parent():
    # 307598 Jarrow: EGCG 15 mg under Green Tea Leaf Extract 500 mg is 3% of
    # the extract; its "15%" is EGCG's share of the catechins, not the extract.
    assert _blob_note("307598", "Epigallocatechin Gallate") is None
    # 328035: Curcuminoids 950 mg under Turmeric Rhizome Extract 1 g is 95%.
    assert _blob_note("328035", "Curcuminoids") == "95% curcuminoids"


@pytest.mark.parametrize("ingredient, note", [
    ({"notes": "80%", "raw_source_text": "Silymarin", "quantity": 140, "unit": "mg",
      "parentBlendMass": 175, "parentBlendUnit": "mg"}, "80% silymarin"),
    ({"notes": "20%", "raw_source_text": "Curcuminoids", "quantity": 100, "unit": "mcg",
      "parentBlendMass": 500, "parentBlendUnit": "mcg"}, "20% curcuminoids"),
    ({"notes": "15%", "raw_source_text": "Epigallocatechin Gallate", "quantity": 15, "unit": "mg",
      "parentBlendMass": 500, "parentBlendUnit": "mg"}, None),
    # Not a standardization percentage.
    ({"notes": "0%", "raw_source_text": "Silymarin"}, None),
    ({"notes": "150%", "raw_source_text": "Silymarin"}, None),
    ({"notes": "0% curcuminoids"}, None),
    ({"notes": "provides 50% curcumin absorption"}, None),
    ({"notes": "up to 45% curcumin bioavailability"}, None),
])
def test_the_bare_percent_and_range_guards(ingredient, note):
    from build_final_db import _compute_standardization_note
    assert _compute_standardization_note(ingredient) == note
