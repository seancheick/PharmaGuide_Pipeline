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
