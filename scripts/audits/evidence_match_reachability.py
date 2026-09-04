#!/usr/bin/env python3
"""Recompute clinical-evidence linkage from manifest-owned enriched inputs.

The gate answers one narrow question: does the current evidence matcher reach
exactly the same reviewed records that the enriched artifact stamps, and does
every recomputed match identify the active/form/aggregate that owns it?  It
never discovers studies, performs fuzzy matching, or changes scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from stage_manifest import MANIFEST_NAME, select_stage_files  # noqa: E402


REPORT_SCHEMA_VERSION = "1.0.0"
RecomputeEvidence = Callable[[dict[str, Any]], dict[str, Any]]


class EvidenceReachabilityError(RuntimeError):
    """The exact enriched input corpus or a recomputed match was invalid."""


def _entry_id(match: Any) -> str:
    if not isinstance(match, dict):
        return ""
    return str(match.get("id") or match.get("study_id") or "").strip()


def _clinical_matches(evidence: Any) -> list[dict[str, Any]]:
    if not isinstance(evidence, dict):
        return []
    matches = evidence.get("clinical_matches")
    if not isinstance(matches, list):
        return []
    return [match for match in matches if isinstance(match, dict)]


def _match_has_identity_provenance(match: dict[str, Any]) -> bool:
    if any(
        str(value or "").strip()
        for value in (
            match.get("matched_canonical_id"),
            match.get("marker_via_ingredient"),
        )
    ):
        return True
    return any(
        str(value or "").strip()
        for field in ("matched_canonical_ids", "aggregate_canonical_ids", "matched_source_row_refs")
        for value in (
            match.get(field)
            if isinstance(match.get(field), list)
            else []
        )
    )


def recompute_evidence(enricher: SupplementEnricherV3, product: dict[str, Any]) -> dict[str, Any]:
    """Replay both native ingredient and later whole-formula evidence stages.

    Formula identity is re-proven from label/measurement inputs, never accepted
    from the stamped evidence block that this audit is checking.
    """
    from studied_formulas import formula_clinical_match

    evidence = enricher._collect_evidence_data(product, product.get("ingredient_quality_data"))
    formula = formula_clinical_match(product)
    if formula:
        matches = [m for m in _clinical_matches(evidence) if _entry_id(m) != formula["id"]]
        evidence["clinical_matches"] = [*matches, formula]
        evidence["match_count"] = len(evidence["clinical_matches"])
    return evidence


def build_reachability_report(
    products: Iterable[dict[str, Any]],
    *,
    recompute: RecomputeEvidence,
) -> dict[str, Any]:
    """Compare stamped and recomputed native evidence matches."""
    affected: list[dict[str, Any]] = []
    entry_product_counts: Counter[str] = Counter()
    product_count = 0
    newly_reachable_count = 0
    stale_count = 0
    unlinked_count = 0
    recompute_error_count = 0

    for product in products:
        if not isinstance(product, dict):
            raise EvidenceReachabilityError("Enriched product is not an object")
        product_count += 1
        dsld_id = str(
            product.get("dsld_id") or product.get("dsldId") or product.get("id") or ""
        ).strip()
        if not dsld_id:
            raise EvidenceReachabilityError("Enriched product has no DSLD ID")

        stamped_matches = _clinical_matches(product.get("evidence_data"))
        stamped_ids = {_entry_id(match) for match in stamped_matches if _entry_id(match)}
        recompute_error = None
        try:
            recomputed_matches = _clinical_matches(recompute(product))
        except Exception as exc:  # pragma: no cover - exercised through CLI
            recomputed_matches = []
            recompute_error = f"{type(exc).__name__}: {exc}"
            recompute_error_count += 1
        recomputed_by_id = {
            _entry_id(match): match
            for match in recomputed_matches
            if _entry_id(match)
        }
        recomputed_ids = set(recomputed_by_id)
        for entry_id in recomputed_ids:
            entry_product_counts[entry_id] += 1

        newly_reachable = sorted(recomputed_ids - stamped_ids)
        stale = sorted(stamped_ids - recomputed_ids)
        unlinked = sorted(
            entry_id
            for entry_id, match in recomputed_by_id.items()
            if not _match_has_identity_provenance(match)
        )
        newly_reachable_count += len(newly_reachable)
        stale_count += len(stale)
        unlinked_count += len(unlinked)

        if newly_reachable or stale or unlinked or recompute_error:
            affected.append({
                "dsld_id": dsld_id,
                "product_name": (
                    product.get("product_name")
                    or product.get("fullName")
                    or product.get("name")
                    or ""
                ),
                "newly_reachable_native_ids": newly_reachable,
                "stale_native_ids": stale,
                "unlinked_recomputed_ids": unlinked,
                "recompute_error": recompute_error,
            })

    affected.sort(key=lambda row: row["dsld_id"])
    candidate_clean = not any((
        newly_reachable_count,
        stale_count,
        unlinked_count,
        recompute_error_count,
    ))
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "mode": "read_only",
        "summary": {
            "product_count": product_count,
            "affected_product_count": len(affected),
            "newly_reachable_native_match_count": newly_reachable_count,
            "stale_native_match_count": stale_count,
            "unlinked_recomputed_match_count": unlinked_count,
            "recompute_error_count": recompute_error_count,
            "candidate_clean": candidate_clean,
        },
        "recomputed_entry_product_counts": dict(
            sorted(entry_product_counts.items())
        ),
        "products": affected,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_manifest_owned_products(
    products_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    products: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    stage_dirs = sorted(
        manifest.parent
        for manifest in products_dir.glob(
            f"output_*_enriched/enriched/{MANIFEST_NAME}"
        )
    )
    if not stage_dirs:
        raise EvidenceReachabilityError(
            f"No manifest-owned enriched stages found under {products_dir}"
        )
    for stage_dir in stage_dirs:
        for path in select_stage_files(
            [stage_dir],
            "enrich",
            require_manifest=True,
        ):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, list) or not all(
                isinstance(product, dict) for product in payload
            ):
                raise EvidenceReachabilityError(
                    f"Enriched batch is not a product array: {path}"
                )
            products.extend(payload)
            inputs.append({
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            })
    return products, inputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-dir", type=Path, default=Path("scripts/products"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    products, inputs = _iter_manifest_owned_products(args.products_dir.resolve())
    enricher = SupplementEnricherV3()

    def recompute(product: dict[str, Any]) -> dict[str, Any]:
        return recompute_evidence(enricher, product)

    report = build_reachability_report(products, recompute=recompute)
    report["inputs"] = inputs
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 1 if args.strict and not report["summary"]["candidate_clean"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
