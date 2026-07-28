import json
from pathlib import Path


DATA = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curated_interactions"
    / "curated_interactions_v1.json"
)
BY_ID = {
    row["id"]: row for row in json.loads(DATA.read_text())["interactions"]
}


def test_folate_interaction_is_phenytoin_specific_and_excludes_valproate():
    rule = BY_ID["DSI_ANTICONV_FOLATE"]

    assert rule["agent1_id"] == "8183"
    assert rule["agent1_name"] == "Phenytoin"
    assert rule["source_pmids"] == ["6370643"]
    assert "phenytoin" in rule["mechanism"].lower()
    assert "valproate" not in rule["mechanism"].lower()
    assert "anticonvulsants" not in rule["mechanism"].lower()
