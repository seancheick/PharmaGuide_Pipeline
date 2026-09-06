"""A structural blend anchor is not a verified ingredient identity.

Fixtures are the raw-cleaner replays of DSLD 17186 (Nature's Bounty
Glucosamine Chondroitin Complex: the 3,500 mg blend header is unmapped after
the UNII guards) and DSLD 328831 (Thorne Ginseng Plus: "Botalys" maps to
ginseng), enriched with the candidate and pruned to the fields the scoring
contract and modules read. They are the acceptance evidence for the identity
corrections the read-only corpus audit cannot replay.
"""
import json
from pathlib import Path

import pytest

from scoring_input_contract import get_scoring_ingredients, mass_primary_label_actives
from scoring_v4.modules.generic_helpers import get_active_ingredients
from scoring_v4.modules.generic_evidence import resolved_clinical_matches

FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "audits/probiotic_rubric_review_2026_09_04/replay_identity_fixtures_2026_09_06.json"
)


@pytest.fixture(scope="module")
def replays():
    return json.loads(FIXTURES.read_text())


def _header_row(rows):
    return next(r for r in rows if r.get("raw_source_path") == "ingredientRows[6]")


def test_unmapped_blend_header_keeps_its_structural_total(replays):
    rows = get_scoring_ingredients(replays["17186"], strict=True).rows
    header = _header_row(rows)
    assert header["scoring_input_kind"] == "product_level_evidence"
    assert header["quantity"] == 3500.0 and header["unit"] == "mg"
    assert header["canonical_source_db"] == "unmapped"


def test_structural_anchor_is_not_stamped_as_a_mapped_identity(replays):
    header = _header_row(get_scoring_ingredients(replays["17186"], strict=True).rows)
    assert header["identity_kind"] == "label_taxonomy_anchor"
    assert header["mapped"] is False
    assert header["mapped_identity"] is False
    assert header.get("clean_identity_id") is None


def test_verified_label_rows_keep_their_cleaner_identity(replays):
    rows = get_scoring_ingredients(replays["17186"], strict=True).rows
    vitamin_c = next(r for r in rows if r.get("raw_source_path") == "ingredientRows[3]")
    assert vitamin_c["canonical_id"] == "vitamin_c"
    assert vitamin_c["mapped"] is True and vitamin_c["mapped_identity"] is True
    assert "identity_kind" not in vitamin_c


def test_structural_anchor_is_never_a_dose_primary(replays):
    product = replays["17186"]
    primaries = mass_primary_label_actives(product, get_active_ingredients(product))
    assert [row["canonical_id"] for row in primaries] == []


def test_replayed_ginseng_plus_matches_ginseng_not_astragalus(replays):
    ids = [m.get("id") for m in resolved_clinical_matches(replays["328831"])[0]]
    assert "INGR_GINSENG" in ids
    assert not any("ASTRAGALUS" in str(i) for i in ids)
