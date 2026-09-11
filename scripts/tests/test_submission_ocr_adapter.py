"""Reading a Facts panel from geometry alone.

This adapter exists so that agreement between two extractors means something.
That only holds if it fails differently from a vision model, which is why it
reconstructs rows from where words physically sit and never asks anything to
understand the label. These tests drive it with synthetic OCR output, so the
assembly rules are asserted exactly and no engine is downloaded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction.adapters.ocr_adapter import (  # noqa: E402
    PROVIDER,
    RULES_VERSION,
    OcrLabelAdapter,
    OcrLine,
    OcrPage,
)
from submission_review.extraction.extractor import (  # noqa: E402
    ExtractionConfig,
    ExtractionError,
    PreparedBundle,
    PreparedInput,
)

_DIGEST = "a" * 64
#: The envelope requires real photo identifiers, not placeholders.
_PHOTO = "11111111-1111-4111-8111-111111111111"


def _line(text, top, left=10.0, width=260.0, height=18.0):
    return OcrLine(text=text, left=left, top=top,
                   right=left + width, bottom=top + height)


def _photo(photo_id=_PHOTO, categories=("supplement_facts",)):
    data = b"\xff\xd8fixture"
    return PreparedInput(
        input_id="i1", photo_id=photo_id, original_sha256=_DIGEST,
        sent_sha256=_DIGEST, content_type="image/jpeg", byte_size=len(data),
        data=data, categories=categories,
    )


def _bundle(*photos):
    return PreparedBundle(submission_id="s1", evidence_revision=2,
                          photos=photos or (_photo(),))


def _config(**overrides):
    values = dict(provider=PROVIDER, model="paddleocr", model_digest="c" * 64,
                  prompt_version=RULES_VERSION,
                  retention_policy_version="local-only-v1")
    values.update(overrides)
    return ExtractionConfig(**values)


class _Reader:
    def __init__(self, lines_by_photo):
        self._lines = lines_by_photo

    def read(self, data, *, photo_id, input_id):
        return OcrPage(photo_id=photo_id, input_id=input_id,
                       lines=tuple(self._lines.get(photo_id, ())))


def _extract(lines, bundle=None, config=None):
    adapter = OcrLabelAdapter(_Reader({_PHOTO: lines}))
    return adapter.extract(bundle or _bundle(), config or _config()).draft


def test_a_row_is_assembled_from_boxes_at_the_same_height() -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Vitamin C", 40, left=10, width=120),
        _line("500 mg", 40, left=300, width=70),
    ])

    rows = draft["ingredient_rows"]
    assert len(rows) == 1
    assert rows[0]["display_name"]["value"] == "Vitamin C"
    # A flat text dump destroys the association between a name and its amount;
    # the vertical band is what recovers it.
    assert rows[0]["amount"]["value"] == {"value": 500.0, "unit_text": "mg"}


def test_collapsed_serving_header_is_not_an_ingredient() -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("ServingSizeOneCapsule", 30),
        _line("Turmeric Root Extract 500 mg", 70),
    ])
    assert draft["serving"]["size"]["value"] == "OneCapsule"
    assert [r["display_name"]["value"] for r in draft["ingredient_rows"]] == ["Turmeric Root Extract"]


def test_dense_touching_rows_keep_separate_amounts_and_names() -> None:
    draft = _extract([
        _line("Alpha Lipoic Acid", 40, width=120, height=14),
        _line("1 mg", 39, left=260, width=40, height=15),
        _line("Quercetin", 51, width=120, height=14),
        _line("2 mg", 50, left=260, width=40, height=15),
    ])
    assert [(r["display_name"]["value"], r["amount"]["value"]["value"])
            for r in draft["ingredient_rows"]] == [("Alpha Lipoic Acid", 1), ("Quercetin", 2)]


def test_amount_and_percent_without_name_remain_an_unidentified_partial_row() -> None:
    draft = _extract([
        _line("0.5 mg", 40, left=260, width=40),
        _line("25%", 40, left=310, width=40),
    ])
    row = draft["ingredient_rows"][0]
    assert row["display_name"]["status"] == "unreadable"
    assert row["display_name"]["value"] is None
    assert row["amount"]["value"]["value"] == 0.5
    assert row["percent_dv"]["value"] == 25
    assert row["status"] == "partial"


def test_facts_column_excludes_tall_marketing_and_footer() -> None:
    draft = _extract([
        _line("Marketing 900 mg", 0, left=10, width=300, height=180),
        _line("SupplementFacts", 20, left=500, width=260),
        _line("Vitamin C", 60, left=500, width=120),
        _line("500 mg", 60, left=800, width=70),
        _line("*Daily Value not established.", 100, left=500),
        _line("OtherIngredients: cellulose", 130, left=500),
        _line("Warning: contains 50 mg", 160, left=500),
    ])
    assert [r["display_name"]["value"] for r in draft["ingredient_rows"]] == ["Vitamin C"]
    assert draft["ingredient_rows"][0]["amount"]["value"]["value"] == 500


def test_undeclared_marketing_amount_is_not_a_facts_panel() -> None:
    draft = _extract([_line("Super power 500 mg", 40)],
                     bundle=_bundle(_photo(categories=())))
    assert draft["abstained"] is True


def test_two_facts_headings_abstain_instead_of_combining_editions() -> None:
    draft = _extract([
        _line("Supplement Facts", 0), _line("Vitamin C 500 mg", 40),
        _line("Supplement Facts", 150), _line("Vitamin C 100 mg", 190),
    ])
    assert draft["abstained"] is True


def test_recognized_facts_panel_does_not_depend_on_user_slot_and_keeps_source() -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Vitamin C", 40, width=120),
        _line("500 mg", 40, left=300, width=70),
    ], bundle=_bundle(_photo(categories=("front_identity",))))
    row = draft["ingredient_rows"][0]
    assert row["display_name"]["value"] == "Vitamin C"
    assert row["amount"]["sources"][0]["photo_id"] == _PHOTO
    assert row["amount"]["sources"][0]["input_id"] == "i1"


def test_wrapped_name_and_amount_stay_one_row_when_boxes_overlap_as_a_chain() -> None:
    draft = _extract([
        _line("Bifidobacterium longum", 40, left=10, width=220, height=42),
        _line("subsp. longum 35624", 79, left=10, width=220, height=55),
        _line("10 mg", 80, left=300, width=70, height=51),
    ])

    rows = draft["ingredient_rows"]
    assert len(rows) == 1
    assert rows[0]["display_name"]["value"] == "Bifidobacterium longum subsp. longum 35624"
    assert rows[0]["amount"]["value"] == {"value": 10.0, "unit_text": "mg"}


def test_collapsed_serving_headings_are_still_read() -> None:
    draft = _extract([
        _line("ServingSize:1Capsule", 0),
        _line("ServingsPerContainer:28", 30),
        _line("Vitamin C", 80, left=10, width=120),
        _line("500 mg", 80, left=300, width=70),
    ])

    assert draft["serving"]["size"]["value"] == "1Capsule"
    assert draft["serving"]["servings_per_container"]["value"] == "28"


def test_overlapping_amount_bridges_wrapped_name_lines() -> None:
    draft = _extract([
        _line("Chaste Tree", 40, left=10, width=160, height=47),
        _line("42 mg", 85, left=300, width=70, height=51),
        _line("berry extract", 92, left=10, width=140, height=37),
    ])

    rows = draft["ingredient_rows"]
    assert len(rows) == 1
    assert rows[0]["display_name"]["value"] == "Chaste Tree berry extract"
    assert rows[0]["amount"]["value"] == {"value": 42.0, "unit_text": "mg"}


def test_disclosure_and_footnotes_are_not_emitted_as_ingredients() -> None:
    draft = _extract([
        _line("Vitamin C", 40, left=10, width=120),
        _line("500 mg", 40, left=300, width=70),
        _line("+ Provides 6 billion CFU", 80, left=10, width=220),
        _line("cells until the best by date", 120, left=10, width=220),
        _line("Other ingredients: cellulose", 160, left=10, width=220),
        _line("magnesium stearate", 200, left=10, width=220),
    ])

    rows = draft["ingredient_rows"]
    assert [row["display_name"]["value"] for row in rows] == ["Vitamin C"]


def test_the_printed_unit_crosses_exactly_as_printed() -> None:
    draft = _extract([
        _line("Folate", 40, left=10, width=100),
        _line("400 mcg DFE", 40, left=300, width=110),
        _line("Probiotic Blend", 70, left=10, width=140),
        _line("10 billion CFU", 70, left=300, width=120),
    ])

    units = [row["amount"]["value"]["unit_text"] for row in draft["ingredient_rows"]]
    assert units == ["mcg DFE", "billion CFU"]


def test_indentation_nests_a_blend_child_under_its_header() -> None:
    draft = _extract([
        _line("Proprietary Blend", 40, left=10, width=160),
        _line("250 mg", 40, left=300, width=70),
        _line("Ginger Root", 70, left=34, width=120),
        _line("Turmeric", 100, left=34, width=110),
    ])

    rows = draft["ingredient_rows"]
    # Indentation is the only structural signal a panel gives, and it is
    # geometry — which is exactly what this adapter can see and a flat text
    # reader cannot.
    assert rows[0]["is_blend_header"] is True
    assert [row["parent_index"] for row in rows] == [None, 0, 0]


def test_a_sibling_at_equal_indent_is_not_a_child() -> None:
    draft = _extract([
        _line("Vitamin C", 40, left=10, width=120),
        _line("500 mg", 40, left=300, width=70),
        _line("Vitamin D", 70, left=10, width=120),
        _line("25 mcg", 70, left=300, width=70),
    ])

    assert [row["parent_index"] for row in draft["ingredient_rows"]] == [None, None]


def test_a_row_with_no_amount_is_kept_and_marked_partial() -> None:
    draft = _extract([
        _line("Proprietary Blend", 40, left=10, width=160),
        _line("Ginger Root", 70, left=34, width=120),
    ])

    rows = draft["ingredient_rows"]
    # A panel with a row silently dropped is a different label from the one
    # photographed.
    assert len(rows) == 2
    assert rows[1]["amount"]["status"] == "not_present"
    assert rows[1]["amount"]["value"] is None


def test_a_percent_daily_value_is_read_separately_from_the_amount() -> None:
    draft = _extract([
        _line("Vitamin C", 40, left=10, width=120),
        _line("500 mg 556%", 40, left=300, width=140),
    ])

    row = draft["ingredient_rows"][0]
    assert row["amount"]["value"] == {"value": 500.0, "unit_text": "mg"}
    assert row["percent_dv"]["value"] == 556.0


def test_panel_headings_are_not_ingredients() -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Amount Per Serving", 20),
        _line("% Daily Value", 20, left=300, width=110),
        _line("Vitamin C", 60, left=10, width=120),
        _line("500 mg", 60, left=300, width=70),
    ])

    names = [row["display_name"]["value"] for row in draft["ingredient_rows"]]
    assert names == ["Vitamin C"]


def test_every_reading_cites_the_line_it_came_from() -> None:
    draft = _extract([
        _line("Vitamin C", 40, left=10, width=120),
        _line("500 mg", 40, left=300, width=70),
    ])

    row = draft["ingredient_rows"][0]
    for reading in (row["display_name"], row["amount"]):
        assert reading["sources"], "a read field must name the image it came from"
        assert reading["sources"][0]["photo_id"] == _PHOTO
        assert reading["sources"][0]["supporting_text"]


def test_the_adapter_reports_no_confidence_of_its_own() -> None:
    draft = _extract([
        _line("Vitamin C", 40, left=10, width=120),
        _line("500 mg", 40, left=300, width=70),
    ])

    # A self-reported number is precisely what must never authorize an
    # approval, so this reader declines to invent one.
    assert draft["overall_confidence"] is None
    assert draft["ingredient_rows"][0]["amount"]["confidence"] is None


def test_an_unreadable_panel_abstains_rather_than_returning_an_empty_label() -> None:
    draft = _extract([_line("Supplement Facts", 0)])

    assert draft["abstained"] is True
    assert "no ingredient rows" in draft["abstain_reason"]


def test_the_rules_version_is_pinned_like_a_prompt() -> None:
    first = OcrLabelAdapter(_Reader({})).prompt_sha256
    second = OcrLabelAdapter(_Reader({})).prompt_sha256

    # A benchmarked configuration must not silently become a different one.
    assert first == second and len(first) == 64


def test_a_configuration_for_another_provider_is_refused() -> None:
    with pytest.raises(ExtractionError) as raised:
        _extract([_line("Vitamin C", 40)], config=_config(provider="ollama"))

    assert raised.value.code == "provider_unavailable"


def test_an_engine_failure_becomes_a_typed_failure() -> None:
    class Broken:
        def read(self, data, *, photo_id, input_id):
            raise RuntimeError("engine exploded")

    with pytest.raises(ExtractionError) as raised:
        OcrLabelAdapter(Broken()).extract(_bundle(), _config())

    # A provider boundary must never let an SDK exception escape the worker.
    assert raised.value.code == "model_failure"
