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


def _rows(draft):
    def amount(row):
        field = row.get("amount") or {}
        return (field.get("value") or {}).get("value") if field.get("status") == "read" else None
    return [((row["display_name"] or {}).get("value"), amount(row)) for row in draft["ingredient_rows"]]


def test_header_lines_do_not_swallow_the_first_rows() -> None:
    """Reproduced on DSLD 739 (Emergen-C), including its OCR quirks.

    Every box on a dense panel touches the next, so the header, the first
    four rows and Thiamin's dose chained into one band. Each line then went
    to its nearest dose, all of them to Thiamin's, and the resulting row
    began with "Supplement Facts" and was dropped whole — Vitamin C 1,000 mg,
    the product's headline ingredient, with it.
    """
    draft = _extract([
        _line("Supplement Facts", 58, left=23, width=190, height=12),
        _line("Serving Size 1 packet (8.3 g)", 76, left=23, width=135, height=12),
        _line("% DV", 89, left=306, width=25, height=11),
        _line("Amount Per Serving", 90, left=23, width=76, height=11),
        _line("Calories", 101, left=23, width=36, height=11),
        _line("20", 103, left=269, width=16, height=9),
        _line("2%", 112, left=305, width=26, height=11),
        _line("Total Carbohydrate", 113, left=24, width=79, height=11),
        _line("59", 113, left=267, width=19, height=11),
        _line("Vitamin C (as ascorbic acid) 1.0", 136, left=24, width=260, height=11),
        _line("1.667%", 137, left=299, width=32, height=11),
        _line("0.38mg", 147, left=250, width=33, height=11),
        _line("25%", 148, left=308, width=23, height=11),
        _line("Thiamin (as thiamine HCl)", 150, left=24, width=114, height=10),
        _line("0.43 mg", 158, left=248, width=36, height=11),
        _line("25%", 159, left=309, width=23, height=11),
        _line("Riboflavin", 160, left=23, width=60, height=11),
    ])
    rows = _rows(draft)
    names = [name or "" for name, _ in rows]
    assert names[0] == "Calories"
    assert "Total Carbohydrate" in names
    assert any(name.startswith("Vitamin C") for name in names)
    assert ("Thiamin (as thiamine HCl)", 0.38) in rows
    assert ("Riboflavin", 0.43) in rows
    assert not any(h in name for name in names
                   for h in ("Supplement Facts", "Serving Size", "Amount Per Serving"))


def test_a_percent_with_a_thousands_comma_is_read_whole() -> None:
    """"1,667%" was read as 667%, even when OCR got the comma right."""
    from submission_review.extraction.adapters.ocr_adapter import _parse_percent
    assert _parse_percent("1,667%")[0] == 1667.0
    assert _parse_percent("25%")[0] == 25.0


def test_an_ambiguous_thousands_reading_is_never_a_dose() -> None:
    """OCR turns "1,000 mg" into "1.000 mg", which read as 1 mg.

    Found in real drafts (DSLD 8718, 758, 746). On 98,377 printed doses only
    34 are a 1-999 value with exactly three decimals, against 5,746 written
    with a thousands comma, so the reading is refused rather than guessed.
    A person reads it; a thousandfold dose is the error gated at zero.
    """
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Vitamin C", 40, left=10, width=120),
        _line("1.000 mg", 40, left=300, width=70),
        _line("1.667%", 40, left=380, width=50),
    ])
    [row] = draft["ingredient_rows"]
    assert row["display_name"]["value"] == "Vitamin C"
    assert row["amount"]["status"] == "unreadable"
    assert row["amount"]["value"] is None
    assert (row["percent_dv"] or {}).get("value") is None


def test_unambiguous_decimals_and_thousands_are_still_read() -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Vitamin B12", 40, left=10, width=120),
        _line("0.025 mg", 40, left=300, width=70),
        _line("Folic Acid", 70, left=10, width=120),
        _line("12.5 mcg", 70, left=300, width=70),
        _line("Vitamin C", 100, left=10, width=120),
        _line("1,000 mg", 100, left=300, width=70),
    ])
    assert _rows(draft) == [("Vitamin B12", 0.025), ("Folic Acid", 12.5), ("Vitamin C", 1000.0)]



def test_a_number_beside_the_name_is_still_the_name() -> None:
    """Only a number standing apart in the dose column is a lost-unit dose."""
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Vitamin B", 40, left=10, width=90, height=18),
        _line("12", 40, left=102, width=18, height=18),
        _line("6 mcg", 40, left=300, width=70, height=18),
    ])
    assert _rows(draft) == [("Vitamin B 12", 6.0)]


def test_a_dose_whose_unit_was_lost_is_unreadable_not_absent() -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Total Carbohydrate", 40, left=10, width=120, height=18),
        _line("59", 40, left=300, width=30, height=18),
    ])
    [row] = draft["ingredient_rows"]
    assert row["display_name"]["value"] == "Total Carbohydrate"
    assert row["amount"]["status"] == "unreadable"


def test_a_number_with_no_name_is_an_unidentified_row_not_a_name() -> None:
    """Sugars on DSLD 739: OCR read "59" (for 5 g) and never the word.

    A number must not become an ingredient's name — the same rule that keeps
    a lone "25%" from naming a row. It is a printed row nobody could read.
    """
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Total Carbohydrate", 40, left=10, width=120, height=18),
        _line("5 g", 40, left=300, width=30, height=18),
        _line("59", 70, left=300, width=30, height=18),
        _line("Vitamin C", 100, left=10, width=120, height=18),
        _line("500 mg", 100, left=300, width=70, height=18),
    ])
    names = [(row["display_name"] or {}).get("value") for row in draft["ingredient_rows"]]
    assert "59" not in names
    unnamed = [row for row in draft["ingredient_rows"] if row["display_name"]["status"] == "unreadable"]
    assert len(unnamed) == 1 and unnamed[0]["amount"]["status"] == "unreadable"


def test_any_servings_per_line_is_a_heading() -> None:
    """Labels print "Servings Per Bottle", "Per Package", "Per Container"."""
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Servings Per Bottle 30", 20, left=10, width=200, height=18),
        _line("Vitamin C", 60, left=10, width=120, height=18),
        _line("500 mg", 60, left=300, width=70, height=18),
    ])
    assert _rows(draft) == [("Vitamin C", 500.0)]



def test_servings_per_bottle_is_read_as_servings_per_container() -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Servings Per Bottle 30", 20, left=10, width=200, height=18),
        _line("Vitamin C", 60, left=10, width=120, height=18),
        _line("500 mg", 60, left=300, width=70, height=18),
    ])
    assert draft["serving"]["servings_per_container"]["value"] == "30"



@pytest.mark.parametrize("heading", ["ServingsPerContainer100", "AmountPerTablet %DailyValue"])
def test_a_heading_with_its_spaces_lost_is_still_a_heading(heading) -> None:
    draft = _extract([
        _line("Supplement Facts", 0),
        _line(heading, 20, left=10, width=200, height=18),
        _line("Vitamin C", 60, left=10, width=120, height=18),
        _line("500 mg", 60, left=300, width=70, height=18),
    ])
    assert _rows(draft) == [("Vitamin C", 500.0)]


def test_a_second_column_name_never_takes_this_rows_dose() -> None:
    """Reproduced on DSLD 778, a Facts panel printed in two columns.

    The right-hand column's "Choline" sat in the same band as Riboflavin's
    name and dose. Joined, it read as "Choline ... Riboflavin" at Riboflavin's
    50 mg — a wrong dose for Choline, the error the benchmark gates at zero.
    A name that starts right of the row's dose column is another column's.
    """
    draft = _extract([
        # A heading as wide as 778's, so the panel's bounds admit both columns.
        _line("Supplement Facts", 0, left=100, width=1000),
        _line("Riboflavin (Vitamin B-2)", 40, left=100, width=210, height=18),
        _line("50mg", 40, left=540, width=67, height=18),
        _line("2941%", 40, left=630, width=70, height=18),
        _line("Choline (as Choline Bitartrate)", 41, left=730, width=260, height=18),
    ])
    assert _rows(draft) == [("Riboflavin (Vitamin B-2)", 50.0)]


def test_a_name_packed_into_its_own_dose_box_keeps_its_wrapped_line() -> None:
    """A box holding name and dose together does not mark a dose column."""
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Magnesium (as magnesium", 40, left=10, width=200, height=18),
        _line("bisglycinate) 200 mg", 52, left=10, width=260, height=18),
    ])
    [row] = draft["ingredient_rows"]
    assert row["display_name"]["value"].startswith("Magnesium (as magnesium")
    assert row["amount"]["value"]["value"] == 200.0


def test_the_rows_own_dose_box_wins_over_a_standardization_line() -> None:
    """DSLD 699: the previous ingredient's "(5% Hydrastine = 6.25 mg)" shared
    Echinacea's band, sat above its "25mg*", and was read as its dose because
    the parser took the first number it met. A box that is only a dose is the
    row's dose; a constituent in parentheses never is."""
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("(5% Hydrastine = 6.25 mg)", 30, left=20, width=200, height=14),
        _line("Echinacea angustifolia Root Extract", 44, left=10, width=260, height=14),
        _line("25mg*", 43, left=400, width=60, height=14),
    ])
    assert [amount for _, amount in _rows(draft)] == [25.0]


def test_a_misread_digit_glued_to_a_dose_is_unreadable_not_zero() -> None:
    """DSLD 745: "10mcg" came back as "T0mcg" and was read as 0 mcg."""
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Chromium (as chromium ascorbate)", 40, left=10, width=220, height=18),
        _line("T0mcg", 40, left=300, width=50, height=18),
        _line("8%", 40, left=380, width=30, height=18),
    ])
    [row] = draft["ingredient_rows"]
    assert row["amount"]["status"] == "unreadable"


def test_a_name_glued_to_its_dose_keeps_the_dose() -> None:
    """Only one or two letters stuck to a number read as a misread digit."""
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Chromium10mcg", 40, left=10, width=220, height=18),
    ])
    assert [amount for _, amount in _rows(draft)] == [10.0]


def test_servings_per_day_is_never_servings_per_container() -> None:
    """A daily count read as a container count is a wrong value on a gated
    field. Only package words name a container."""
    draft = _extract([
        _line("Supplement Facts", 0),
        _line("Servings Per Day 2", 20, left=10, width=200, height=18),
        _line("Vitamin C", 60, left=10, width=120, height=18),
        _line("500 mg", 60, left=300, width=70, height=18),
    ])
    assert draft["serving"]["servings_per_container"]["value"] is None
