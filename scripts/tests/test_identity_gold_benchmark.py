"""Gold identity/form benchmark (roadmap 1.10): real label rows through the production enricher.

Expectations in fixtures/identity_gold_cases.json were written from label chemistry and IQM form
keys, not from enricher output. The anchoring test keeps them tied to the live IQM.
"""

import copy
import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3

SCRIPTS = Path(__file__).resolve().parents[1]
DOC = json.loads((SCRIPTS / "tests" / "fixtures" / "identity_gold_cases.json").read_text())
CASES = DOC["cases"]
IQM = json.loads((SCRIPTS / "data" / "ingredient_quality_map.json").read_text())


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def test_fixture_is_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    assert DOC["_metadata"]["case_count"] == len(CASES)
    for c in CASES:
        assert len(c["active_ingredients"]) == len(c["expect"]), c["id"]


def test_expected_identity_is_a_live_iqm_form():
    for c in CASES:
        for exp in c["expect"]:
            assert exp["canonical_id"] in IQM, (c["id"], exp)
            if exp["form_id"] is not None:
                assert exp["form_id"] in IQM[exp["canonical_id"]]["forms"], (c["id"], exp)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_label_row_resolves_to_expected_identity(enricher, case):
    product = {
        "id": f"gold-{case['id']}",
        "product_name": case["product"],
        "activeIngredients": copy.deepcopy(case["active_ingredients"]),
        "inactiveIngredients": [],
    }
    enriched, errors = enricher.enrich_product(product)
    assert errors == []
    rows = [
        r for r in enriched["ingredient_quality_data"]["ingredients"]
        if r.get("source_section") in (None, "active")
    ]
    got = [{k: r.get(k) for k in exp} for r, exp in zip(rows, case["expect"])]
    assert len(rows) == len(case["expect"])
    assert got == case["expect"]
