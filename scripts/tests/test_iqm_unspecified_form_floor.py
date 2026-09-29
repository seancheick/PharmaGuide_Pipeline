"""IQM unspecified-form contract after Q38 (2026-09-28)."""

import json
from pathlib import Path

from scoring_reference_resolver import authored_unknown_form, unknown_floor, unknown_form_quality


IQM_PATH = Path(__file__).parents[1] / "data" / "ingredient_quality_map.json"


def _iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


def test_every_authored_unspecified_form_is_lowest_eligible_named_minus_one() -> None:
    mismatches = []
    for parent_id, parent in _iqm().items():
        if parent_id.startswith("_") or not isinstance(parent, dict):
            continue
        authored = authored_unknown_form(parent)
        floor = unknown_floor(parent)
        if authored is None or floor is None:
            continue
        form_name, form = authored
        if form.get("bio_score") != floor[0]:
            mismatches.append((parent_id, form_name, form.get("bio_score"), floor))
        assert "unknown_floor" not in form, (parent_id, form_name)
        resolved = unknown_form_quality(parent)
        assert resolved["form_id"] == form_name
        assert resolved["bio_score"] == floor[0]
        assert resolved["basis"] == "authored_unspecified_mechanical_floor"
    assert not mismatches, mismatches


def test_ineligible_named_forms_do_not_lower_the_unspecified_floor() -> None:
    parent = {
        "forms": {
            "plain": {"bio_score": 8},
            "wrong compound": {"bio_score": 1, "parent_relationship": "different_compound"},
            "x (unspecified)": {"bio_score": 7},
        }
    }
    assert unknown_floor(parent) == (7.0, "plain")
    assert unknown_form_quality(parent)["bio_score"] == 7.0


def test_biological_and_local_matrix_parents_follow_the_same_rule() -> None:
    iqm = _iqm()
    expected = {
        "bifidobacterium_lactis": 11,
        "lions_mane": 8,
        "magnesium": 1,
        "vitamin_a": 4,
        "vanadium": 6,
    }
    for parent_id, score in expected.items():
        _, form = authored_unknown_form(iqm[parent_id])
        assert form["bio_score"] == unknown_floor(iqm[parent_id])[0] == score
