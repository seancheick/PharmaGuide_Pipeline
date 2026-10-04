"""Gold dose/UL benchmark (roadmap 1.10): real labels through the production enricher.

Each case's per-day exposure and over-UL verdict were computed by hand from the label (see the
fixture's `basis` per case), not taken from enricher output.
"""

import copy
import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3

SCRIPTS = Path(__file__).resolve().parents[1]
DOC = json.loads((SCRIPTS / "tests" / "fixtures" / "dose_ul_gold_cases.json").read_text())
CASES = DOC["cases"]


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def test_fixture_is_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    assert DOC["_metadata"]["case_count"] == len(CASES)
    assert all(c["basis"] for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_label_yields_expected_daily_exposure_and_ul_verdict(enricher, case):
    product = copy.deepcopy(case["product"])
    product["product_name"] = product["fullName"]
    product["inactiveIngredients"] = []
    enriched, errors = enricher.enrich_product(product)
    assert errors == []
    expect = case["expect"]
    rows = [
        r for r in enriched["rda_ul_data"]["adequacy_results"]
        if r.get("canonical_id") == expect["canonical_id"]
    ]
    assert rows
    assert any(r.get("over_ul") for r in rows) == expect["over_ul"]
    if expect["safety_per_day"] is not None:
        assessed = [r["safety_exposure"] for r in rows if r.get("pct_ul") is not None]
        target = expect["safety_per_day"]
        matches = [e for e in assessed if abs(e["per_day"] - target) <= 0.005 * target]
        assert matches, assessed
        if expect.get("safety_unit"):
            assert matches[0]["unit"] == expect["safety_unit"]
