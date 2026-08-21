from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_raw_to_final import (  # noqa: E402
    ProductRecord,
    _check_raw_actives_present_in_blob,
    audit_product,
)


def _record() -> ProductRecord:
    return ProductRecord(
        dsld_id="fixture",
        archetype=None,
        product_name="Fixture",
        upc=None,
    )


def _cleaned() -> dict:
    return {
        "activeIngredients": [
            {
                "name": "Magnesium Glycinate",
                "raw_source_path": "ingredientRows[0]",
            }
        ]
    }


def test_aggregate_drop_reason_cannot_amnesty_a_missing_active() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "inactive_ingredients": [],
        "display_ingredients": [],
        "ingredients_dropped_reasons": ["DROPPED_AS_INACTIVE"],
    }

    _check_raw_actives_present_in_blob(record, _cleaned(), blob)

    assert [finding.code for finding in record.findings] == [
        "RAW_ACTIVE_MISSING_FROM_BLOB"
    ]


def test_display_ledger_destination_reconciles_a_non_scoring_source_row() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "inactive_ingredients": [],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "Magnesium Glycinate",
                "display_disposition": "label_context",
            }
        ],
        "ingredients_dropped_reasons": [],
    }

    _check_raw_actives_present_in_blob(record, _cleaned(), blob)

    assert record.findings == []


def test_explicit_gate_quarantine_is_a_reconciled_final_destination(
    tmp_path: Path,
) -> None:
    record = audit_product(
        dsld_id="quarantined",
        archetype="fixture",
        blob_dir=tmp_path / "detail_blobs",
        products_root=None,
        db_path=None,
        stage_index=None,
        excluded_by_gate={
            "quarantined": ["review_queue: assessment readiness incomplete"]
        },
    )

    assert record.findings == []
    assert record.stages["final_destination"] == {
        "kind": "quarantined",
        "reasons": ["review_queue: assessment readiness incomplete"],
    }
