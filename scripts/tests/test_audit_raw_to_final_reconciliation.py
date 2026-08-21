from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_raw_to_final import (  # noqa: E402
    ProductRecord,
    _check_blend_children,
    _check_branded_tokens,
    _check_display_label_collapse,
    _check_plant_part,
    _check_raw_actives_present_in_blob,
    _check_standardization,
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


def test_label_fidelity_checks_use_the_app_display_ledger() -> None:
    record = _record()
    blob = {
        # The legacy scoring analysis canonicalizes the title. The app renders
        # the canonical display ledger whenever it is present.
        "ingredients": [
            {
                "name": "KSM-66",
                "raw_source_text": "KSM-66",
                "display_label": "Ashwagandha",
                "standard_name": "Ashwagandha",
                "forms": [{"name": "Ashwagandha Root Extract"}],
            }
        ],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "KSM-66",
                "label_display_name": "KSM-66",
                "label_display_form": "Ashwagandha Root Extract",
                "display_type": "mapped_ingredient",
                "score_included": True,
                "analysis": {
                    "canonical_id": "ashwagandha",
                    "display_label": "Ashwagandha",
                    "standard_name": "Ashwagandha",
                    "form_note": "KSM-66 is made from ashwagandha root.",
                },
            }
        ],
    }

    _check_display_label_collapse(record, blob)
    _check_branded_tokens(record, blob)
    _check_plant_part(record, blob)

    assert record.findings == []


def test_label_fidelity_still_flags_loss_from_the_app_display_surface() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "KSM-66 Ashwagandha root extract",
                "label_display_name": "Ashwagandha",
                "display_type": "mapped_ingredient",
                "score_included": True,
                "analysis": {
                    "canonical_id": "ashwagandha",
                    "display_label": "Ashwagandha",
                    "standard_name": "Ashwagandha",
                },
            }
        ],
    }

    _check_display_label_collapse(record, blob)
    _check_branded_tokens(record, blob)
    _check_plant_part(record, blob)

    assert {finding.code for finding in record.findings} == {
        "DISPLAY_LABEL_COLLAPSES_TO_CANONICAL",
        "BRANDED_TOKEN_DROPPED",
        "PLANT_PART_DROPPED",
    }


def test_display_collapse_allows_an_explicit_reciprocal_source_correction() -> None:
    record = _record()
    blob = {
        "ingredients": [],
        "display_ingredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "raw_source_text": "Magnesium",
                "label_display_name": "Magtein Magnesium L-Threonate",
                "display_type": "mapped_ingredient",
                "canonical_id": "magnesium",
                "mapped_to": {
                    "raw_source_path": "ingredientRows[0].nestedRows[0]",
                },
                "analysis": {
                    "display_label": "Magtein Magnesium L-Threonate",
                    "standard_name": "Magnesium",
                },
            },
            {
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "raw_source_text": "Magtein Magnesium L-Threonate",
                "label_display_name": "Magnesium",
                "display_type": "mapped_ingredient",
                "canonical_id": "magnesium",
                "mapped_to": {"raw_source_path": "ingredientRows[0]"},
                "analysis": {
                    "display_label": "Magnesium",
                    "standard_name": "Magnesium",
                },
            },
        ],
    }

    _check_display_label_collapse(record, blob)

    assert record.findings == []


def test_standardization_audit_uses_the_exporters_exact_claim_contract() -> None:
    record = _record()
    blob = {
        "ingredients": [
            {
                "name": "Saw Palmetto",
                "notes": (
                    "Generic listing without specifying the extraction method "
                    "or standardization level. Could be standardized to "
                    "85-95% fatty acids depending on the source."
                ),
                "standardization_note": None,
            },
            {
                "name": "Cranberry",
                "notes": "Standardized to 25% A-type proanthocyanidins.",
                "standardization_note": None,
            },
            {
                "name": "Ashwagandha",
                "notes": "Root extract standardized to 5% withanolides.",
                "standardization_note": None,
            },
        ]
    }

    _check_standardization(record, blob)

    assert [(finding.code, finding.ingredient) for finding in record.findings] == [
        ("STANDARDIZATION_NOTE_DROPPED", "Ashwagandha")
    ]


def test_partial_blend_allows_named_children_without_individual_amounts() -> None:
    record = _record()
    blob = {
        "proprietary_blend_detail": {
            "blends": [
                {
                    "name": "Daily Botanical Blend",
                    "disclosure_level": "partial",
                    "total_weight": 500,
                    "unit": "mg",
                    "hidden_count": 2,
                    "child_ingredients": [
                        {"name": "Ashwagandha", "amount": None, "unit": ""},
                        {"name": "Rhodiola", "amount": None, "unit": ""},
                    ],
                }
            ]
        }
    }

    _check_blend_children(record, blob)

    assert record.findings == []


def test_full_blend_requires_every_child_amount() -> None:
    record = _record()
    blob = {
        "proprietary_blend_detail": {
            "blends": [
                {
                    "name": "Fully Disclosed Blend",
                    "disclosure_level": "full",
                    "total_weight": 500,
                    "unit": "mg",
                    "child_ingredients": [
                        {"name": "Ashwagandha", "amount": 300, "unit": "mg"},
                        {"name": "Rhodiola", "amount": None, "unit": ""},
                    ],
                }
            ]
        }
    }

    _check_blend_children(record, blob)

    assert [finding.code for finding in record.findings] == [
        "BLEND_CHILD_WITHOUT_DOSE_DISCLOSURE"
    ]
