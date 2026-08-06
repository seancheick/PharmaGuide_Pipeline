#!/usr/bin/env python3
"""Read-only Phase 5 triage for released products with zero V4 Evidence.

This audit separates facts the pipeline can prove from clinical conclusions
that require external literature review. It never changes enrichment data,
scoring configuration, or product scores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


BUCKET_IDENTITY_OR_LINKAGE_FAILED = (
    "evidence_exists_identity_or_linkage_failed"
)
BUCKET_EVIDENCE_TRULY_ABSENT = "evidence_truly_absent"
BUCKET_KNOWLEDGE_BASE_MISSING = "evidence_exists_knowledge_base_missing"
BUCKET_PRODUCT_NOT_COMPARABLE = "evidence_exists_product_not_comparable"
BUCKET_REFERENCE_OR_MECHANISM_ONLY = "reference_or_mechanism_only"
BUCKET_EXTERNAL_REVIEW_REQUIRED = "external_literature_review_required"
FINAL_REVIEW_BUCKETS = frozenset({
    BUCKET_EVIDENCE_TRULY_ABSENT,
    BUCKET_IDENTITY_OR_LINKAGE_FAILED,
    BUCKET_KNOWLEDGE_BASE_MISSING,
    BUCKET_PRODUCT_NOT_COMPARABLE,
    BUCKET_REFERENCE_OR_MECHANISM_ONLY,
})


def build_triage_report(
    catalog_products: Iterable[dict[str, Any]],
    scored_products: Iterable[dict[str, Any]],
    evidence_entries: Iterable[dict[str, Any]],
    *,
    review_decisions: Iterable[dict[str, Any]] = (),
    tier_thresholds: Iterable[float] = (),
    detail_products: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Return a deterministic triage report scoped to unique released rows."""
    scored_product_rows = list(scored_products)
    scored_by_id = {
        _dsld_id(product): product
        for product in scored_product_rows
        if _dsld_id(product)
    }
    stage3_zero_ids = [
        _dsld_id(product)
        for product in scored_product_rows
        if _is_stage3_zero_evidence(product)
    ]
    stage3_unique_zero_ids = set(stage3_zero_ids)
    detail_by_id = {
        _dsld_id(product): product
        for product in detail_products
        if _dsld_id(product)
    }
    evidence_index = _evidence_identity_index(evidence_entries)
    decision_index, invalid_decision_count = _review_decision_index(
        review_decisions
    )
    products: list[dict[str, Any]] = []

    seen_catalog_ids: set[str] = set()
    for catalog_product in catalog_products:
        dsld_id = _dsld_id(catalog_product)
        if not dsld_id or dsld_id in seen_catalog_ids:
            continue
        seen_catalog_ids.add(dsld_id)
        if catalog_product.get("quality_score_status") != "scored":
            continue
        if _as_float(catalog_product.get("pillar_evidence_v4")) != 0.0:
            continue

        detail_identity_names = _detail_identity_names(
            detail_by_id.get(dsld_id, {})
        )
        identity_names = (
            detail_identity_names
            if detail_identity_names
            else _catalog_identity_names(catalog_product)
        )
        identity_keys = {_norm(name) for name in identity_names if _norm(name)}
        matched_entries = {
            entry["id"]: entry
            for name in identity_names
            for entry in evidence_index.get(_norm(name), ())
        }
        matched_ids = sorted(matched_entries)
        verified_human_ids = sorted(
            entry_id
            for entry_id, entry in matched_entries.items()
            if _is_verified_human_entry(entry)
        )
        score_eligible_human_ids = sorted(
            entry_id
            for entry_id, entry in matched_entries.items()
            if _is_score_eligible_human_entry(entry)
        )
        stage3_product = scored_by_id.get(dsld_id, {})
        stage3_metadata = _evidence_metadata(stage3_product)
        comparison_reasons = _dose_form_population_reasons(stage3_metadata)
        identity_level, identity_drivers = _identity_context(stage3_product)
        matched_decisions = {
            decision["id"]: decision
            for identity_key in identity_keys
            for decision in decision_index.get(identity_key, ())
        }
        reviewed_buckets = {
            decision["bucket"] for decision in matched_decisions.values()
        }
        review_decision_id = None
        conflicting_review_decision_ids = (
            sorted(matched_decisions)
            if len(reviewed_buckets) > 1
            else []
        )
        if conflicting_review_decision_ids:
            bucket = BUCKET_EXTERNAL_REVIEW_REQUIRED
        elif len(reviewed_buckets) == 1:
            bucket = reviewed_buckets.pop()
            review_decision_id = ",".join(sorted(matched_decisions))
        elif score_eligible_human_ids and comparison_reasons:
            bucket = BUCKET_PRODUCT_NOT_COMPARABLE
        elif score_eligible_human_ids:
            bucket = BUCKET_IDENTITY_OR_LINKAGE_FAILED
        elif (
            verified_human_ids
            and int(_as_float(stage3_metadata.get("matched_entries")) or 0) > 0
        ):
            bucket = BUCKET_EVIDENCE_TRULY_ABSENT
        elif (
            matched_ids
            and int(_as_float(stage3_metadata.get("matched_entries")) or 0) > 0
        ):
            bucket = BUCKET_REFERENCE_OR_MECHANISM_ONLY
        else:
            bucket = BUCKET_EXTERNAL_REVIEW_REQUIRED
        products.append({
            "dsld_id": dsld_id,
            "product_name": catalog_product.get("product_name"),
            "brand_name": catalog_product.get("brand_name"),
            "v4_module": catalog_product.get("v4_module"),
            "quality_score_v4_100": catalog_product.get(
                "quality_score_v4_100"
            ),
            "quality_tier": catalog_product.get("quality_tier"),
            "bucket": bucket,
            "matched_evidence_entry_ids": matched_ids,
            "matched_verified_human_entry_ids": verified_human_ids,
            "matched_score_eligible_human_entry_ids": (
                score_eligible_human_ids
            ),
            "dose_form_population_reasons": comparison_reasons,
            "review_decision_id": review_decision_id,
            "conflicting_review_decision_ids": (
                conflicting_review_decision_ids
            ),
            "candidate_identity_keys": sorted(identity_keys),
            "identity_confidence": identity_level,
            "identity_drivers": identity_drivers,
            "stage3_context_present": dsld_id in scored_by_id,
            "detail_blob_context_present": dsld_id in detail_by_id,
        })

    _attach_priority(products, tier_thresholds)
    products.sort(key=lambda row: (
        -(row.get("priority_score") or 0.0),
        row["bucket"],
        row["dsld_id"],
    ))
    released_zero_ids = {row["dsld_id"] for row in products}
    bucket_counts = Counter(row["bucket"] for row in products)
    review_groups = _build_review_groups(products)
    return {
        "summary": {
            "released_zero_evidence_products": len(products),
            "stage3_zero_evidence_rows": len(stage3_zero_ids),
            "stage3_unique_zero_evidence_products": len(
                stage3_unique_zero_ids
            ),
            "duplicate_stage3_zero_evidence_rows": (
                len(stage3_zero_ids) - len(stage3_unique_zero_ids)
            ),
            "stage3_zero_evidence_products_not_released": len(
                stage3_unique_zero_ids - released_zero_ids
            ),
            "released_zero_evidence_missing_stage3_context": len(
                released_zero_ids - set(scored_by_id)
            ),
            "released_zero_evidence_missing_detail_blob_context": len(
                released_zero_ids - set(detail_by_id)
            ),
            "bucket_counts": dict(sorted(bucket_counts.items())),
            "invalid_review_decisions": invalid_decision_count,
            "conflicting_review_decision_products": sum(
                bool(row["conflicting_review_decision_ids"])
                for row in products
            ),
            "priority_method": {
                "formula": (
                    "catalog_prevalence_proxy * evidence_likely_exists * "
                    "identity_reliability * current_evidence_zero * "
                    "tier_proximity"
                ),
                "scan_frequency": (
                    "catalog prevalence proxy; product scan telemetry unavailable"
                ),
                "calibration_effect": "none; review ordering only",
            },
        },
        "products": products,
        "review_groups": review_groups,
    }


def _identity_context(
    scored_product: dict[str, Any],
) -> tuple[str | None, list[str]]:
    confidence = scored_product.get("_v4_confidence_detail")
    if not isinstance(confidence, dict):
        return None, []
    identity = confidence.get("identity")
    if not isinstance(identity, dict):
        return None, []
    level = str(identity.get("level") or "").strip().lower() or None
    drivers = sorted({
        str(driver)
        for driver in identity.get("drivers") or []
        if str(driver).strip()
    })
    return level, drivers


def _attach_priority(
    products: list[dict[str, Any]],
    tier_thresholds: Iterable[float],
) -> None:
    thresholds = sorted({
        float(value)
        for value in tier_thresholds
        if _as_float(value) is not None and float(value) > 0.0
    })
    for product in products:
        verified_ids = product["matched_verified_human_entry_ids"]
        matched_ids = product["matched_evidence_entry_ids"]
        identity_keys = product["candidate_identity_keys"]
        product["review_key"] = (
            verified_ids[0]
            if verified_ids
            else matched_ids[0]
            if matched_ids
            else identity_keys[0]
            if identity_keys
            else f"unidentified:{product['dsld_id']}"
        )

    prevalence = Counter(product["review_key"] for product in products)
    evidence_factors = {
        BUCKET_EVIDENCE_TRULY_ABSENT: 0.1,
        BUCKET_IDENTITY_OR_LINKAGE_FAILED: 1.0,
        BUCKET_KNOWLEDGE_BASE_MISSING: 1.0,
        BUCKET_PRODUCT_NOT_COMPARABLE: 1.0,
        BUCKET_REFERENCE_OR_MECHANISM_ONLY: 0.2,
        BUCKET_EXTERNAL_REVIEW_REQUIRED: 0.5,
    }
    identity_factors = {
        "high": 1.0,
        "moderate": 0.7,
        "low": 0.4,
        None: 0.2,
    }
    for product in products:
        distance = _tier_boundary_distance(
            product.get("quality_score_v4_100"),
            thresholds,
        )
        tier_factor = _tier_proximity_factor(distance)
        product["catalog_prevalence_proxy"] = prevalence[
            product["review_key"]
        ]
        product["evidence_likely_exists_factor"] = evidence_factors[
            product["bucket"]
        ]
        product["identity_reliability_factor"] = identity_factors.get(
            product["identity_confidence"],
            0.2,
        )
        product["current_evidence_zero_factor"] = 1.0
        product["tier_boundary_distance"] = distance
        product["tier_proximity_factor"] = tier_factor
        product["priority_score"] = (
            round(
                product["catalog_prevalence_proxy"]
                * product["evidence_likely_exists_factor"]
                * product["identity_reliability_factor"]
                * product["current_evidence_zero_factor"]
                * tier_factor,
                4,
            )
            if tier_factor is not None
            else None
        )


def _tier_boundary_distance(
    score: Any,
    thresholds: list[float],
) -> float | None:
    numeric_score = _as_float(score)
    if numeric_score is None or not thresholds:
        return None
    return round(min(abs(numeric_score - threshold) for threshold in thresholds), 4)


def _tier_proximity_factor(distance: float | None) -> float | None:
    if distance is None:
        return None
    if distance <= 1.0:
        return 1.0
    if distance <= 3.0:
        return 0.75
    if distance <= 5.0:
        return 0.5
    if distance <= 10.0:
        return 0.25
    return 0.1


def _build_review_groups(
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for product in products:
        grouped[(product["bucket"], product["review_key"])].append(product)

    rows: list[dict[str, Any]] = []
    for (bucket, review_key), group in grouped.items():
        priorities = [
            float(product["priority_score"])
            for product in group
            if product.get("priority_score") is not None
        ]
        distances = [
            float(product["tier_boundary_distance"])
            for product in group
            if product.get("tier_boundary_distance") is not None
        ]
        identity_counts = Counter(
            product.get("identity_confidence") or "unknown"
            for product in group
        )
        rows.append({
            "bucket": bucket,
            "review_key": review_key,
            "product_count": len(group),
            "max_priority_score": max(priorities) if priorities else None,
            "closest_tier_boundary": min(distances) if distances else None,
            "identity_confidence_counts": dict(sorted(identity_counts.items())),
            "sample_dsld_ids": sorted(
                (product["dsld_id"] for product in group),
                key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
            )[:10],
        })
    rows.sort(key=lambda row: (
        -(row["max_priority_score"] or 0.0),
        row["bucket"],
        row["review_key"],
    ))
    return rows


def _is_stage3_zero_evidence(product: dict[str, Any]) -> bool:
    if product.get("quality_score_status") != "scored":
        return False
    pillars = product.get("_v4_pillars") or product.get("quality_pillars_v4")
    if isinstance(pillars, dict):
        evidence = pillars.get("evidence")
        if isinstance(evidence, dict):
            return _as_float(evidence.get("score")) == 0.0
    metadata = _evidence_metadata(product)
    module = product.get("_v4_module_breakdown")
    dimensions = module.get("dimensions") if isinstance(module, dict) else None
    evidence = dimensions.get("evidence") if isinstance(dimensions, dict) else None
    return (
        bool(metadata)
        and isinstance(evidence, dict)
        and _as_float(evidence.get("score")) == 0.0
    )


def _review_decision_index(
    decisions: Iterable[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    invalid = 0
    for decision in decisions:
        if not _valid_review_decision(decision):
            invalid += 1
            continue
        normalized = dict(decision)
        normalized["id"] = str(decision["id"]).strip()
        for identity in decision["identity_keys"]:
            key = _norm(identity)
            if key:
                index[key].append(normalized)
    return index, invalid


def _valid_review_decision(decision: Any) -> bool:
    if not isinstance(decision, dict):
        return False
    if decision.get("review_status") != "verified":
        return False
    if decision.get("bucket") not in FINAL_REVIEW_BUCKETS:
        return False
    for field in ("id", "reviewed_by", "reviewed_on"):
        if not str(decision.get(field) or "").strip():
            return False
    identity_keys = decision.get("identity_keys")
    if not isinstance(identity_keys, list) or not any(
        _norm(identity) for identity in identity_keys
    ):
        return False
    sources = decision.get("sources")
    if not isinstance(sources, list) or not sources:
        return False
    return all(
        isinstance(source, dict)
        and source.get("verification") == "content_verified"
        and (
            str(source.get("pmid") or "").strip()
            or str(source.get("doi") or "").strip()
            or str(source.get("url") or "").strip()
        )
        for source in sources
    )


def _evidence_identity_index(
    entries: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "").strip()
        if not entry_id:
            continue
        if entry_id.upper().startswith("BRAND_"):
            # Brand records often carry a generic ingredient alias for search
            # recall. That alias is not proof that an unbranded product used
            # the clinically tested branded material.
            names = [
                entry.get("standard_name"),
                *(entry.get("brand_tokens") or []),
            ]
        else:
            names = [
                entry.get("standard_name"),
                *(entry.get("aliases") or []),
            ]
        for name in names:
            key = _norm(name)
            if key:
                index[key].append({**entry, "id": entry_id})
    return index


def _evidence_metadata(scored_product: dict[str, Any]) -> dict[str, Any]:
    module = scored_product.get("_v4_module_breakdown")
    if not isinstance(module, dict):
        return {}
    dimensions = module.get("dimensions")
    if not isinstance(dimensions, dict):
        return {}
    evidence = dimensions.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    metadata = evidence.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    generic = metadata.get("generic_evidence_metadata")
    if not isinstance(generic, dict):
        return metadata

    merged = {**metadata, **generic}
    for field in ("flags", "sub_clinical_canonicals"):
        merged[field] = sorted({
            str(value)
            for source in (metadata, generic)
            for value in source.get(field) or []
            if str(value).strip()
        })
    return merged


def _dose_form_population_reasons(metadata: dict[str, Any]) -> list[str]:
    reasons = {
        str(flag)
        for flag in metadata.get("flags") or []
        if str(flag) in {
            "SUB_CLINICAL_DOSE_DETECTED",
            "SUPRA_CLINICAL_DOSE",
        }
    }
    reasons.update(
        f"sub_clinical:{canonical}"
        for canonical in metadata.get("sub_clinical_canonicals") or []
        if canonical
    )
    return sorted(reasons)


def _is_verified_human_entry(entry: dict[str, Any]) -> bool:
    if not entry.get("references_structured"):
        return False
    study_type = _norm(entry.get("study_type")).replace(" ", "_")
    evidence_level = _norm(entry.get("evidence_level")).replace(" ", "_")
    return (
        study_type
        not in {"reference", "animal_study", "in_vitro"}
        and evidence_level not in {"reference", "preclinical"}
    )


def _is_score_eligible_human_entry(entry: dict[str, Any]) -> bool:
    if not _is_verified_human_entry(entry):
        return False
    effect = _norm(entry.get("effect_direction") or "positive_strong")
    return effect != "negative"


def _catalog_identity_names(product: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    nutrients = _json_value(product.get("key_nutrients_summary"), [])
    if isinstance(nutrients, list):
        for row in nutrients:
            if isinstance(row, dict) and row.get("name"):
                names.add(str(row["name"]))

    fingerprint = _json_value(product.get("ingredient_fingerprint"), {})
    if isinstance(fingerprint, dict):
        nutrient_map = fingerprint.get("nutrients")
        if isinstance(nutrient_map, dict):
            names.update(str(name) for name in nutrient_map)
        herbs = fingerprint.get("herbs")
        if isinstance(herbs, list):
            names.update(str(name) for name in herbs if name)
    return names


def _detail_identity_names(product: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    ingredients = product.get("ingredients")
    if not isinstance(ingredients, list):
        return names
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            continue
        role = _norm(ingredient.get("role"))
        if role and role not in {"active", "major", "claim prominent"}:
            continue
        for field in (
            "canonical_id",
            "standard_name",
            "standardName",
            "name",
            "source_label_name",
        ):
            value = ingredient.get(field)
            if value:
                names.add(str(value))
    return names


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return value if value is not None else fallback


def _dsld_id(product: dict[str, Any]) -> str:
    value = product.get("dsld_id")
    return str(value).strip() if value is not None else ""


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _load_catalog_products(db_path: Path) -> list[dict[str, Any]]:
    columns = (
        "dsld_id",
        "product_name",
        "brand_name",
        "v4_module",
        "quality_score_status",
        "quality_score_v4_100",
        "quality_tier",
        "pillar_evidence_v4",
        "key_nutrients_summary",
        "ingredient_fingerprint",
    )
    with sqlite3.connect(str(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        available = {
            row[1]
            for row in connection.execute("PRAGMA table_info(products_core)")
        }
        missing = sorted(set(columns) - available)
        if missing:
            raise ValueError(
                f"products_core missing evidence-triage columns: {missing}"
            )
        rows = connection.execute(
            f"SELECT {', '.join(columns)} FROM products_core"
        ).fetchall()
    return [dict(row) for row in rows]


def _load_scored_products(scored_root: Path) -> tuple[
    list[dict[str, Any]],
    list[Path],
]:
    files = sorted(
        path
        for path in scored_root.glob("**/scored/scored_*.json")
        if path.is_file()
    )
    if not files:
        raise FileNotFoundError(
            f"no Stage-3 scored JSON files found under {scored_root}"
        )
    products: list[dict[str, Any]] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not all(
            isinstance(product, dict) for product in payload
        ):
            raise ValueError(f"{path} is not a Stage-3 product array")
        products.extend(payload)
    return products, files


def _load_detail_products(
    detail_blobs_dir: Path,
    dsld_ids: Iterable[str],
) -> tuple[list[dict[str, Any]], list[Path]]:
    products: list[dict[str, Any]] = []
    files: list[Path] = []
    for dsld_id in sorted(set(dsld_ids)):
        path = detail_blobs_dir / f"{dsld_id}.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path} is not a product detail object")
        products.append(payload)
        files.append(path)
    return products, files


def _load_evidence_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = (
        payload.get("backed_clinical_studies")
        if isinstance(payload, dict)
        else payload
    )
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) for entry in entries
    ):
        raise ValueError(f"{path} has no backed_clinical_studies array")
    return entries


def _load_review_decisions(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = (
        payload.get("decisions") if isinstance(payload, dict) else payload
    )
    if not isinstance(decisions, list):
        raise ValueError(f"{path} has no decisions array")
    return decisions


def _load_tier_thresholds(path: Path) -> list[float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tiers = payload.get("tiers") if isinstance(payload, dict) else None
    if not isinstance(tiers, list):
        raise ValueError(f"{path} has no tiers array")
    thresholds: list[float] = []
    for tier in tiers:
        if not isinstance(tier, dict):
            raise ValueError(f"{path} contains a malformed tier")
        minimum = _as_float(tier.get("min"))
        if minimum is None:
            raise ValueError(f"{path} contains a non-numeric tier minimum")
        thresholds.append(minimum)
    return thresholds


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scored_input_fingerprint(files: Iterable[Path], root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    file_count = 0
    for path in files:
        relative_path = str(path.relative_to(root))
        content_sha = _sha256(path)
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content_sha.encode("ascii"))
        digest.update(b"\n")
        file_count += 1
    return {
        "file_count": file_count,
        "aggregate_sha256": digest.hexdigest(),
    }


def _write_products_csv(path: Path, products: list[dict[str, Any]]) -> None:
    fields = (
        "dsld_id",
        "product_name",
        "brand_name",
        "v4_module",
        "quality_score_v4_100",
        "quality_tier",
        "bucket",
        "review_decision_id",
        "conflicting_review_decision_ids",
        "matched_evidence_entry_ids",
        "matched_verified_human_entry_ids",
        "matched_score_eligible_human_entry_ids",
        "dose_form_population_reasons",
        "candidate_identity_keys",
        "identity_confidence",
        "identity_drivers",
        "review_key",
        "catalog_prevalence_proxy",
        "evidence_likely_exists_factor",
        "identity_reliability_factor",
        "current_evidence_zero_factor",
        "tier_boundary_distance",
        "tier_proximity_factor",
        "priority_score",
        "stage3_context_present",
        "detail_blob_context_present",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()
        for product in products:
            row = {field: product.get(field) for field in fields}
            for field in (
                "matched_evidence_entry_ids",
                "matched_verified_human_entry_ids",
                "matched_score_eligible_human_entry_ids",
                "conflicting_review_decision_ids",
                "dose_form_population_reasons",
                "candidate_identity_keys",
                "identity_drivers",
            ):
                row[field] = json.dumps(row[field], separators=(",", ":"))
            writer.writerow(row)


def _write_review_groups_csv(
    path: Path,
    review_groups: list[dict[str, Any]],
) -> None:
    fields = (
        "bucket",
        "review_key",
        "product_count",
        "max_priority_score",
        "closest_tier_boundary",
        "identity_confidence_counts",
        "sample_dsld_ids",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()
        for group in review_groups:
            row = {field: group.get(field) for field in fields}
            for field in ("identity_confidence_counts", "sample_dsld_ids"):
                row[field] = json.dumps(row[field], separators=(",", ":"))
            writer.writerow(row)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify released zero-Evidence products without changing scores"
        )
    )
    parser.add_argument("--catalog-db", required=True, type=Path)
    parser.add_argument("--scored-root", required=True, type=Path)
    parser.add_argument("--detail-blobs-dir", required=True, type=Path)
    parser.add_argument("--evidence-db", required=True, type=Path)
    parser.add_argument("--scoring-config", required=True, type=Path)
    parser.add_argument("--review-decisions", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    catalog_products = _load_catalog_products(args.catalog_db)
    scored_products, scored_files = _load_scored_products(args.scored_root)
    released_zero_ids = [
        _dsld_id(product)
        for product in catalog_products
        if product.get("quality_score_status") == "scored"
        and _as_float(product.get("pillar_evidence_v4")) == 0.0
    ]
    detail_products, detail_files = _load_detail_products(
        args.detail_blobs_dir,
        released_zero_ids,
    )
    evidence_entries = _load_evidence_entries(args.evidence_db)
    tier_thresholds = _load_tier_thresholds(args.scoring_config)
    review_decisions = _load_review_decisions(args.review_decisions)

    report = build_triage_report(
        catalog_products,
        scored_products,
        evidence_entries,
        review_decisions=review_decisions,
        tier_thresholds=tier_thresholds,
        detail_products=detail_products,
    )
    report["inputs"] = {
        "catalog_db": {
            "path": str(args.catalog_db),
            "sha256": _sha256(args.catalog_db),
        },
        "scored_artifacts": _scored_input_fingerprint(
            scored_files,
            args.scored_root,
        ),
        "detail_blobs": _scored_input_fingerprint(
            detail_files,
            args.detail_blobs_dir,
        ),
        "evidence_db": {
            "path": str(args.evidence_db),
            "sha256": _sha256(args.evidence_db),
        },
        "scoring_config": {
            "path": str(args.scoring_config),
            "sha256": _sha256(args.scoring_config),
        },
        "review_decisions": (
            {
                "path": str(args.review_decisions),
                "sha256": _sha256(args.review_decisions),
            }
            if args.review_decisions is not None
            else None
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        key: value
        for key, value in report.items()
        if key != "products"
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_products_csv(args.output_dir / "products.csv", report["products"])
    _write_review_groups_csv(
        args.output_dir / "review_groups.csv",
        report["review_groups"],
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
