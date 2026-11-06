"""Held labels from the 2026.11.02 build that are ours to finish.

Every disclosed form read below names a form the map already holds. Each entry is
parent-scoped, so it cannot create a new identity on another row, and each was
checked against the printed label or its DSLD record (receipts:
scripts/audits/not_scored_blockers_20261102/research.md).

The second half pins what stays held: a real label limit, an earlier review's hold,
or a decision that is Sean's must not be finished by an alias.
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
    ("312832", "Flaxseed Oil", "flaxseed", "flaxseed oil"),
    ("328465", "GS15-4", "ginseng", "gs15-4 enzyme-fermented asian ginseng root extract"),
    ("328649", "Reishi Mushroom Fruiting Body Extract", "reishi", "reishi fruiting body"),
    ("293269", "Vitamin A", "vitamin_a", "beta-carotene from mixed carotenoids"),
    ("328639", "Vitamin A", "vitamin_a", "beta-carotene from mixed carotenoids"),
])
def test_a_known_disclosed_form_is_read_not_held(pid, name, canonical, form):
    rows = _rows(_enrich(pid), name)
    assert rows, name
    assert {r.get("canonical_id") for r in rows} == {canonical}
    assert not [r for r in rows if r.get("form_match_status") == "unmapped"]
    assert not [r for r in rows if r.get("unmapped_forms")]
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


def test_a_recognized_whole_food_row_is_no_longer_a_conflict():
    name = "Organic freeze-dried banana powder"
    assert _quality_rows(_enrich("28963"), name)[0].get("identity_disposition") != "identity_conflict"


@pytest.mark.parametrize("pid, name, why", [
    ("78327", "N-Acetyl-L-Cystine", "a real compound (PubChem CID 12049111) DSLD groups under NAC (CID 12035)"),
    ("63330", "FoodState farm fresh Beet Root", "reviewed 2026-10-26: exports without a quality identity"),
    ("43662", "FoodState(R) Farm Fresh Beet Root", "reviewed 2026-10-26: exports without a quality identity"),
    ("259374", "Organic Hemp Powder (seed)", "reviewed 2026-10-26: exports without a quality identity"),
])
def test_a_row_held_for_its_identity_stays_a_conflict(pid, name, why):
    rows = _quality_rows(_enrich(pid), name)
    assert [r.get("identity_disposition") for r in rows] == ["identity_conflict"], why


@pytest.mark.parametrize("pid, name, why", [
    ("269689", "Magnesium Lysinate Glycinate Chelate", "Sean 2026-10-13: not an alias for glycinate"),
    ("203385", "Magnesium Bisglycinate Chelate buffered", "Sean 2026-10-13: not an alias for glycinate"),
    ("311132", "Oat Straw Extract", "the label prints straw and seed for one row"),
    ("12144", "Chondroitin Complex", "blend members written as forms, open decision"),
    ("336100", "Biotin", "a hair-complex name on biotin, pinned held in test_identity_label_named_over_group"),
    ("312947", "Psyllium", "LEDGER D21 and this label's correction: the P. asiatica hold stays"),
    ("306204", "Dandelion Root Extract", "LEDGER D21: Taraxacum mongolicum needs a species call"),
    ("328434", "Neuravena", "LEDGER D21: wild green oat aerial parts need a plant-part call"),
    ("214676", "Phosphorus", "phase2 form curation: phosphorus oxide is chemically ambiguous"),
    ("47590", "L-Arginine", "LEDGER Q32: OT2 is an unestablished token"),
    ("246350", "Zychrome Chromium", "LEDGER Q32 and test_dinicocysteinate_never_inherits_polynicotinate_form"),
    ("231826", "Chromium", "LEDGER Q32: Chromium GlycoProtein Matrix is an unestablished token"),
    ("312640", "Corn Silk, Powder", "test_a_named_corn_silk_powder_cannot_claim_extract_form_credit"),
    ("256962", "Magnesium", "magnesium oxide chelate is not an established compound"),
    ("66513", "Manganese", "manganese bisglycinate sulfate chelate is not an established compound"),
    ("27203", "Silica", "silicon hydrolyzed vegetable protein is not an established compound"),
    ("287389", "Virtiva", "this label's correction: do not infer pure ginkgo or phosphatidylserine"),
    ("328649", "Shell-broken Reishi mushroom spore", "the map has no spore form and extract standards do not apply"),
    ("220021", "Calcium", "the printed term reads as two different calcium forms"),
    ("294296", "Wild Cherry Fruit Extract, Powder", "Sean 2026-11-03: species identification is settled; preparation assessment is not"),
    ("241290", "Diosmin", "Sean 2026-11-03: the current mapping does not justify its score"),
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


def test_gs15_4_uses_exact_preparation_and_completed_neutral_dose():
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    from scoring_v4.scored_artifact import build_scored_artifact

    product = _enrich("328465")
    row, = _rows(product, "GS15-4")
    assert row["canonical_id"] == "ginseng"
    assert row["form_id"] == "gs15-4 enzyme-fermented asian ginseng root extract"
    assert row["quantity"] == 200
    assert row["unit"] == "mg"
    assert row.get("bio_score") is None
    dose = score_botanical_purpose_dose(product, row)
    assert dose["metadata"]["benchmark"] == "absent"
    scored = build_scored_artifact(product)
    release = scored["assessment_readiness"]["release_assessment"]
    assert release["blockers"] == []
    assert release["unfinished_source_assessment"] is None
    assert scored["quality_score_status"] == "scored"
    assert "form_quality_unassessed" not in scored["strict_scoring_contract"]["findings"]
    assert scored["product_safety_status"] == "no_known_catalog_concern"
    from build_final_db import validate_export_contract
    assert validate_export_contract(product, scored) == []


@pytest.mark.parametrize("other", ["Panax ginseng", "steamed red ginseng", "HYFRG", "GINST15"])
def test_gs15_4_dose_review_does_not_transfer_to_other_preparations(other, monkeypatch):
    from dose_assessment import _dose_source_preparation_matches, _source_dose_row
    from evidence_resolver import _load_literature_evidence

    product = _enrich("328465")
    row, = _rows(product, "GS15-4")
    record = _load_literature_evidence()["gs15_4_fermented_panax_ginseng_root_extract"]
    assert _dose_source_preparation_matches(product, row, record)
    source = {**_source_dose_row(product, row), "raw_source_text": other}
    monkeypatch.setattr("dose_assessment._source_dose_row", lambda *_: source)
    assert not _dose_source_preparation_matches(product, row, record)
