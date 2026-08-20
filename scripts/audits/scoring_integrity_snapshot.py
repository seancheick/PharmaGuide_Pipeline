#!/usr/bin/env python3
"""Freeze and compare release-sensitive scoring state.

The snapshot reads only checksum-verified Score stage outputs and a completed
catalog candidate. It does not rescore products, replay consumer blobs, or
change any input. The resulting JSON includes a deterministic integrity digest
so an edited baseline is rejected before comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from stage_manifest import MANIFEST_NAME, select_stage_files  # noqa: E402


SNAPSHOT_SCHEMA_VERSION = "1.0.0"
SUBMISSION_STAGE = "output_Product_Submissions_scored"


class SnapshotError(ValueError):
    """The requested integrity snapshot cannot be trusted."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _iter_rows(payload: Any, *, source: Path) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping) and isinstance(payload.get("products"), list):
        rows = payload["products"]
    else:
        raise SnapshotError(f"Scored artifact has unsupported shape: {source}")
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise SnapshotError(f"Scored row {index} is not an object: {source}")
        yield dict(row)


def _ordered_scored_stage_dirs(products_dir: Path) -> list[Path]:
    stage_dirs = sorted(
        path
        for path in products_dir.glob("output_*_scored/scored")
        if path.is_dir()
    )
    submissions = [
        path for path in stage_dirs if path.parent.name == SUBMISSION_STAGE
    ]
    return [path for path in stage_dirs if path not in submissions] + submissions


def _stage_provenance(stage_dir: Path, products_dir: Path) -> dict[str, Any]:
    manifest_path = stage_dir / MANIFEST_NAME
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    return {
        "stage_owner": str(stage_dir.relative_to(products_dir)),
        "run_id": manifest.get("run_id"),
        "generated_at": manifest.get("generated_at"),
        "owned_file_count": len(manifest.get("owned_files") or []),
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "content_sha256": dict(sorted((manifest.get("content_sha256") or {}).items())),
    }


def _score_components(row: Mapping[str, Any]) -> dict[str, Any]:
    breakdown = _safe_dict(row.get("_v4_module_breakdown"))
    dimensions = _safe_dict(breakdown.get("dimensions"))
    return {
        "raw_score_100": breakdown.get("raw_score_100"),
        "dimensions": {
            name: _safe_dict(payload).get("score")
            for name, payload in sorted(dimensions.items())
        },
        "verification_bonus": _safe_dict(
            breakdown.get("verification_bonus")
        ).get("score"),
        "manufacturer_trust": _safe_dict(
            breakdown.get("manufacturer_trust")
        ).get("score"),
        "manufacturer_violations": _safe_dict(
            breakdown.get("manufacturer_violations")
        ).get("score"),
        "safety_hygiene_base": _safe_dict(
            breakdown.get("safety_hygiene_base")
        ).get("score"),
    }


def _freeze_product(
    row: Mapping[str, Any],
    *,
    stage_owner: str,
    source_file: str,
) -> dict[str, Any]:
    provenance = _safe_dict(row.get("_v4_provenance"))
    taxonomy = _safe_dict(row.get("supplement_taxonomy"))
    completeness = _safe_dict(row.get("_v4_completeness_gate"))
    pillars = row.get("_v4_pillars")
    if not isinstance(pillars, Mapping):
        pillars = row.get("quality_pillars_v4")
    frozen_pillars = {
        str(key): value for key, value in sorted(_safe_dict(pillars).items())
    }
    quality_score = row.get("quality_score_v4_100")
    if quality_score is None:
        quality_score = row.get("_v4_quality_score_100")

    return {
        "source": {
            "stage_owner": stage_owner,
            "file": source_file,
        },
        "route": {
            "module": row.get("_v4_module") or provenance.get("module_route"),
            "reason_codes": list(taxonomy.get("classification_reason_codes") or []),
            "confidence": taxonomy.get("classification_confidence"),
            "classifier_version": provenance.get("classification_schema_version"),
        },
        "score": {
            "quality_score_v4_100": quality_score,
            "raw_score_v4_100": row.get("raw_score_v4_100")
            if row.get("raw_score_v4_100") is not None
            else row.get("_v4_raw_score_100"),
            "pillars": frozen_pillars,
            "components": _score_components(row),
            "tier": row.get("quality_tier") or row.get("_v4_quality_tier"),
            "confidence": row.get("quality_score_confidence")
            if "quality_score_confidence" in row
            else row.get("_v4_confidence"),
        },
        "outcome": {
            "quality_score_status": row.get("quality_score_status"),
            "verdict": row.get("verdict"),
            "safety_verdict": row.get("safety_verdict"),
            "blocking_reason": row.get("blocking_reason"),
            "score_unavailable_reason": row.get("score_unavailable_reason")
            or row.get("not_scorable_reason")
            or row.get("quality_score_suppressed_reason"),
            "is_live_eligible": completeness.get("is_live_eligible"),
            "completeness_verdict": completeness.get("verdict"),
        },
        "mapping": {
            "mapped_coverage": row.get("mapped_coverage"),
            "unmapped_actives_total": row.get("unmapped_actives_total"),
        },
    }


def _distribution(products: Mapping[str, Mapping[str, Any]], path: tuple[str, ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for product in products.values():
        value: Any = product
        for part in path:
            value = _safe_dict(value).get(part)
        counts["<null>" if value is None else str(value)] += 1
    return dict(sorted(counts.items()))


def _load_scored_products(products_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    stage_dirs = _ordered_scored_stage_dirs(products_dir)
    if not stage_dirs:
        raise SnapshotError(f"No scored stage directories under {products_dir}")

    products: dict[str, Any] = {}
    stage_records: list[dict[str, Any]] = []
    source_digest = hashlib.sha256()
    input_rows = 0
    duplicate_rows = 0

    for stage_dir in stage_dirs:
        owned_files = select_stage_files(
            [stage_dir],
            "score",
            require_manifest=True,
        )
        provenance = _stage_provenance(stage_dir, products_dir)
        stage_records.append(provenance)
        source_digest.update(_canonical_bytes(provenance))
        stage_owner = provenance["stage_owner"]

        for path in owned_files:
            payload = json.loads(path.read_bytes())
            for row in _iter_rows(payload, source=path):
                input_rows += 1
                dsld_id = str(row.get("dsld_id") or "").strip()
                if not dsld_id:
                    raise SnapshotError(f"Scored row has no dsld_id: {path}")
                if dsld_id in products:
                    duplicate_rows += 1
                products[dsld_id] = _freeze_product(
                    row,
                    stage_owner=stage_owner,
                    source_file=path.name,
                )

    source = {
        "scored_stage_count": len(stage_records),
        "stages": stage_records,
        "scored_source_sha256": source_digest.hexdigest(),
        "scored_input_rows": input_rows,
        "duplicate_scored_rows": duplicate_rows,
    }
    return dict(sorted(products.items())), source


def _artifact_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SnapshotError(f"Required release artifact is missing: {path}")
    digest, size = _hash_file(path)
    return {"bytes": size, "sha256": digest}


def _catalog_product_count(db_path: Path) -> int:
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM products_core").fetchone()[0]
            )
    except (sqlite3.Error, TypeError, IndexError) as exc:
        raise SnapshotError(f"Cannot read products_core from {db_path}: {exc}") from exc


def _payload_accounting(dist_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    blobs_dir = dist_dir / "detail_blobs"
    if not blobs_dir.is_dir():
        raise SnapshotError(f"Detail blob directory is missing: {blobs_dir}")

    blob_files = sorted(blobs_dir.glob("*.json"), key=lambda path: path.name)
    key_bytes: defaultdict[str, int] = defaultdict(int)
    key_occurrences: Counter[str] = Counter()
    tree_digest = hashlib.sha256()
    total_bytes = 0

    for path in blob_files:
        raw = path.read_bytes()
        total_bytes += len(raw)
        raw_digest = _sha256_bytes(raw)
        tree_digest.update(path.name.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(raw_digest.encode("ascii"))
        tree_digest.update(b"\0")
        tree_digest.update(str(len(raw)).encode("ascii"))
        tree_digest.update(b"\n")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SnapshotError(f"Unreadable detail blob {path}: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise SnapshotError(f"Detail blob is not an object: {path}")
        for key, value in payload.items():
            normalized_key = str(key)
            key_occurrences[normalized_key] += 1
            key_bytes[normalized_key] += len(
                _canonical_bytes({normalized_key: value})
            )

    payload = {
        "detail_blob_count": len(blob_files),
        "detail_blob_bytes": total_bytes,
        "detail_blob_tree_sha256": tree_digest.hexdigest(),
        "top_level_key_bytes_method": "canonical-single-key-json",
        "top_level_key_bytes": dict(sorted(key_bytes.items())),
        "top_level_key_occurrences": dict(sorted(key_occurrences.items())),
    }
    artifact = {
        "detail_blobs": {
            "count": len(blob_files),
            "bytes": total_bytes,
            "sha256": tree_digest.hexdigest(),
        }
    }
    return payload, artifact


def seal_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    """Replace the self-hash after all report content is final."""
    report.pop("integrity", None)
    report["integrity"] = {
        "algorithm": "sha256",
        "scope": "canonical JSON excluding integrity",
        "sha256": _sha256_bytes(_canonical_bytes(report)),
    }
    return report


def verify_integrity(report: Mapping[str, Any]) -> bool:
    integrity = _safe_dict(report.get("integrity"))
    expected = integrity.get("sha256")
    if not isinstance(expected, str):
        return False
    body = dict(report)
    body.pop("integrity", None)
    return expected == _sha256_bytes(_canonical_bytes(body))


def build_snapshot(products_dir: Path, dist_dir: Path) -> dict[str, Any]:
    products_dir = Path(products_dir).resolve()
    dist_dir = Path(dist_dir).resolve()
    products, source = _load_scored_products(products_dir)

    manifest_path = dist_dir / "export_manifest.json"
    index_path = dist_dir / "detail_index.json"
    core_path = dist_dir / "pharmaguide_core.db"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise SnapshotError("export_manifest.json must be an object")

    artifacts = {
        "export_manifest.json": _artifact_record(manifest_path),
        "detail_index.json": _artifact_record(index_path),
        "pharmaguide_core.db": _artifact_record(core_path),
    }
    payload, blob_artifact = _payload_accounting(dist_dir)
    artifacts.update(blob_artifact)
    exported_products = _catalog_product_count(core_path)
    excluded = sorted(
        str(entry.get("dsld_id"))
        for entry in (manifest.get("excluded_by_gate") or [])
        if isinstance(entry, Mapping) and entry.get("dsld_id") is not None
    )

    report: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "source": source,
        "release_contract": {
            "export_schema_version": manifest.get("schema_version"),
            "scoring_version": manifest.get("scoring_version"),
            "pipeline_version": manifest.get("pipeline_version"),
            "db_version": manifest.get("db_version"),
        },
        "corpus": {
            "scored_input_rows": source["scored_input_rows"],
            "scored_unique_products": len(products),
            "duplicate_scored_rows": source["duplicate_scored_rows"],
            "exported_products": exported_products,
            "excluded_by_gate": excluded,
            "module_counts": _distribution(products, ("route", "module")),
            "quality_status_counts": _distribution(
                products, ("outcome", "quality_score_status")
            ),
            "verdict_counts": _distribution(products, ("outcome", "verdict")),
            "tier_counts": _distribution(products, ("score", "tier")),
            "confidence_counts": _distribution(
                products, ("score", "confidence")
            ),
            "live_eligibility_counts": _distribution(
                products, ("outcome", "is_live_eligible")
            ),
        },
        "artifacts": artifacts,
        "payload": payload,
        "products": products,
    }
    return seal_snapshot(report)


def _changed_ids(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    path: tuple[str, ...],
    shared_ids: Iterable[str],
) -> list[str]:
    changed: list[str] = []
    for dsld_id in shared_ids:
        before: Any = baseline[dsld_id]
        after: Any = candidate[dsld_id]
        for part in path:
            before = _safe_dict(before).get(part)
            after = _safe_dict(after).get(part)
        if before != after:
            changed.append(dsld_id)
    return changed


def compare_snapshots(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    if not verify_integrity(baseline):
        raise SnapshotError("Baseline snapshot integrity check failed")
    if not verify_integrity(candidate):
        raise SnapshotError("Candidate snapshot integrity check failed")
    before = _safe_dict(baseline.get("products"))
    after = _safe_dict(candidate.get("products"))
    before_ids = set(before)
    after_ids = set(after)
    shared_ids = sorted(before_ids & after_ids)

    result = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "baseline_sha256": _safe_dict(baseline.get("integrity")).get("sha256"),
        "candidate_sha256": _safe_dict(candidate.get("integrity")).get("sha256"),
        "added_products": sorted(after_ids - before_ids),
        "removed_products": sorted(before_ids - after_ids),
        "changed_routes": _changed_ids(
            before, after, ("route", "module"), shared_ids
        ),
        "changed_route_provenance": _changed_ids(
            before, after, ("route",), shared_ids
        ),
        "changed_scores": _changed_ids(
            before, after, ("score", "quality_score_v4_100"), shared_ids
        ),
        "changed_pillars": _changed_ids(
            before, after, ("score", "pillars"), shared_ids
        ),
        "changed_score_components": _changed_ids(
            before, after, ("score", "components"), shared_ids
        ),
        "changed_tiers": _changed_ids(before, after, ("score", "tier"), shared_ids),
        "changed_verdicts": _changed_ids(
            before, after, ("outcome", "verdict"), shared_ids
        ),
        "changed_statuses": _changed_ids(
            before, after, ("outcome", "quality_score_status"), shared_ids
        ),
        "changed_mapping_coverage": _changed_ids(
            before, after, ("mapping", "mapped_coverage"), shared_ids
        ),
        "changed_blocking_reasons": _changed_ids(
            before, after, ("outcome", "blocking_reason"), shared_ids
        ),
    }
    result["unchanged_product_count"] = len(shared_ids) - len(
        set().union(
            *(set(value) for key, value in result.items() if key.startswith("changed_"))
        )
    )
    return result


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise SnapshotError(f"Refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_verified(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not verify_integrity(payload):
        raise SnapshotError(f"Snapshot integrity check failed: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    freeze = commands.add_parser("freeze", help="Freeze a manifest-owned snapshot")
    freeze.add_argument("--products-dir", type=Path, required=True)
    freeze.add_argument("--dist-dir", type=Path, required=True)
    freeze.add_argument("--out", type=Path, required=True)

    compare = commands.add_parser("compare", help="Compare two frozen snapshots")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            report = build_snapshot(args.products_dir, args.dist_dir)
        else:
            report = compare_snapshots(
                _load_verified(args.baseline),
                _load_verified(args.candidate),
            )
        _write_new_json(args.out, report)
    except (OSError, json.JSONDecodeError, SnapshotError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
