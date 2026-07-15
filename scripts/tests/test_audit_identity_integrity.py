from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audit_identity_integrity import (  # noqa: E402
    audit_enriched_outputs,
    audit_product,
)
from identity_integrity import is_identity_scoreable  # noqa: E402
from scoring_v4.router import VALID_CLASSES  # noqa: E402
from stage_manifest import write_stage_manifest  # noqa: E402


def _active_row(disposition="clean", supplied="magnesium", final="magnesium", **overrides):
    scoreable = is_identity_scoreable(disposition) and final is not None
    row = {
        "raw_source_path": "activeIngredients[0]",
        "source_label_key": "label:magnesium:magnesium:200:mg",
        "source_label_name": "Magnesium",
        "label_display_name": "Magnesium",
        "label_display_form": "as Glycinate",
        "canonical_id_before": supplied,
        "canonical_id_after": final,
        "canonical_id": final,
        "identity_disposition": disposition,
        "scoreable_identity": scoreable,
        "identity_resolution_rationale": "test rationale",
    }
    row.update(overrides)
    return row


def _product(rows, product_id="TEST"):
    return {"dsld_id": product_id, "ingredient_quality_data": {"ingredients": rows}}


def _force(route):
    return lambda product: route


def test_audit_emits_one_disposition_record_per_active_row():
    records = audit_product(
        _product([_active_row(), _active_row(supplied="dha", final="dha")]),
        classify=_force("generic"),
    )
    assert len(records) == 2
    assert all(not r.failed for r in records)
    assert [r.disposition for r in records] == ["clean", "clean"]


def test_audit_covers_every_scoring_route_module_agnostically():
    # The coverage inventory is VALID_CLASSES, not a hand-kept list: every route,
    # including the generic fallback, must receive an audit disposition per row.
    for route in VALID_CLASSES:
        records = audit_product(_product([_active_row()]), classify=_force(route))
        assert len(records) == 1, route
        assert records[0].route == route
        assert not records[0].failed, route


def test_audit_fails_when_a_routed_row_lacks_a_disposition():
    for route in VALID_CLASSES:
        row = _active_row()
        del row["identity_disposition"]
        records = audit_product(_product([row]), classify=_force(route))
        assert records[0].failed, route
        assert records[0].violation.startswith("missing_or_invalid_disposition"), route


def test_audit_fails_on_unresolved_identity_conflict():
    records = audit_product(
        _product([_active_row(disposition="identity_conflict", final=None)]),
        classify=_force("omega"),
    )
    assert records[0].failed
    assert records[0].violation == "unresolved_identity_conflict"


def test_audit_fails_on_missing_display_label():
    records = audit_product(
        _product([_active_row(disposition="missing_display_label", final=None)]),
        classify=_force("generic"),
    )
    assert records[0].failed
    assert records[0].violation == "missing_display_label"


def test_audit_fails_on_canonical_mismatch_after_repair():
    # Repaired to epa, but the authoritative canonical_id still says dha.
    row = _active_row(disposition="repaired", supplied="dha", final="epa")
    row["canonical_id"] = "dha"
    records = audit_product(_product([row]), classify=_force("omega"))
    assert records[0].failed
    assert records[0].violation.startswith("canonical_mismatch_after_repair")


def test_audit_passes_clean_repaired_and_taxonomy_only_rows():
    rows = [
        _active_row(disposition="clean"),
        _active_row(disposition="repaired", supplied="dha", final="epa"),
        _active_row(disposition="taxonomy_only", supplied="ashwagandha", final="ashwagandha"),
        # Intentionally non-scorable taxonomy_only: no inferred canonical.
        _active_row(disposition="taxonomy_only", supplied=None, final=None),
    ]
    records = audit_product(_product(rows), classify=_force("generic"))
    assert [r.failed for r in records] == [False, False, False, False]


def test_audit_over_absent_products_dir_yields_no_records():
    # An auto-skipped release whose old products directory is absent must not
    # fail the gate just because there is nothing to scan.
    records = audit_enriched_outputs(products_dir=REPO_ROOT / "does_not_exist_dir")
    assert records == []


def test_audit_reads_only_manifest_owned_enriched_batches(tmp_path):
    stage_dir = tmp_path / "output_Test_enriched" / "enriched"
    stage_dir.mkdir(parents=True)
    batch = stage_dir / "enriched_batch_1.json"
    batch.write_text(json.dumps([_product([_active_row()])]), encoding="utf-8")
    write_stage_manifest(stage_dir, "enrich", [batch], run_id="identity-audit-run")

    records = audit_enriched_outputs(
        products_dir=tmp_path,
        classify=_force("generic"),
    )

    assert len(records) == 1
    assert records[0].product_id == "TEST"


def test_audit_fails_when_an_active_row_has_no_identity_audit_row():
    product = {
        "dsld_id": "MISSING-IQD",
        "activeIngredients": [
            {
                "name": "Magnesium",
                "raw_source_text": "Magnesium",
                "raw_source_path": "activeIngredients[0]",
            }
        ],
        "ingredient_quality_data": {"ingredients": []},
    }

    records = audit_product(product, classify=_force("generic"))

    assert len(records) == 1
    assert records[0].failed
    assert records[0].violation == "missing_identity_audit_row"


def test_audit_requires_literal_label_identity_and_source_key_for_scorable_rows():
    missing_label = _active_row(source_label_name=None)
    missing_key = _active_row(source_label_key="")

    label_records = audit_product(_product([missing_label]), classify=_force("generic"))
    key_records = audit_product(_product([missing_key]), classify=_force("generic"))

    assert label_records[0].violation == "missing_literal_source_label"
    assert key_records[0].violation == "missing_source_label_key"
