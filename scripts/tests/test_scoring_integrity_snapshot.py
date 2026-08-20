from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "audits"))

from stage_manifest import StageManifestError, write_stage_manifest  # noqa: E402
import scoring_integrity_snapshot as snapshot  # noqa: E402


def _scored_row(
    dsld_id: str,
    *,
    module: str = "generic",
    score: float = 61.5,
    verdict: str = "SAFE",
) -> dict:
    return {
        "dsld_id": dsld_id,
        "_v4_module": module,
        "_v4_quality_score_100": score,
        "quality_score_v4_100": score,
        "quality_score_status": "scored",
        "quality_tier": "Acceptable",
        "verdict": verdict,
        "safety_verdict": verdict,
        "mapped_coverage": 1.0,
        "blocking_reason": None,
        "_v4_confidence": "high",
        "_v4_pillars": {
            "formulation": 12.0,
            "dose": 13.0,
            "evidence": 10.0,
            "transparency": 9.0,
            "verification": 8.0,
            "safety_hygiene": 9.5,
        },
        "_v4_completeness_gate": {
            "is_live_eligible": True,
            "verdict": None,
        },
        "_v4_provenance": {
            "module_route": module,
            "scoring_engine_version": "4.2.0",
        },
        "supplement_taxonomy": {
            "classification_confidence": 0.95,
            "classification_reason_codes": ["fixture_route"],
        },
        "_v4_module_breakdown": {
            "raw_score_100": score,
            "dimensions": {
                "formulation": {"score": 12.0},
                "dose": {"score": 13.0},
                "evidence": {"score": 10.0},
                "transparency": {"score": 9.0},
            },
            "verification_bonus": {"score": 3.0},
            "manufacturer_trust": {"score": 1.0},
            "manufacturer_violations": {"score": 0.0},
            "safety_hygiene_base": {"score": 9.5},
        },
    }


def _write_scored_stage(
    products_dir: Path,
    name: str,
    rows: list[dict],
) -> None:
    stage_dir = products_dir / f"output_{name}_scored" / "scored"
    stage_dir.mkdir(parents=True)
    batch = stage_dir / "scored_cleaned_batch_1.json"
    batch.write_text(json.dumps(rows), encoding="utf-8")
    write_stage_manifest(stage_dir, "score", [batch], run_id=f"run-{name.lower()}")


def _write_dist(dist_dir: Path, rows: list[dict]) -> None:
    blobs = dist_dir / "detail_blobs"
    blobs.mkdir(parents=True)
    index = {}
    for row in rows:
        dsld_id = row["dsld_id"]
        payload = {
            "dsld_id": dsld_id,
            "ingredients": [{"canonical_id": "fixture"}],
            "warnings": [],
        }
        blob_path = blobs / f"{dsld_id}.json"
        blob_path.write_text(json.dumps(payload), encoding="utf-8")
        index[dsld_id] = {"blob_sha256": "fixture"}

    (dist_dir / "detail_index.json").write_text(
        json.dumps(index), encoding="utf-8"
    )
    (dist_dir / "export_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "2.3.0",
                "scoring_version": "4.2.0",
                "product_count": len(rows),
                "excluded_by_gate": [{"dsld_id": "quarantined"}],
            }
        ),
        encoding="utf-8",
    )
    with sqlite3.connect(dist_dir / "pharmaguide_core.db") as connection:
        connection.execute("CREATE TABLE products_core (dsld_id TEXT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO products_core (dsld_id) VALUES (?)",
            [(row["dsld_id"],) for row in rows],
        )


def test_snapshot_freezes_manifest_owned_scores_artifacts_and_payload_bytes(
    tmp_path: Path,
) -> None:
    products = tmp_path / "products"
    dist = tmp_path / "dist"
    rows = [_scored_row("1"), _scored_row("2", module="omega", score=72.0)]
    _write_scored_stage(products, "Fixture", rows)
    _write_dist(dist, rows)

    report = snapshot.build_snapshot(products, dist)

    assert report["corpus"]["scored_input_rows"] == 2
    assert report["corpus"]["scored_unique_products"] == 2
    assert report["corpus"]["exported_products"] == 2
    assert report["corpus"]["module_counts"] == {"generic": 1, "omega": 1}
    assert report["corpus"]["excluded_by_gate"] == ["quarantined"]
    assert report["products"]["2"]["route"]["module"] == "omega"
    assert report["products"]["2"]["score"]["quality_score_v4_100"] == 72.0
    assert report["payload"]["detail_blob_count"] == 2
    assert report["payload"]["detail_blob_bytes"] == sum(
        path.stat().st_size for path in (dist / "detail_blobs").glob("*.json")
    )
    assert report["payload"]["top_level_key_bytes"]["ingredients"] > 0
    assert report["artifacts"]["pharmaguide_core.db"]["sha256"]
    assert snapshot.verify_integrity(report)


def test_snapshot_rejects_unowned_scored_json(tmp_path: Path) -> None:
    products = tmp_path / "products"
    dist = tmp_path / "dist"
    rows = [_scored_row("1")]
    _write_scored_stage(products, "Fixture", rows)
    _write_dist(dist, rows)
    stage = products / "output_Fixture_scored" / "scored"
    (stage / "unowned.json").write_text("[]", encoding="utf-8")

    with pytest.raises(StageManifestError, match="unowned files"):
        snapshot.build_snapshot(products, dist)


def test_product_submissions_are_the_explicit_duplicate_winner(tmp_path: Path) -> None:
    products = tmp_path / "products"
    dist = tmp_path / "dist"
    _write_scored_stage(products, "Base", [_scored_row("1", score=50.0)])
    _write_scored_stage(
        products,
        "Product_Submissions",
        [_scored_row("1", score=80.0)],
    )
    _write_dist(dist, [_scored_row("1", score=80.0)])

    report = snapshot.build_snapshot(products, dist)

    assert report["corpus"]["duplicate_scored_rows"] == 1
    assert report["products"]["1"]["score"]["quality_score_v4_100"] == 80.0
    assert report["products"]["1"]["source"]["stage_owner"] == (
        "output_Product_Submissions_scored/scored"
    )


def test_snapshot_diff_reports_every_release_sensitive_change(tmp_path: Path) -> None:
    products = tmp_path / "products"
    dist = tmp_path / "dist"
    rows = [_scored_row("1"), _scored_row("2")]
    _write_scored_stage(products, "Fixture", rows)
    _write_dist(dist, rows)
    baseline = snapshot.build_snapshot(products, dist)

    changed = json.loads(json.dumps(baseline))
    changed["products"]["1"]["route"]["module"] = "omega"
    changed["products"]["1"]["score"]["quality_score_v4_100"] = 70.0
    changed["products"]["1"]["score"]["pillars"]["dose"] = 15.0
    changed["products"]["1"]["outcome"]["verdict"] = "CAUTION"
    changed["products"]["1"]["outcome"]["quality_score_status"] = "not_scored"
    changed["products"].pop("2")
    changed["products"]["3"] = changed["products"]["1"]
    assert not snapshot.verify_integrity(changed)
    snapshot.seal_snapshot(changed)

    delta = snapshot.compare_snapshots(baseline, changed)

    assert delta["added_products"] == ["3"]
    assert delta["removed_products"] == ["2"]
    assert delta["changed_routes"] == ["1"]
    assert delta["changed_scores"] == ["1"]
    assert delta["changed_pillars"] == ["1"]
    assert delta["changed_verdicts"] == ["1"]
    assert delta["changed_statuses"] == ["1"]
