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


REPORT_SCHEMA_VERSION = "1.1.0"


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
    scored_products_dir: Path | None = None,
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
    shadow_incomplete_count = 0
    cause_backlog: dict[tuple[str, str, str], dict[str, Any]] = {}

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
            artifact_sha256 = next(item["sha256"] for item in stages[-1]["owned_files"]
                                   if item["name"] == source_file.name)
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
                # This is a report of the existing owner's decisions, never a
                # second readiness classifier. Regeneration cannot close work:
                # closure also needs reviewed resolution and rebuilt evidence.
                for dimension, symbol in {
                    "identity": "_identity_readiness",
                    "dose": "_dose_readiness",
                    "evidence": "evaluate_evidence_assessment",
                    "verification": "evaluate_verification_assessment",
                    "route": "_route_readiness",
                }.items():
                    detail = readiness.get(dimension) or {}
                    if detail.get("readiness") != "incomplete":
                        continue
                    findings = ([item for item in detail.get("ingredient_assessments", [])
                                 if item.get("state") == "not_yet_evaluated"]
                                if dimension == "evidence" else [])
                    for finding in findings or [detail]:
                        reason = str(finding.get("reason_code") or "incomplete_assessment")
                        canonical_id = str(finding.get("canonical_id") or "")
                        key = (dimension, reason, canonical_id)
                        group = cause_backlog.setdefault(key, {
                            "dimension": dimension, "cause": reason,
                            "canonical_id": canonical_id,
                            "owner": f"assessment_readiness.py::{symbol}",
                            "affected_product_ids": set(), "source_evidence": [],
                            "status": "open", "resolution": None,
                            "regression_coverage": [], "review_result": None,
                            "rebuilt_verification": None,
                        })
                        group["affected_product_ids"].add(dsld_id)
                        group["source_evidence"].append({
                            "dsld_id": dsld_id, "stage_owner": stage_owner,
                            "source_file": source_file.name,
                            "artifact_sha256": artifact_sha256,
                            "source_row_ref": finding.get("source_row_ref"),
                            "assessment": finding,
                        })

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
                shadow_incomplete = [
                    str(name)
                    for name in readiness.get("shadow_incomplete_dimensions") or []
                ]
                if shadow_incomplete:
                    shadow_incomplete_count += 1
                if readiness.get("is_live_ready") is True:
                    live_ready_count += 1
                else:
                    incomplete_count += 1
                if unavailable or shadow_incomplete:
                    remediation_queue.append({
                        "gates_catalog_eligibility": bool(unavailable),
                        "shadow_incomplete_dimensions": shadow_incomplete,
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
                        "identity_reason_code": identity.get("reason_code"),
                        "dose_reason_code": dose.get("reason_code"),
                        "not_yet_evaluated_material_actives": _material_backlog(
                            readiness
                        ),
                        "verification_state": verification_state,
                        "dose_assessment_source": dose.get("assessment_source"),
                    })

    if scored_products_dir is not None:
        scored_root = Path(scored_products_dir).resolve()
        scored_stages = sorted(scored_root.glob(f"output_*_scored/scored/{MANIFEST_NAME}"))
        if not scored_stages:
            raise AssessmentReadinessShadowError("No manifest-owned scored stages found")
        scored_ids: set[str] = set()
        for manifest_path in scored_stages:
            stage = manifest_path.parent
            manifest_digest = _sha256(manifest_path)
            for path in select_stage_files([stage], "score", require_manifest=True):
                digest = _sha256(path)
                for product in _iter_products(json.loads(path.read_text()), path):
                    pid = str(product.get("dsld_id") or product.get("dsldId") or product.get("id") or "")
                    if not pid or pid in scored_ids:
                        raise AssessmentReadinessShadowError("Missing or duplicate scored product ID")
                    scored_ids.add(pid)
                    readiness = product.get("assessment_readiness") or {}
                    receipt = readiness.get("release_assessment") or {}
                    blockers = receipt.get("blockers")
                    if (not isinstance(blockers, list) or
                            (receipt.get("is_complete") is not True and not blockers)):
                        blockers = ["release_assessment_receipt_missing"]
                    for blocker in blockers:
                        cause, _, subject = str(blocker).partition(":")
                        group = cause_backlog.setdefault(("release", cause, subject), {
                            "dimension": "release", "cause": cause, "canonical_id": subject,
                            "owner": "assessment_readiness.py::evaluate_release_assessment",
                            "affected_product_ids": set(), "source_evidence": [],
                            "status": "open", "resolution": None, "regression_coverage": [],
                            "review_result": None, "rebuilt_verification": None,
                        })
                        group["affected_product_ids"].add(pid)
                        group["source_evidence"].append({
                            "dsld_id": pid, "stage_owner": stage.parent.name,
                            "source_file": path.name, "artifact_sha256": digest,
                            "manifest_sha256": manifest_digest,
                            "assessment": receipt,
                        })
        if scored_ids != set(product_id_counts):
            raise AssessmentReadinessShadowError("Scored and enriched product cohorts differ")

    duplicate_count = sum(
        count - 1 for count in product_id_counts.values() if count > 1
    )
    remediation_queue.sort(key=lambda row: str(row.get("dsld_id") or ""))
    report: dict[str, Any] = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "mode": "measure_only",
        "enforcement_enabled": False,
        "catalog_eligibility_changed": False,
        "release_assessments_included": scored_products_dir is not None,
        "generated_at": generated_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "products_dir": str(products_dir),
        "summary": {
            "product_count": product_count,
            "live_ready_product_count": live_ready_count,
            "incomplete_product_count": incomplete_count,
            "shadow_incomplete_product_count": shadow_incomplete_count,
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
        "cause_backlog": [
            {**group, "affected_product_ids": sorted(group["affected_product_ids"])}
            for _, group in sorted(cause_backlog.items())
        ],
        "stages": stages,
    }
    report["report_sha256"] = hashlib.sha256(_canonical_bytes(report)).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-dir", default="scripts/products")
    parser.add_argument("--output", required=True)
    parser.add_argument("--scored-products-dir", help="Include existing scored release-completion receipts")
    args = parser.parse_args()

    report = build_shadow_report(Path(args.products_dir),
        scored_products_dir=Path(args.scored_products_dir) if args.scored_products_dir else None)
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
