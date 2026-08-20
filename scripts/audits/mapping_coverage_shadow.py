#!/usr/bin/env python3
"""Measure strict mapped coverage without changing catalog eligibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_input_contract import (  # noqa: E402
    get_scoring_ingredients,
    score_exclusion_reason,
)
from stage_manifest import (  # noqa: E402
    MANIFEST_NAME,
    StageManifestError,
    select_stage_files,
)


REPORT_SCHEMA_VERSION = "1.0.0"


class MappingCoverageShadowError(RuntimeError):
    """The shadow measurement could not establish an exact corpus."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
            raise MappingCoverageShadowError(
                f"Unsupported enriched payload shape: {source}"
            )
    else:
        raise MappingCoverageShadowError(
            f"Enriched payload is not a list or object: {source}"
        )

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise MappingCoverageShadowError(
                f"Enriched row {index} is not an object: {source}"
            )
        yield row


def _enriched_stage_dirs(products_dir: Path) -> list[Path]:
    stage_dirs = sorted(
        manifest.parent
        for manifest in products_dir.glob(
            f"output_*_enriched/enriched/{MANIFEST_NAME}"
        )
    )
    if not stage_dirs:
        raise MappingCoverageShadowError(
            f"No manifest-owned enriched stages found under {products_dir}"
        )
    return stage_dirs


def _unresolved_rows(result: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rejected in result.rejected_rows:
        if rejected.reason != "missing_scoring_identity":
            continue
        row = rejected.row
        path = str(row.get("raw_source_path") or "").strip()
        key = path or "|".join((
            str(row.get("name") or row.get("raw_source_text") or ""),
            str(row.get("quantity") or ""),
            str(row.get("unit") or ""),
        ))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "raw_source_path": path or None,
            "label": (
                row.get("raw_source_text")
                or row.get("name")
                or row.get("standard_name")
                or "unknown"
            ),
            "reason_code": score_exclusion_reason(row)
            or "missing_scoring_identity",
            "canonical_id": row.get("canonical_id"),
            "quantity": row.get("quantity"),
            "unit": row.get("unit"),
        })
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("raw_source_path") or ""),
            str(row.get("label") or ""),
        ),
    )


def build_shadow_report(
    products_dir: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a manifest-owned, measure-only mapped-coverage report."""

    products_dir = Path(products_dir).resolve()
    stages: list[dict[str, Any]] = []
    fraction_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    no_eligible_reason_counts: Counter[str] = Counter()
    product_id_counts: Counter[str] = Counter()
    remediation_queue: list[dict[str, Any]] = []
    no_eligible_queue: list[dict[str, Any]] = []
    contract_failures: list[dict[str, Any]] = []
    product_count = 0
    perfect_count = 0
    below_one_count = 0
    no_eligible_count = 0
    mapped_rows = 0
    unmapped_rows = 0

    for stage_dir in _enriched_stage_dirs(products_dir):
        manifest_path = stage_dir / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        owned_files = select_stage_files(
            [stage_dir],
            "enrich",
            require_manifest=True,
        )
        stage_owner = stage_dir.parent.name
        stages.append({
            "stage_owner": stage_owner,
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
                product_count += 1
                dsld_id = str(
                    product.get("dsld_id") or product.get("dsldId") or ""
                ).strip()
                if not dsld_id:
                    raise MappingCoverageShadowError(
                        f"Enriched product has no dsld_id: {source_file}"
                    )
                product_id_counts[dsld_id] += 1

                result = get_scoring_ingredients(
                    product,
                    strict=True,
                    allow_legacy_fallback=False,
                )
                mapped_rows += result.mapped_count
                unmapped_rows += result.unmapped_count
                denominator = result.mapped_count + result.unmapped_count
                if denominator == 0:
                    no_eligible_count += 1
                    fraction_counts["no_score_eligible_rows"] += 1
                    zero_reason = (
                        result.zero_scorable_reason or "no_score_eligible_rows"
                    )
                    no_eligible_reason_counts[zero_reason] += 1
                    iqd = product.get("ingredient_quality_data")
                    if not isinstance(iqd, dict):
                        iqd = {}
                    taxonomy = product.get("supplement_taxonomy")
                    if not isinstance(taxonomy, dict):
                        taxonomy = {}
                    evidence = product.get("product_scoring_evidence")
                    no_eligible_queue.append({
                        "dsld_id": dsld_id,
                        "product_name": (
                            product.get("product_name")
                            or product.get("fullName")
                            or ""
                        ),
                        "stage_owner": stage_owner,
                        "source_file": source_file.name,
                        "product_scoring_class": (
                            product.get("product_scoring_class")
                            or taxonomy.get("product_scoring_class")
                        ),
                        "primary_type": (
                            product.get("primary_type")
                            or taxonomy.get("primary_type")
                        ),
                        "current_quality_score_status": product.get(
                            "quality_score_status"
                        ),
                        "ingredients_scorable_count": len(
                            iqd.get("ingredients_scorable")
                            if isinstance(iqd.get("ingredients_scorable"), list)
                            else []
                        ),
                        "ingredients_skipped_count": len(
                            iqd.get("ingredients_skipped")
                            if isinstance(iqd.get("ingredients_skipped"), list)
                            else []
                        ),
                        "product_scoring_evidence_count": len(
                            evidence if isinstance(evidence, list) else []
                        ),
                        "zero_scorable_reason": zero_reason,
                    })
                else:
                    fraction_counts[
                        f"{result.mapped_count}/{denominator}"
                    ] += 1
                    if result.unmapped_count == 0:
                        perfect_count += 1
                    else:
                        below_one_count += 1

                if not result.strict_contract_passed:
                    contract_failures.append({
                        "dsld_id": dsld_id,
                        "product_name": (
                            product.get("product_name")
                            or product.get("fullName")
                            or ""
                        ),
                        "stage_owner": stage_owner,
                        "source_file": source_file.name,
                        "findings": sorted(set(result.contract_findings)),
                    })

                unresolved = _unresolved_rows(result)
                for row in unresolved:
                    reason_counts[str(row["reason_code"])] += 1
                if result.unmapped_count:
                    remediation_queue.append({
                        "dsld_id": dsld_id,
                        "product_name": (
                            product.get("product_name")
                            or product.get("fullName")
                            or ""
                        ),
                        "stage_owner": stage_owner,
                        "source_file": source_file.name,
                        "mapped_count": result.mapped_count,
                        "unmapped_count": result.unmapped_count,
                        "mapped_coverage": round(
                            result.mapped_count / denominator,
                            6,
                        ),
                        "unresolved_rows": unresolved,
                    })

    duplicate_count = sum(
        count - 1 for count in product_id_counts.values() if count > 1
    )
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "mode": "shadow",
        "enforcement_enabled": False,
        "coverage_contract": (
            "mapped score-eligible label actives / all score-eligible label actives"
        ),
        "products_dir": str(products_dir),
        "source": {
            "stage_count": len(stages),
            "stages": stages,
        },
        "summary": {
            "product_count": product_count,
            "perfect_coverage_product_count": perfect_count,
            "below_one_product_count": below_one_count,
            "no_score_eligible_rows_product_count": no_eligible_count,
            "mapped_score_eligible_row_count": mapped_rows,
            "unmapped_score_eligible_row_count": unmapped_rows,
            "strict_contract_failed_product_count": len(contract_failures),
            "duplicate_product_id_count": duplicate_count,
        },
        "coverage_fraction_counts": dict(sorted(fraction_counts.items())),
        "unresolved_reason_counts": dict(sorted(reason_counts.items())),
        "no_score_eligible_reason_counts": dict(
            sorted(no_eligible_reason_counts.items())
        ),
        "duplicate_product_ids": {
            dsld_id: count
            for dsld_id, count in sorted(product_id_counts.items())
            if count > 1
        },
        "strict_contract_failures": sorted(
            contract_failures,
            key=lambda row: (row["dsld_id"], row["stage_owner"]),
        ),
        "remediation_queue": sorted(
            remediation_queue,
            key=lambda row: (row["dsld_id"], row["stage_owner"]),
        ),
        "no_score_eligible_queue": sorted(
            no_eligible_queue,
            key=lambda row: (row["dsld_id"], row["stage_owner"]),
        ),
    }
    report["report_sha256"] = hashlib.sha256(_canonical_bytes(report)).hexdigest()
    return report


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise MappingCoverageShadowError(
            f"Refusing to overwrite existing report: {path}"
        )
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_shadow_report(args.products_dir)
        _write_new_json(args.out, report)
    except (
        OSError,
        json.JSONDecodeError,
        MappingCoverageShadowError,
        StageManifestError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
