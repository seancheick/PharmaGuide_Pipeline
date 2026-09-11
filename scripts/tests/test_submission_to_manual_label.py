"""Draft to approval-schema skeleton: nothing invented, nothing dropped.

A draft is a reading of photographs. The reviewer's job is to confirm it, and
a confirmation pass is exactly what fails to catch a plausible invented value —
so anything the model could not read must arrive as an explicit gap, not as a
guess and not as silence.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction.to_manual_label import (  # noqa: E402
    to_manual_label,
)


def _f(value, status="read"):
    return {"value": value, "status": status, "confidence": None, "sources": []}


def _draft(**overrides):
    draft = {
        "identity": {"brand": _f("Acme"), "product_name": _f("Multi")},
        "serving": {"size": _f("2 capsules"), "servings_per_container": _f("30")},
        "ingredient_rows": [],
        "other_ingredients": {"text": _f("Rice flour"), "disclosure_hint": "present"},
        "statements": [],
    }
    draft.update(overrides)
    return draft


def _row(name, **overrides):
    row = {
        "display_name": _f(name), "amount": None, "percent_dv": None,
        "form_text": None, "parent_index": None, "is_blend_header": False,
        "status": "read",
    }
    row.update(overrides)
    return row


def test_printed_units_cross_over_exactly_as_printed() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Folate", amount=_f({"value": 400, "unit_text": "mcg DFE"})),
        _row("Probiotic blend", amount=_f({"value": 10, "unit_text": "billion CFU"})),
    ]))

    units = [row["quantity"][0]["unit"] for row in skeleton.payload["ingredientRows"]]
    # Normalising here would destroy the only record of what the label said.
    assert units == ["mcg DFE", "billion CFU"]


def test_blend_children_are_nested_under_their_header() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Proprietary Blend", is_blend_header=True),
        _row("Ginger", parent_index=0, amount=_f({"value": 50, "unit_text": "mg"})),
        _row("Turmeric", parent_index=0),
    ]))

    rows = skeleton.payload["ingredientRows"]
    assert len(rows) == 1
    assert [child["name"] for child in rows[0]["nestedRows"]] == ["Ginger", "Turmeric"]


def test_a_blend_header_is_not_reported_as_a_missing_amount() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Proprietary Blend", is_blend_header=True),
    ]))

    # A header prints no weight of its own; that is the label, not a gap.
    assert skeleton.unresolved == [
        entry for entry in skeleton.unresolved if entry["path"] != "ingredientRows[0].quantity"
    ]


def test_an_unreadable_row_is_kept_and_named_rather_than_dropped() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Vitamin C", amount=_f({"value": 500, "unit_text": "mg"})),
        _row(None, display_name=_f(None, "unreadable"), amount=_f(None, "unreadable")),
    ]))

    # A panel with a row silently removed is a different label from the one
    # photographed, and the reviewer has to be able to see the row was there.
    assert len(skeleton.payload["ingredientRows"]) == 2
    paths = {entry["path"] for entry in skeleton.unresolved}
    assert "ingredientRows[1].name" in paths
    assert "ingredientRows[1].quantity" in paths


def test_a_percent_dv_only_row_invents_no_amount() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Calcium", amount=_f(None, "not_present"), percent_dv=_f(20)),
    ]))

    assert skeleton.payload["ingredientRows"][0]["quantity"] == []
    reported = [e for e in skeleton.unresolved if e["path"] == "ingredientRows[0].quantity"]
    # manual_label_v1 has no field for the percentage, so the reviewer is told
    # what was printed instead of the value being quietly discarded.
    assert reported and reported[0]["printed"] == "%DV 20"


@pytest.mark.parametrize('dv', [None, 13])
@pytest.mark.parametrize('header', [False, True])
def test_incomplete_amount_keeps_printed_range_for_reviewer(dv, header):
    amount = _f({'value': None, 'unit_text': 'IU'}, 'partial')
    amount['sources'] = [{'supporting_text': 'Vitamin A 667 - 1,042 IU 13-21%'}]
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row('Vitamin A', amount=amount, percent_dv=_f(dv) if dv else None,
             is_blend_header=header),
    ]))
    row = skeleton.payload['ingredientRows'][0]
    assert row['quantity'] == []
    assert row['forms'] == []
    gap = next(e for e in skeleton.unresolved if e['path'] == 'ingredientRows[0].quantity')
    assert gap['printed'] == 'Vitamin A 667 - 1,042 IU 13-21%'


def test_the_serving_phrase_is_never_parsed_into_numbers() -> None:
    skeleton = to_manual_label(_draft())

    assert "servingSizes" not in skeleton.payload
    entry = next(e for e in skeleton.unresolved if e["path"] == "servingSizes")
    assert entry["printed"] == "2 capsules"


def test_an_unread_brand_is_absent_rather_than_empty() -> None:
    skeleton = to_manual_label(_draft(
        identity={"brand": _f(None, "unreadable"), "product_name": _f("Multi")},
    ))

    assert "brandName" not in skeleton.payload
    assert any(e["path"] == "brandName" for e in skeleton.unresolved)


def test_the_facts_panel_disclosure_uses_the_catalog_vocabulary() -> None:
    skeleton = to_manual_label(_draft(
        other_ingredients={"text": _f(None, "not_present"),
                           "disclosure_hint": "on_facts_panel"},
    ))

    assert skeleton.payload["otherIngredientsDisclosure"] == "included_on_facts_panel"
    assert "otherIngredients" not in skeleton.payload


def test_a_forward_parent_reference_is_reported_not_obeyed() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Child", parent_index=5),
    ]))

    # No printed panel nests a row under one that comes later.
    assert len(skeleton.payload["ingredientRows"]) == 1
    assert any(e["path"] == "ingredientRows[0].nestedRows" for e in skeleton.unresolved)


def test_the_skeleton_is_deliberately_not_approvable_on_its_own() -> None:
    from product_submission_import import (
        SubmissionImportError,
        _validate_label_payload,
    )

    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Vitamin C", amount=_f({"value": 500, "unit_text": "mg"})),
    ]))

    # The strict validator runs at approval, never here. A skeleton that
    # satisfied it would mean this module had filled in a human's judgement.
    with pytest.raises(SubmissionImportError):
        _validate_label_payload(skeleton.payload)
    assert skeleton.unresolved


def test_a_structured_serving_amount_crosses_but_the_phrase_never_does() -> None:
    structured = to_manual_label(_draft(serving={
        "size": _f("2 capsules"),
        "servings_per_container": _f("30"),
        "amount": _f({"value": 2, "unit_text": "capsule"}),
    }))
    phrase_only = to_manual_label(_draft(serving={
        "size": _f("2 capsules"), "servings_per_container": _f("30"),
        "amount": None,
    }))

    # The draft carries both. Copying the structured amount is transcription;
    # parsing the phrase would be a reading decision about the photograph.
    assert structured.payload["servingSizes"] == [
        {"minQuantity": 2.0, "maxQuantity": 2.0, "unit": "capsule", "order": 1}
    ]
    assert "servingSizes" not in phrase_only.payload
    assert any(e["path"] == "servingSizes" for e in phrase_only.unresolved)


def test_a_printed_percent_dv_is_kept_in_the_row_notes() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Calcium", amount=_f(None, "not_present"), percent_dv=_f(20)),
    ]))

    row = skeleton.payload["ingredientRows"][0]
    # notes is a real field on an ingredient row, so the printed value survives
    # in the payload as well as being named as unrecordable as a quantity.
    assert row["notes"] == "Printed %DV: 20"
    assert row["quantity"] == []
    assert any(e["path"] == "ingredientRows[0].quantity" for e in skeleton.unresolved)


def test_servings_per_container_and_disclosure_cross_intact() -> None:
    skeleton = to_manual_label(_draft(
        serving={"size": _f("2 capsules"),
                 "servings_per_container": _f("60"),
                 "amount": _f({"value": 2, "unit_text": "capsules"})},
        other_ingredients={"text": _f("Vegetable cellulose"),
                           "disclosure_hint": "present"},
    ))

    # Relocated from the console suite when the browser mapper was deleted:
    # the behaviour is the mapper's, so the test belongs beside it.
    assert skeleton.payload["servingsPerContainer"] == "60"
    assert skeleton.payload["servingSizes"][0]["unit"] == "capsules"
    assert skeleton.payload["servingSizes"][0]["minQuantity"] == 2
    assert skeleton.payload["otherIngredientsDisclosure"] == "present"
    assert skeleton.payload["otherIngredients"] == "Vegetable cellulose"


def test_a_nested_row_keeps_its_own_form() -> None:
    skeleton = to_manual_label(_draft(ingredient_rows=[
        _row("Proprietary Blend", is_blend_header=True),
        _row("Magnesium", parent_index=0, form_text=_f("glycinate"),
             amount=_f({"value": 200, "unit_text": "mg"})),
    ]))

    child = skeleton.payload["ingredientRows"][0]["nestedRows"][0]
    assert child["forms"] == [{"name": "glycinate"}]
    assert child["quantity"] == [{"quantity": 200.0, "unit": "mg"}]
