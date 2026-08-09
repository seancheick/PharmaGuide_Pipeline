"""Regression tests for the form-note curation queue's eligibility mapping."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reports.form_note_curation_report import SAFETY_RE, product_reach  # noqa: E402


def _display_row(path, *, state="assessed"):
    return {
        "raw_source_path": path,
        "score_included": True,
        "analysis": {
            "canonical_id": "vitamin_b2_riboflavin",
            "bio_score": 10.0,
            "form_display_state": state,
        },
    }


def test_reach_uses_the_display_row_source_path_not_first_canonical_match(tmp_path):
    """Two rows for one nutrient may resolve to different IQM forms.

    Canonical ID is not a form identity. The report must follow the same source
    path linkage as the final payload builder or its curation priority is wrong.
    """
    blob = {
        "ingredients": [
            {
                "canonical_id": "vitamin_b2_riboflavin",
                "matched_form": "riboflavin",
                "raw_source_path": "activeIngredients[0]",
            },
            {
                "canonical_id": "vitamin_b2_riboflavin",
                "matched_form": "riboflavin-5-phosphate",
                "raw_source_path": "activeIngredients[1]",
            },
        ],
        "display_ingredients": [
            _display_row("activeIngredients[0]"),
            _display_row("activeIngredients[1]"),
            _display_row("activeIngredients[2]", state="not_disclosed"),
        ],
    }
    (tmp_path / "one-product.json").write_text(json.dumps(blob))

    assert product_reach(tmp_path) == {
        ("vitamin_b2_riboflavin", "riboflavin"): 1,
        ("vitamin_b2_riboflavin", "riboflavin-5-phosphate"): 1,
    }


def test_safety_flag_catches_contraindication_word_family():
    assert SAFETY_RE.search("This form is contraindicated in this scenario.")
