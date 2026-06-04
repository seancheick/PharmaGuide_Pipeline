from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
API_AUDIT_ROOT = SCRIPTS_ROOT / "api_audit"
for path in (str(SCRIPTS_ROOT), str(API_AUDIT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_v4_botanical_materiality_shadow import build_rows, summarize  # noqa: E402


def _row(canonical: str, name: str, quantity: float, unit: str = "mg", **extra):
    row = {
        "canonical_id": canonical,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical}]",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": True,
    }
    row.update(extra)
    return row


def _product(name: str, rows: list[dict], *, dsld_id: str = "fixture"):
    return {
        "id": dsld_id,
        "dsld_id": dsld_id,
        "product_name": name,
        "primary_type": "general_supplement",
        "supplement_taxonomy": {"primary_type": "general_supplement"},
        "ingredient_quality_data": {"ingredients_scorable": rows},
    }


def test_shadow_audit_reports_threshold_revocation_for_borderline_botanical():
    product = _product(
        "Ashwagandha with Magnesium",
        [
            _row(
                "ashwagandha",
                "Ashwagandha Root Extract",
                300,
                raw_taxonomy={
                    "category": "botanical",
                    "forms": [{"name": "root extract", "category": "botanical"}],
                },
            ),
            _row("magnesium", "Magnesium", 400, raw_taxonomy={"category": "mineral"}),
        ],
        dsld_id="ashwagandha-magnesium",
    )

    rows = build_rows(
        [product],
        current_owner_threshold=0.5,
        current_blocker_threshold=0.5,
        candidate_owner_threshold=1.0,
        candidate_blocker_threshold=0.5,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["transition"] == "candidate_revokes_botanical_ownership"
    assert row["current_eligible"] is True
    assert row["candidate_eligible"] is False
    assert row["current_owner_type"] == "therapeutic_botanical"
    assert row["candidate_owner_type"] == "phytonutrient_support"


def test_shadow_audit_does_not_report_clearly_material_botanical():
    product = _product(
        "Turmeric Curcumin Extract",
        [
            _row(
                "turmeric",
                "Turmeric Root Extract",
                500,
                raw_taxonomy={
                    "category": "botanical",
                    "forms": [{"name": "root extract", "category": "botanical"}],
                },
            ),
            _row("zinc", "Zinc", 5, raw_taxonomy={"category": "mineral"}),
        ],
    )

    assert build_rows(
        [product],
        current_owner_threshold=0.5,
        current_blocker_threshold=0.5,
        candidate_owner_threshold=1.0,
        candidate_blocker_threshold=0.5,
    ) == []


def test_shadow_audit_summary_counts_transitions():
    rows = [
        {
            "transition": "candidate_revokes_botanical_ownership",
            "current_owner_type": "therapeutic_botanical",
            "candidate_owner_type": "phytonutrient_support",
            "current_owner_reason_code": "therapeutic_botanical_owner",
            "candidate_owner_reason_code": "material_nonbotanical_deliverable",
        }
    ]

    summary = summarize(
        rows,
        total_products=2,
        current_owner_threshold=0.5,
        current_blocker_threshold=0.5,
        candidate_owner_threshold=1.0,
        candidate_blocker_threshold=0.5,
        elapsed_seconds=0.2,
    )

    assert summary["changed_count"] == 1
    assert summary["transition_counts"] == {"candidate_revokes_botanical_ownership": 1}
    assert summary["ms_per_product"] == 100.0
