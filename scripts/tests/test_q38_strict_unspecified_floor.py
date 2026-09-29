"""Q38: an unspecified form is always the lowest eligible named form minus one."""

import json
from pathlib import Path

from scoring_reference_resolver import authored_unknown_form, unknown_floor, unknown_form_quality


IQM_PATH = Path(__file__).parents[1] / "data" / "ingredient_quality_map.json"


def test_every_authored_unspecified_form_equals_its_mechanical_floor() -> None:
    iqm = json.loads(IQM_PATH.read_text())
    mismatches = []

    for parent_id, parent in iqm.items():
        if parent_id.startswith("_") or not isinstance(parent, dict):
            continue
        authored = authored_unknown_form(parent)
        floor = unknown_floor(parent)
        if authored is None:
            continue
        form_name, form = authored
        if floor is None:
            assert form.get("bio_score") == unknown_form_quality(parent)["bio_score"]
            continue
        if form.get("bio_score") != floor[0]:
            mismatches.append(
                (parent_id, form_name, form.get("bio_score"), floor[0], floor[1])
            )
        assert "unknown_floor" not in form, (
            parent_id,
            form_name,
            "Q38 retired unspecified-form overrides",
        )

    assert not mismatches, mismatches


def test_unverified_legacy_excellent_form_cannot_create_new_excellent_unspecified_score() -> None:
    parent = {
        "forms": {
            "legacy excellent": {"bio_score": 13},
            "x (unspecified)": {"bio_score": 11},
        }
    }
    assert unknown_floor(parent) is None
