"""Gold interaction-subject benchmark (roadmap 1.10): real label rows through the production enricher.

Each case names the rules the ingredient must reach (recall) and the rules it must not inherit
(false-severe). The expectations come from the ingredient's chemistry, not from enricher output.
"""

import copy
import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3

SCRIPTS = Path(__file__).resolve().parents[1]
DOC = json.loads((SCRIPTS / "tests" / "fixtures" / "interaction_subject_gold_cases.json").read_text())
CASES = DOC["cases"]
RULE_IDS = {
    r["id"]
    for r in json.loads((SCRIPTS / "data" / "ingredient_interaction_rules.json").read_text())["interaction_rules"]
}


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def test_fixture_is_well_formed_and_anchored_to_live_rules():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    assert DOC["_metadata"]["case_count"] == len(CASES)
    for c in CASES:
        assert c["must_fire"], c["id"]
        assert set(c["must_fire"]) | set(c["must_not_fire"]) <= RULE_IDS, c["id"]
        assert not set(c["must_fire"]) & set(c["must_not_fire"]), c["id"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_label_row_reaches_expected_rules(enricher, case):
    product = {
        "id": f"gold-{case['id']}",
        "product_name": case["product"],
        "activeIngredients": copy.deepcopy(case["active_ingredients"]),
        "inactiveIngredients": [],
    }
    enriched, errors = enricher.enrich_product(product)
    assert errors == []
    fired = {a["rule_id"] for a in enriched["interaction_profile"].get("ingredient_alerts") or []}
    assert not fired & set(case["must_not_fire"])
    assert set(case["must_fire"]) <= fired
