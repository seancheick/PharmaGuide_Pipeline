from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from row_ledger import (  # noqa: E402
    build_row_ledger,
    summarize_row_ledger,
    validate_row_ledger,
)


def test_row_ledger_reconciles_every_source_and_links_owned_components() -> None:
    source_rows = [
        {
            "raw_source_path": "ingredientRows[0]",
            "raw_source_text": "Magnesium",
            "source_section": "activeIngredients",
        },
        {
            "raw_source_path": "ingredientRows[0].nestedRows[0]",
            "raw_source_text": "Magnesium Glycinate",
            "source_section": "activeIngredients",
        },
        {
            "raw_source_path": "ingredientRows[0].forms[0]",
            "raw_source_text": "Bisglycinate",
            "source_section": "activeIngredients",
        },
        {
            "raw_source_path": "otheringredients.ingredients[0]",
            "raw_source_text": "Hypromellose",
            "source_section": "inactiveIngredients",
        },
    ]
    display_rows = [
        {
            "raw_source_path": "ingredientRows[0]",
            "raw_source_text": "Magnesium",
            "source_section": "activeIngredients",
            "display_type": "mapped_ingredient",
            "display_disposition": "scored",
            "score_included": True,
            "canonical_id": "magnesium",
        },
        {
            "raw_source_path": "ingredientRows[0].nestedRows[0]",
            "raw_source_text": "Magnesium Glycinate",
            "source_section": "activeIngredients",
            "display_type": "label_context",
            "display_disposition": "label_context",
            "score_included": False,
        },
        {
            "raw_source_path": "otheringredients.ingredients[0]",
            "raw_source_text": "Hypromellose",
            "source_section": "inactiveIngredients",
            "display_type": "inactive_ingredient",
            "display_disposition": "other_ingredient",
            "score_included": False,
        },
    ]
    omissions = [
        {
            "raw_source_path": "ingredientRows[0].forms[0]",
            "raw_source_text": "Bisglycinate",
            "omission_reason": "duplicate_source_line",
        }
    ]
    ingredients = [
        {
            "raw_source_path": "ingredientRows[0]",
            "canonical_id": "magnesium",
        }
    ]

    ledger = build_row_ledger(
        source_rows,
        display_rows,
        omissions,
        ingredients,
        [],
    )
    by_ref = {row["row_ref"]: row for row in ledger}

    assert len(ledger) == len(source_rows)
    assert by_ref["ingredientRows[0]"]["mapping_disposition"] == (
        "mapped_score_active"
    )
    assert by_ref["ingredientRows[0]"]["final_destination"] == "ingredients"
    assert by_ref["ingredientRows[0].nestedRows[0]"]["owner_row_ref"] == (
        "ingredientRows[0]"
    )
    assert by_ref["ingredientRows[0].nestedRows[0]"]["score_eligible"] is False
    assert by_ref["ingredientRows[0].forms[0]"]["mapping_disposition"] == (
        "owned_component"
    )
    assert by_ref["ingredientRows[0].forms[0]"]["final_destination"] == (
        "owner_row"
    )
    assert by_ref["otheringredients.ingredients[0]"]["mapping_disposition"] == (
        "source_inactive_row"
    )

    summary = summarize_row_ledger(ledger)
    assert summary["source_row_count"] == 4
    assert summary["score_eligible_count"] == 1
    assert summary["mapped_score_eligible_count"] == 1
    assert summary["mapped_coverage"] == 1.0
    assert validate_row_ledger(ledger, raw_actives_count=2) == []


def test_active_to_inactive_transition_has_a_distinct_disposition() -> None:
    source = [{
        "raw_source_path": "ingredientRows[0]",
        "raw_source_text": "Silicon Dioxide",
        "source_section": "activeIngredients",
    }]
    display = [{
        **source[0],
        "display_type": "inactive_ingredient",
        "display_disposition": "other_ingredient",
        "score_included": False,
    }]

    ledger = build_row_ledger(source, display, [], [], [])

    assert ledger[0]["source_role"] == "active_reclassified_inactive"
    assert ledger[0]["mapping_disposition"] == "active_reclassified_inactive"
    assert ledger[0]["reason_code"] == "ACTIVE_RECLASSIFIED_AS_INACTIVE"
    assert ledger[0]["final_destination"] == "inactive_ingredients"


def test_unresolved_score_eligible_row_is_measured_then_fails_strict_validation() -> None:
    source = [{
        "raw_source_path": "ingredientRows[0]",
        "raw_source_text": "Unknown Active",
        "source_section": "activeIngredients",
    }]
    display = [{
        **source[0],
        "display_type": "mapped_ingredient",
        "display_disposition": "scored",
        "score_included": True,
        "canonical_id": None,
    }]

    ledger = build_row_ledger(source, display, [], [], [])
    summary = summarize_row_ledger(ledger)
    issues = validate_row_ledger(ledger, raw_actives_count=1)

    assert ledger[0]["mapping_disposition"] == "unresolved_score_active"
    assert summary["mapped_coverage"] == 0.0
    assert any(issue["code"] == "UNRESOLVED_SCORE_ACTIVE" for issue in issues)


def test_duplicate_source_reference_is_never_silently_deduplicated() -> None:
    source = {
        "raw_source_path": "ingredientRows[0]",
        "raw_source_text": "Magnesium",
        "source_section": "activeIngredients",
    }

    issues = validate_row_ledger(
        [
            {
                "row_ref": "ingredientRows[0]",
                "source_label": "Magnesium",
                "source_section": "activeIngredients",
                "source_role": "score_active",
                "score_eligible": True,
                "mapping_disposition": "mapped_score_active",
                "reason_code": "MAPPED_CANONICAL_IDENTITY",
                "final_destination": "ingredients",
                "owner_row_ref": None,
                "canonical_id": "magnesium",
            },
            {
                "row_ref": source["raw_source_path"],
                "source_label": source["raw_source_text"],
                "source_section": source["source_section"],
                "source_role": "score_active",
                "score_eligible": True,
                "mapping_disposition": "mapped_score_active",
                "reason_code": "MAPPED_CANONICAL_IDENTITY",
                "final_destination": "ingredients",
                "owner_row_ref": None,
                "canonical_id": "magnesium",
            },
        ],
        raw_actives_count=1,
    )

    assert any(issue["code"] == "DUPLICATE_ROW_REF" for issue in issues)


def test_unexplained_non_active_source_row_fails_strict_validation() -> None:
    source = [{
        "raw_source_path": "labelRows[0]",
        "raw_source_text": "Unclassified label row",
        "source_section": "other",
    }]

    ledger = build_row_ledger(source, [], [], [], [])
    issues = validate_row_ledger(ledger, raw_actives_count=0)

    assert ledger[0]["mapping_disposition"] == "unresolved_source_row"
    assert any(issue["code"] == "UNRESOLVED_SOURCE_ROW" for issue in issues)
