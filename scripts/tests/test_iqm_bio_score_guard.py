import copy
import json
import math
from pathlib import Path


def _entry():
    data = json.loads((Path(__file__).parents[1] / "data" / "ingredient_quality_map.json").read_text())
    return data["vitamin_b12_cobalamin"]


def test_integrity_rejects_nonfinite_bool_and_out_of_range_bio_scores():
    from db_integrity_sanity_check import check_iqm

    for value in (-1, 16, True, math.nan, math.inf):
        entry = copy.deepcopy(_entry())
        entry["forms"]["methylcobalamin"]["bio_score"] = value
        findings = []
        check_iqm(findings, {"vitamin_b12_cobalamin": entry}, "ingredient_quality_map.json")
        assert any(
            item.severity == "error"
            and item.path.endswith("methylcobalamin.bio_score")
            for item in findings
        )


def test_integrity_accepts_zero_and_fifteen_bio_scores():
    from db_integrity_sanity_check import check_iqm

    for value in (0, 15):
        entry = copy.deepcopy(_entry())
        entry["forms"]["methylcobalamin"]["bio_score"] = value
        findings = []
        check_iqm(findings, {"vitamin_b12_cobalamin": entry}, "ingredient_quality_map.json")
        assert not any(item.path.endswith("methylcobalamin.bio_score") for item in findings)
