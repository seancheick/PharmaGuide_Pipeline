"""Held labels from the 2026.11.02 build that are ours to finish.

Every disclosed form below is a known identity the map did not read. Each entry is
parent-scoped, so it cannot create a new identity on another row, and each was
checked against the printed label or its DSLD record (receipts:
scripts/audits/not_scored_blockers_20261102/research.md). A form whose quality
nobody has established takes the parent's authored unspecified form, the floor.

The second half pins what stays held: a real label limit, or a decision that is
Sean's, must not be finished by an alias.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _enrich(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"not_scored_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


def _rows(enriched, name):
    from scoring_input_contract import get_scoring_ingredients

    return [r for r in get_scoring_ingredients(enriched, strict=True).rows if r.get("name") == name]


def _quality_rows(enriched, name):
    return [r for r in enriched["ingredient_quality_data"]["ingredients"] if r.get("name") == name]


@pytest.mark.parametrize("pid, name, canonical, form", [
    ("246350", "Zychrome Chromium", "chromium", "chromium (unspecified)"),
    ("231826", "Chromium", "chromium", "chromium (unspecified)"),
    ("295001", "Conjugated Linoleic Acid", "cla", "cla 80%"),
    ("312640", "Corn Silk, Powder", "corn_silk", "corn silk (unspecified)"),
    ("306204", "Dandelion Root Extract", "dandelion", "dandelion root"),
    ("294296", "Wild Cherry Fruit Extract, Powder", "dark_sweet_cherry", "dark sweet cherry powder"),
    ("241290", "Diosmin", "diosmin", "diosmin (unspecified)"),
    ("312832", "Flaxseed Oil", "flaxseed", "flaxseed oil"),
    ("287389", "Virtiva", "ginkgo", "ginkgo (unspecified)"),
    ("328465", "GS15-4", "ginseng", "fermented red ginseng"),
    ("47590", "L-Arginine", "l_arginine", "l-arginine base"),
    ("66513", "Manganese", "manganese", "manganese (unspecified)"),
    ("328434", "Neuravena", "oat_straw", "oat straw extract (unspecified)"),
    ("214676", "Phosphorus", "phosphorus", "phosphorus (unspecified)"),
    ("312947", "Psyllium", "psyllium", "psyllium (unspecified)"),
    ("328649", "Reishi Mushroom Fruiting Body Extract", "reishi", "reishi fruiting body"),
    ("328649", "Shell-broken Reishi mushroom spore", "reishi", "reishi (unspecified)"),
    ("27203", "Silica", "silica", "silica (unspecified)"),
    ("293269", "Vitamin A", "vitamin_a", "beta-carotene from mixed carotenoids"),
    ("328639", "Vitamin A", "vitamin_a", "beta-carotene from mixed carotenoids"),
    ("220021", "Calcium", "calcium", None),
    ("256962", "Magnesium", "magnesium", None),
])
def test_a_known_disclosed_form_is_read_not_held(pid, name, canonical, form):
    rows = _rows(_enrich(pid), name)
    assert rows, name
    assert {r.get("canonical_id") for r in rows} == {canonical}
    assert not [r for r in rows if r.get("form_match_status") == "unmapped"]
    assert not [r for r in rows if r.get("unmapped_forms")]
    if form:
        assert {r.get("form_id") for r in rows} == {form}


# One pair at a time: each label row and the single identity it resolves to.
@pytest.mark.parametrize("pid, name, canonical", [
    ("328006", "Oregano Flower, Leaf Oil", "oregano"),
    ("285637", "organic Chamomile (flower) extract", "chamomile"),
])
def test_a_source_verified_pair_resolves_to_that_identity(pid, name, canonical):
    rows = _quality_rows(_enrich(pid), name)
    assert [r.get("canonical_id") for r in rows] == [canonical]
    assert rows[0].get("identity_disposition") != "identity_conflict"


@pytest.mark.parametrize("pid, name", [
    ("63330", "FoodState farm fresh Beet Root"),
    ("43662", "FoodState(R) Farm Fresh Beet Root"),
    ("28963", "Organic freeze-dried banana powder"),
    ("259374", "Organic Hemp Powder (seed)"),
])
def test_a_recognized_whole_food_row_is_no_longer_a_conflict(pid, name):
    enriched = _enrich(pid)
    assert _quality_rows(enriched, name)[0].get("identity_disposition") != "identity_conflict"
    assert name not in [r.get("name") for r in _rows(enriched, name) if r.get("canonical_id") == "dietary_nitrate"]


def test_a_label_that_disagrees_with_dsld_about_a_real_compound_stays_held():
    # The label prints N-acetyl-L-cystine, a real compound (PubChem CID 12049111);
    # DSLD groups the row under N-acetyl cysteine (CID 12035). Which one is Sean's call.
    rows = _quality_rows(_enrich("78327"), "N-Acetyl-L-Cystine")
    assert [r.get("identity_disposition") for r in rows] == ["identity_conflict"]


@pytest.mark.parametrize("pid, name, why", [
    ("269689", "Magnesium Lysinate Glycinate Chelate", "Sean 2026-10-13: not an alias for glycinate"),
    ("203385", "Magnesium Bisglycinate Chelate buffered", "Sean 2026-10-13: not an alias for glycinate"),
    ("311132", "Oat Straw Extract", "the label prints straw and seed for one row"),
    ("12144", "Chondroitin Complex", "blend members written as forms, open decision"),
    ("336100", "Biotin", "a hair-complex name on biotin, pinned held in test_identity_label_named_over_group"),
])
def test_a_real_limit_or_open_decision_stays_held(pid, name, why):
    assert [r for r in _rows(_enrich(pid), name) if r.get("form_match_status") == "unmapped"], why


def test_a_label_with_only_zero_percent_rows_stays_held():
    # Colon Pure prints 0% with no amount and no dosed active. A printed 0% reads as
    # absent (Sean, 2026-09-26), so calling it a no-amount row would mark it present.
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich("212411")
    [row] = [r for r in enriched["activeIngredients"] if r["name"] == "Vitamin C"]
    assert row["cleaner_row_role"] != "daily_value_no_amount"
    assert build_scored_artifact(enriched)["quality_score_status"] == "not_scored"
