#!/usr/bin/env python3
"""Emit manifest-owned route features without changing catalog behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_input_contract import (  # noqa: E402
    build_scoring_classification,
    get_scoring_ingredients,
)
from scoring_v4.route_features import extract_route_features  # noqa: E402
from stage_manifest import MANIFEST_NAME, select_stage_files  # noqa: E402


REPORT_SCHEMA_VERSION = "1.0.0"


class RoutingFeatureShadowError(RuntimeError):
    """A measure-only route report could not establish its exact inputs."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _iter_products(payload: Any, source: Path) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in ("products", "items", "data"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        if rows is None and (payload.get("dsld_id") or payload.get("dsldId")):
            rows = [payload]
        if rows is None:
            raise RoutingFeatureShadowError(
                f"Unsupported enriched payload shape: {source}"
            )
    else:
        raise RoutingFeatureShadowError(
            f"Enriched payload is not a list or object: {source}"
        )
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RoutingFeatureShadowError(
                f"Enriched row {index} is not an object: {source}"
            )
        yield row


def _stage_dirs(products_dir: Path) -> list[Path]:
    stages = sorted(
        manifest.parent
        for manifest in products_dir.glob(
            f"output_*_enriched/enriched/{MANIFEST_NAME}"
        )
    )
    if not stages:
        raise RoutingFeatureShadowError(
            f"No manifest-owned enriched stages found under {products_dir}"
        )
    return stages


def _stamped_classification(product: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = product.get("product_scoring_classification")
    return value if isinstance(value, Mapping) else None


def build_shadow_report(
    products_dir: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the complete measure-only routing feature report."""
    products_dir = Path(products_dir).resolve()
    route_counts: Counter[str] = Counter()
    primary_type_counts: Counter[str] = Counter()
    product_id_counts: Counter[str] = Counter()
    features: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    stage_records: list[dict[str, Any]] = []
    file_count = 0

    for stage_dir in _stage_dirs(products_dir):
        manifest_path = stage_dir / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        owned_files = select_stage_files(
            [stage_dir],
            "enrich",
            require_manifest=True,
        )
        file_count += len(owned_files)
        stage_records.append({
            "stage_owner": stage_dir.parent.name,
            "run_id": manifest.get("run_id"),
            "manifest_sha256": _sha256(manifest_path),
            "owned_files": [
                {
                    "name": path.name,
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in owned_files
            ],
        })

        for source_file in owned_files:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
            for product in _iter_products(payload, source_file):
                dsld_id = str(
                    product.get("dsld_id")
                    or product.get("dsldId")
                    or product.get("id")
                    or ""
                ).strip()
                if not dsld_id:
                    raise RoutingFeatureShadowError(
                        f"Enriched product has no dsld_id: {source_file}"
                    )
                product_id_counts[dsld_id] += 1
                scoring_rows = list(
                    get_scoring_ingredients(
                        product,
                        strict=True,
                        allow_legacy_fallback=False,
                    ).rows
                )
                ingredient_quality_data = product.get("ingredient_quality_data")
                ingredient_quality_data = (
                    ingredient_quality_data
                    if isinstance(ingredient_quality_data, Mapping)
                    else {}
                )
                observed_rows = [
                    row
                    for row in ingredient_quality_data.get("ingredients") or []
                    if isinstance(row, Mapping)
                ]
                recomputed = build_scoring_classification(
                    product,
                    classification_origin="native_enrichment",
                )
                feature = extract_route_features(
                    product,
                    scoring_rows,
                    recomputed,
                    observed_rows=observed_rows,
                )
                feature["source_stage"] = stage_dir.parent.name
                feature["source_file"] = source_file.name
                stamped = _stamped_classification(product)
                stamped_route = str((stamped or {}).get("route_module") or "").strip().lower()
                recomputed_route = str(recomputed.get("route_module") or "generic")
                feature["stamped_route"] = stamped_route or None
                feature["recomputed_route"] = recomputed_route
                features.append(feature)
                route_counts[recomputed_route] += 1
                primary_type_counts[str(feature.get("primary_type") or "unknown")] += 1
                if stamped_route and stamped_route != recomputed_route:
                    mismatches.append({
                        "dsld_id": dsld_id,
                        "product_name": feature.get("product_name"),
                        "brand_name": feature.get("brand_name"),
                        "stamped_route": stamped_route,
                        "recomputed_route": recomputed_route,
                        "recomputed_reason": feature.get("route_reason"),
                    })

    duplicates = sorted(
        dsld_id for dsld_id, count in product_id_counts.items() if count > 1
    )
    features.sort(key=lambda row: (str(row.get("dsld_id") or ""), str(row.get("source_stage") or "")))
    mismatches.sort(key=lambda row: str(row.get("dsld_id") or ""))
    report: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "mode": "measure_only",
        "enforcement_enabled": False,
        "catalog_eligibility_changed": False,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "products_dir": str(products_dir),
        "product_count": len(features),
        "distinct_product_count": len(product_id_counts),
        "duplicate_product_ids": duplicates,
        "manifest_owned_stage_count": len(stage_records),
        "manifest_owned_file_count": file_count,
        "route_distribution": dict(sorted(route_counts.items())),
        "primary_type_distribution": dict(sorted(primary_type_counts.items())),
        "stamped_vs_recomputed_mismatch_count": len(mismatches),
        "stamped_vs_recomputed_mismatches": mismatches,
        "stages": stage_records,
        "features": features,
    }
    report["report_sha256"] = hashlib.sha256(_canonical_bytes(report)).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-dir", default="scripts/products")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = build_shadow_report(Path(args.products_dir))
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote measure-only routing features for {report['product_count']} "
        f"products to {output} ({report['report_sha256']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
