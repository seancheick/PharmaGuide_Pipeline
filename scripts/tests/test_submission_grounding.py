"""Locating a reading in the photograph it claims to come from.

Every field in a draft cites an image and quotes the text it was read out of,
and until now nothing checked the quote. This is the check, and its whole worth
is that it works on any producer: a vision model's claims can be tested against
a reader that cannot hallucinate.

The two failure modes that matter are opposite. A verifier that misses an
invented dose is worse than none, because it lends false assurance. One that
reports honest readings as ungrounded is worse still, because a reviewer learns
to ignore it.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction.adapters.ocr_adapter import (  # noqa: E402
    OcrLine, OcrPage,
)
from submission_review.extraction.grounding import verify_grounding  # noqa: E402

_PHOTO = "11111111-1111-4111-8111-111111111111"


def _page(*texts: str) -> OcrPage:
    lines = tuple(
        OcrLine(text=text, left=10.0, top=20.0 * index,
                right=200.0, bottom=20.0 * index + 18.0)
        for index, text in enumerate(texts)
    )
    return OcrPage(photo_id=_PHOTO, input_id="i1", lines=lines)


def _field(value, supporting, status="read"):
    return {
        "value": value, "status": status, "confidence": None,
        "sources": [{"input_id": "i1", "photo_id": _PHOTO,
                     "supporting_text": supporting}],
    }


def _draft(rows):
    return {
        "identity": {"brand": _field("Northwind", "Northwind"),
                     "product_name": None, "barcode_digits_seen": None},
        "serving": {"size": None, "servings_per_container": None,
                    "basis_text": None, "amount": None},
        "ingredient_rows": rows,
        "other_ingredients": {"text": None, "disclosure_hint": "unknown"},
    }


def _row(name="Vitamin C", amount=None, percent=None):
    return {
        "display_name": _field(name, name),
        "amount": amount, "percent_dv": percent,
        "form_text": None, "parent_index": None,
        "is_blend_header": False, "status": "read",
    }


def test_an_honest_reading_is_fully_grounded() -> None:
    draft = _draft([_row(amount=_field({"value": 500.0, "unit_text": "mg"}, "500 mg"))])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "500 mg")])

    assert report.ungrounded == ()
    assert report.rate == 1.0


def test_an_invented_dose_is_caught_even_though_its_unit_is_printed() -> None:
    draft = _draft([_row(amount=_field({"value": 5000.0, "unit_text": "mg"}, "500 mg"))])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "500 mg")])

    # The unit is always printed somewhere, so requiring only that *something*
    # claimed was found lets any fabricated number through. The digits have to
    # be located on their own.
    assert [entry.path for entry in report.ungrounded] == ["ingredient_rows[0].amount"]


def test_an_invented_ingredient_name_is_caught() -> None:
    draft = _draft([_row(name="Vitamin Q")])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "500 mg")])

    assert [entry.path for entry in report.ungrounded] == ["ingredient_rows[0].display_name"]


def test_collapsed_spacing_does_not_read_as_a_fabrication() -> None:
    draft = _draft([_row(
        name="Proprietary Blend",
        amount=_field({"value": 400.0, "unit_text": "mcg DFE"}, "400 mcg DFE"),
    )])

    # Real OCR returns "400mcgDFE" for the same panel that yields "500 mg".
    # A verifier that flags this teaches reviewers to ignore it.
    report = verify_grounding(
        draft, [_page("Northwind", "ProprietaryBlend", "400mcgDFE")])

    assert report.ungrounded == ()


def test_thousands_separator_does_not_read_as_a_fabrication() -> None:
    draft = _draft([_row(
        amount=_field({"value": 5000.0, "unit_text": "mg"}, "5,000 mg"),
    )])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C", "5,000 mg")])

    assert report.ungrounded == ()


def test_source_input_must_belong_to_the_cited_photo() -> None:
    draft = _draft([_row()])
    draft["ingredient_rows"][0]["display_name"]["sources"][0]["input_id"] = "wrong-input"

    report = verify_grounding(draft, [_page("Vitamin C")])

    entry = next(item for item in report.fields if item.path == "ingredient_rows[0].display_name")
    assert not entry.grounded
    assert "input" in entry.reason


def test_a_field_citing_a_photograph_nobody_read_is_not_grounded() -> None:
    draft = _draft([_row()])
    other = OcrPage(photo_id="22222222-2222-4222-8222-222222222222",
                    input_id="i2", lines=())

    report = verify_grounding(draft, [other])

    assert all(not entry.grounded for entry in report.fields)
    assert any("not read" in entry.reason for entry in report.fields)


def test_a_reading_with_no_source_is_not_grounded() -> None:
    row = _row()
    row["display_name"]["sources"] = []

    report = verify_grounding(_draft([row]), [_page("Vitamin C")])

    assert any(entry.reason == "no source cited" for entry in report.ungrounded)


def test_unread_fields_are_not_checked_at_all() -> None:
    row = _row()
    row["display_name"] = {"value": None, "status": "unreadable",
                           "confidence": None, "sources": []}

    report = verify_grounding(_draft([row]), [_page("Northwind")])

    # Nothing was claimed, so there is nothing to locate; counting it as a
    # failure would punish the honest answer.
    assert "ingredient_rows[0].display_name" not in [e.path for e in report.fields]


def test_the_report_says_how_much_of_the_reading_is_supported() -> None:
    draft = _draft([_row(), _row(name="Vitamin Q")])

    report = verify_grounding(draft, [_page("Northwind", "Vitamin C")])

    assert report.checked == 3 and report.grounded == 2
    payload = report.as_payload()
    assert payload["schema_version"] == "grounding_report_v1"
    assert abs(payload["rate"] - 2 / 3) < 1e-9
