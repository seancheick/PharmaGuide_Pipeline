#!/usr/bin/env python3
"""Measure typed assessment readiness without changing catalog eligibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from assessment_readiness import evaluate_assessment_readiness  # noqa: E402
from scoring_v4.router import class_for_product  # noqa: E402
from stage_manifest import MANIFEST_NAME, select_stage_files  # noqa: E402


REPORT_SCHEMA_VERSION = "1.0.0"


class AssessmentReadinessShadowError(RuntimeError):
    """A measure-only report could not establish its exact input corpus."""


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
            raise AssessmentReadinessShadowError(
                f"Unsupported enriched payload shape: {source}"
            )
    else:
        raise AssessmentReadinessShadowError(
            f"Enriched payload is not a list or object: {source}"
        )
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AssessmentReadinessShadowError(
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
        raise AssessmentReadinessShadowError(
            f"No manifest-owned enriched stages found under {products_dir}"
        )
    return stages


def _material_backlog(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = readiness.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    rows = []
    for assessment in evidence.get("ingredient_assessments") or []:
        if not isinstance(assessment, dict):
            continue
        if assessment.get("state") != "not_yet_evaluated":
            continue
        rows.append({
            "source_row_ref": assessment.get("source_row_ref"),
            "canonical_id": assessment.get("canonical_id"),
            "name": assessment.get("name"),
            "role": assessment.get("role"),
            "reason_code": assessment.get("reason_code"),
        })
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("source_row_ref") or ""),
            str(row.get("canonical_id") or ""),
        ),
    )


def build_shadow_report(
    products_dir: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a manifest-owned, measure-only assessment-readiness report."""
    products_dir = Path(products_dir).resolve()
    dimension_counts: dict[str, Counter[str]] = defaultdict(Counter)
    evidence_state_counts: Counter[str] = Counter()
    verification_state_counts: Counter[str] = Counter()
    unavailable_reason_counts: Counter[str] = Counter()
    product_id_counts: Counter[str] = Counter()
    remediation_queue: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    product_count = 0
    live_ready_count = 0
    incomplete_count = 0
    not_evaluated_active_count = 0
    verification_not_evaluated_count = 0
    legacy_dose_inference_count = 0

    for stage_dir in _stage_dirs(products_dir):
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
                    raise AssessmentReadinessShadowError(
                        f"Enriched product has no dsld_id: {source_file}"
                    )
                product_id_counts[dsld_id] += 1
                module = class_for_product(product)
                readiness = evaluate_assessment_readiness(
                    product,
                    module=module,
                )

                for dimension in (
                    "identity",
                    "dose",
                    "evidence",
                    "verification",
                    "route",
                ):
                    detail = readiness.get(dimension)
                    detail = detail if isinstance(detail, dict) else {}
                    dimension_counts[dimension][
                        str(detail.get("readiness") or "missing")
                    ] += 1

                evidence = readiness.get("evidence")
                evidence = evidence if isinstance(evidence, dict) else {}
                for assessment in evidence.get("ingredient_assessments") or []:
                    if isinstance(assessment, dict):
                        evidence_state_counts[
                            str(assessment.get("state") or "missing")
                        ] += 1
                not_evaluated_active_count += int(
                    evidence.get("not_yet_evaluated_count") or 0
                )

                verification = readiness.get("verification")
                verification = verification if isinstance(verification, dict) else {}
                verification_state = str(
                    verification.get("state") or "missing"
                )
                verification_state_counts[verification_state] += 1
                if verification_state == "not_evaluated":
                    verification_not_evaluated_count += 1

                dose = readiness.get("dose")
                dose = dose if isinstance(dose, dict) else {}
                identity = readiness.get("identity")
                identity = identity if isinstance(identity, dict) else {}
                if dose.get("migration_inference") is True:
                    legacy_dose_inference_count += 1

                unavailable = list(readiness.get("unavailable_reasons") or [])
                for reason in unavailable:
                    unavailable_reason_counts[str(reason)] += 1
                if readiness.get("is_live_ready") is True:
                    live_ready_count += 1
                else:
                    incomplete_count += 1
                    remediation_queue.append({
                        "dsld_id": dsld_id,
                        "product_name": (
                            product.get("product_name")
                            or product.get("fullName")
                            or ""
                        ),
                        "stage_owner": stage_owner,
                        "source_file": source_file.name,
                        "module": module,
                        "unavailable_reasons": unavailable,
                        "identity_blocking_findings": list(
                            identity.get("blocking_contract_findings") or []
                        ),
                        "not_yet_evaluated_material_actives": _material_backlog(
                            readiness
                        ),
                        "verification_state": verification_state,
                        "dose_assessment_source": dose.get("assessment_source"),
                    })

    duplicate_count = sum(
        count - 1 for count in product_id_counts.values() if count > 1
    )
    remediation_queue.sort(key=lambda row: str(row.get("dsld_id") or ""))
    report: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "mode": "measure_only",
        "enforcement_enabled": False,
        "catalog_eligibility_changed": False,
        "generated_at": generated_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "products_dir": str(products_dir),
        "summary": {
            "product_count": product_count,
            "live_ready_product_count": live_ready_count,
            "incomplete_product_count": incomplete_count,
            "not_yet_evaluated_material_active_count": not_evaluated_active_count,
            "verification_not_evaluated_product_count": verification_not_evaluated_count,
            "legacy_dose_inference_product_count": legacy_dose_inference_count,
            "duplicate_product_id_count": duplicate_count,
        },
        "dimension_readiness_counts": {
            name: dict(sorted(counts.items()))
            for name, counts in sorted(dimension_counts.items())
        },
        "evidence_state_counts": dict(sorted(evidence_state_counts.items())),
        "verification_state_counts": dict(
            sorted(verification_state_counts.items())
        ),
        "unavailable_reason_counts": dict(
            sorted(unavailable_reason_counts.items())
        ),
        "remediation_queue": remediation_queue,
        "stages": stages,
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
        f"Wrote measure-only readiness for {report['summary']['product_count']} "
        f"products to {output} ({report['report_sha256']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
