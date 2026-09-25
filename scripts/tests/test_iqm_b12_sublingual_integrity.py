"""B12 sublingual metadata must not claim an unmeasured absorption fraction."""

import json
from pathlib import Path


def test_sublingual_b12_keeps_identity_but_removes_unsupported_fraction() -> None:
    path = Path(__file__).parents[1] / "data" / "ingredient_quality_map.json"
    forms = json.loads(path.read_text())["vitamin_b12_cobalamin"]["forms"]
    for name in ("methylcobalamin sublingual", "cyanocobalamin sublingual"):
        form = forms[name]
        assert form["absorption_structured"]["value"] is None
        assert form["absorption_structured"]["range_low"] is None
        assert form["absorption_structured"]["range_high"] is None
        assert "bypass" not in form["absorption"].lower()


def test_b12_equivalent_supplement_forms_share_parent_max_and_unknown_is_one_lower() -> None:
    path = Path(__file__).parents[1] / "data" / "ingredient_quality_map.json"
    forms = json.loads(path.read_text())["vitamin_b12_cobalamin"]["forms"]
    named = (
        "methylcobalamin sublingual",
        "methylcobalamin",
        "adenosylcobalamin",
        "hydroxocobalamin",
        "cyanocobalamin sublingual",
        "cyanocobalamin",
    )

    assert {forms[name]["bio_score"] for name in named} == {15}
    assert forms["b12 (unspecified)"]["bio_score"] == 14

    copy = " ".join(str(forms[name].get("notes") or "").lower() for name in forms)
    for unsupported in ("preferred over cyanocobalamin", "modest premium", "form matters significantly"):
        assert unsupported not in copy
