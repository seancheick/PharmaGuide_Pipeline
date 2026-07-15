"""Regression coverage for the release gate on emitted RDA/UL stamps."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from audit_rda_ul_reference_stamps import audit_emitted_stamps  # noqa: E402
from reference_data_contract import reference_stamp  # noqa: E402
from stage_manifest import write_stage_manifest  # noqa: E402


def _reference() -> dict:
    data = {
        "_metadata": {
            "reference_data_contract": {
                "reference_version": "test-reference-v1",
                "semantic_fingerprint": "placeholder",
            }
        },
        "nutrient_recommendations": [
            {
                "id": "vitamin_d",
                "standard_name": "Vitamin D",
                "unit": "mcg",
                "ul_status": "established",
                "ul_basis": "all_sources",
                "data": [{"group": "Adult", "age_range": "19+", "rda_ai": 15, "ul": 100}],
            }
        ],
    }
    data["_metadata"]["reference_data_contract"]["semantic_fingerprint"] = reference_stamp(
        data
    )["reference_data_fingerprint"]
    return data


def _write_batch(products_dir: Path, rows: list[dict]) -> None:
    batch_dir = products_dir / "output_Test_enriched" / "enriched"
    batch_dir.mkdir(parents=True)
    (batch_dir / "enriched_batch.json").write_text(json.dumps(rows))


def test_audit_accepts_current_emitted_stamps(tmp_path: Path) -> None:
    reference = _reference()
    reference_path = tmp_path / "rda.json"
    reference_path.write_text(json.dumps(reference))
    _write_batch(
        tmp_path / "products",
        [
            {"id": "current", "rda_ul_data": reference_stamp(reference)},
            {"id": "no-rda"},
        ],
    )

    checked, failures = audit_emitted_stamps(
        products_dir=tmp_path / "products", reference_path=reference_path
    )

    assert checked == 1
    assert failures == []


def test_audit_ignores_stage_manifest_control_file(tmp_path: Path) -> None:
    reference = _reference()
    reference_path = tmp_path / "rda.json"
    reference_path.write_text(json.dumps(reference))
    products_dir = tmp_path / "products"
    _write_batch(products_dir, [{"id": "current", "rda_ul_data": reference_stamp(reference)}])
    stage_dir = products_dir / "output_Test_enriched" / "enriched"
    batch = stage_dir / "enriched_batch.json"
    write_stage_manifest(stage_dir, "enrich", [batch], run_id="rda-audit-run")

    checked, failures = audit_emitted_stamps(
        products_dir=products_dir,
        reference_path=reference_path,
    )

    assert checked == 1
    assert failures == []


def test_audit_rejects_stale_emitted_stamp(tmp_path: Path) -> None:
    reference = _reference()
    reference_path = tmp_path / "rda.json"
    reference_path.write_text(json.dumps(reference))
    _write_batch(
        tmp_path / "products",
        [
            {
                "id": "stale",
                "rda_ul_data": {
                    **reference_stamp(reference),
                    "reference_data_fingerprint": "sha256:stale",
                },
            }
        ],
    )

    checked, failures = audit_emitted_stamps(
        products_dir=tmp_path / "products", reference_path=reference_path
    )

    assert checked == 1
    assert len(failures) == 1
    assert "stale" in failures[0]
