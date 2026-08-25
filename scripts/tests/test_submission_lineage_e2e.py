"""Submission lineage must survive clean → enrich → label_record intact.

Defect A (2026-08-24): the import adapter writes
``label_record_metadata.source_record_id = <submission uuid>``, but the
cleaner's output literal dropped the field and the enricher only re-attached
``source_type`` + ``manual_product_provenance``. ``build_label_record_contract``
then resolved ``source_record_id`` to None for BOTH submission kinds (the
enricher stamps ``source_type='external_manual'``, which defeats the
catalog-source fallback), so ``mark_released_submissions_promoted`` raised
"does not carry submission lineage" and — under ``set -Eeuo pipefail`` —
aborted the entire release on the very first real submission.

These tests run the REAL cleaner and enricher classes over a materialized
label, then the real label_record contract, and finally the real promotion
verifier against a fixture catalog. The spoof test proves the fix is gated:
an ordinary catalog record carrying a forged ``label_record_metadata`` must
NOT acquire submission provenance.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
from label_record_contract import build_label_record_contract  # noqa: E402
from product_submission_import import (  # noqa: E402
    build_manual_label,
    mark_released_submissions_promoted,
    materialize_approved_submissions,
)

SUBMISSION_ID = "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11"
PRODUCT_ID = "PG_SUB_018F4C797C7E4C709D627FC3B9CE6A11"


def _canonical(payload: dict) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _payload() -> dict:
    return {
        "brandName": "Example Labs",
        "fullName": "Example Vitamin D3",
        "ingredientRows": [
            {
                "category": "vitamin",
                "forms": [{"name": "Cholecalciferol"}],
                "ingredientGroup": "Vitamin D",
                "name": "Vitamin D",
                "nestedRows": [],
                "quantity": [{"quantity": 25, "unit": "mcg"}],
            }
        ],
        "offMarket": 0,
        "physicalState": {"langualCode": "", "name": "Capsule"},
        "productType": {
            "langualCode": "",
            "name": "Single-ingredient Dietary Supplement",
        },
        "servingSizes": [
            {
                "maxDailyServings": 1,
                "maxQuantity": 1,
                "minDailyServings": 1,
                "minQuantity": 1,
                "unit": "Capsule(s)",
            }
        ],
    }


def _export_row() -> dict:
    canonical = _canonical(_payload())
    return {
        "approved_at": "2026-07-30T20:00:00Z",
        "approved_payload_canonical": canonical,
        "kind": "missing_product",
        "normalized_upc": "050428381397",
        "payload_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "reviewer_id": "3f276b64-0836-4bea-9453-1c8db4d1f8dd",
        "schema_version": "manual_label_v1",
        "submission_id": SUBMISSION_ID,
    }


def _enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )


def test_submission_lineage_survives_clean_enrich_and_label_record():
    label = build_manual_label(_export_row())
    assert label["label_record_metadata"]["source_record_id"] == SUBMISSION_ID

    cleaned = EnhancedDSLDNormalizer().normalize_product(label)
    assert cleaned.get("label_record_metadata", {}).get(
        "source_record_id"
    ) == SUBMISSION_ID, (
        "cleaner dropped submission lineage (defect A regression)"
    )

    enriched, _issues = _enricher().enrich_product(cleaned)
    assert enriched.get("label_record_metadata", {}).get(
        "source_record_id"
    ) == SUBMISSION_ID, (
        "enricher dropped submission lineage (defect A regression)"
    )

    # The blob stage sets dsld_id from the pipeline id before building the
    # label record; mirror that seam.
    enriched["dsld_id"] = str(enriched.get("id") or PRODUCT_ID)
    contract = build_label_record_contract(
        enriched, enriched.get("display_ingredients")
    )
    assert contract["source_record_id"] == SUBMISSION_ID
    assert contract["lineage_key"] == f"pharmaguide_submission:{SUBMISSION_ID}"


def test_promotion_verifier_accepts_the_pipeline_produced_label_record(
    tmp_path: Path,
):
    manual_dir = tmp_path / "manual"
    materialize_approved_submissions([_export_row()], output_dir=manual_dir)

    label = json.loads((manual_dir / f"{PRODUCT_ID}.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(label)
    enriched, _issues = _enricher().enrich_product(cleaned)
    enriched["dsld_id"] = str(enriched.get("id") or PRODUCT_ID)
    contract = build_label_record_contract(
        enriched, enriched.get("display_ingredients")
    )

    detail_bytes = json.dumps({"label_record": contract}).encode()
    detail_blobs = tmp_path / "detail_blobs"
    detail_blobs.mkdir()
    (detail_blobs / f"{PRODUCT_ID}.json").write_bytes(detail_bytes)

    catalog = tmp_path / "pharmaguide_core.db"
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "create table products_core "
            "(dsld_id text primary key, detail_blob_sha256 text)"
        )
        connection.execute(
            "create table export_manifest (key text, value text)"
        )
        connection.execute(
            "insert into products_core values (?, ?)",
            (PRODUCT_ID, hashlib.sha256(detail_bytes).hexdigest()),
        )
        connection.execute(
            "insert into export_manifest values "
            "('db_version', '2026.08.30.000000')"
        )

    calls: list[tuple[str, dict]] = []
    promoted = mark_released_submissions_promoted(
        output_dir=manual_dir,
        catalog_db=catalog,
        detail_blobs_dir=detail_blobs,
        rpc=lambda name, payload: calls.append((name, payload)) or True,
    )
    assert promoted == [SUBMISSION_ID]
    assert calls == [
        (
            "mark_product_submission_promoted",
            {
                "p_catalog_version": "2026.08.30.000000",
                "p_resolved_dsld_id": PRODUCT_ID,
                "p_submission_id": SUBMISSION_ID,
            },
        )
    ]


def test_catalog_records_cannot_spoof_submission_lineage():
    forged_uuid = "99999999-9999-4999-8999-999999999999"
    catalog_raw = {
        "id": 278454,
        "fullName": "Ordinary Catalog Product",
        "brandName": "Catalog Brand",
        "upcSku": "016000275447",
        "ingredientRows": [
            {
                "category": "vitamin",
                "forms": [],
                "ingredientGroup": "Vitamin C",
                "name": "Vitamin C",
                "nestedRows": [],
                "quantity": [{"quantity": 90, "unit": "mg"}],
            }
        ],
        "servingSizes": [
            {
                "maxDailyServings": 1,
                "maxQuantity": 1,
                "minDailyServings": 1,
                "minQuantity": 1,
                "unit": "Tablet(s)",
            }
        ],
        # The forgery: a catalog record claiming submission lineage.
        "label_record_metadata": {
            "source_record_id": forged_uuid,
            "lineage_key": f"pharmaguide_submission:{forged_uuid}",
        },
    }

    cleaned = EnhancedDSLDNormalizer().normalize_product(catalog_raw)
    assert "label_record_metadata" not in cleaned, (
        "cleaner must not pass lineage through for non-external_manual records"
    )

    enriched, _issues = _enricher().enrich_product(cleaned)
    enriched["dsld_id"] = str(enriched.get("id") or "278454")
    contract = build_label_record_contract(
        enriched, enriched.get("display_ingredients")
    )
    assert contract["source_record_id"] != forged_uuid
    assert contract["source_record_id"] == "278454"
