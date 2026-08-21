#!/usr/bin/env python3
"""Measure schema-3 payload savings and prove warning-copy equivalence.

The input is a complete schema-2.x candidate build. Ownership comes from the
candidate's products_core table, not a loose directory glob: missing or extra
detail blobs are rejected before accounting begins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from export_schema import project_detail_blob, resolve_warning_rule_refs  # noqa: E402


_AUDIT_KEYS = (
    "non_gmo_audit",
    "omega3_audit",
    "proprietary_blend_audit",
    "supplement_type_audit",
    "audit",
)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _field_bytes(key: str, value: Any) -> int:
    # Minus the two outer object braces. This is exact for a standalone field
    # and intentionally excludes the separator shared with adjacent fields.
    return max(0, len(_json_bytes({key: value})) - 2)


def _load_rules(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("_metadata") if isinstance(payload, dict) else None
    rules = payload.get("interaction_rules") if isinstance(payload, dict) else None
    if not isinstance(metadata, dict) or not isinstance(rules, list):
        raise ValueError("profile warning registry requires metadata and rules")
    if metadata.get("total_entries") != len(rules):
        raise ValueError("profile warning registry total_entries mismatch")
    by_id: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("profile warning registry contains a non-object")
        rule_id = str(rule.get("id") or "").strip()
        if not rule_id or rule_id in by_id:
            raise ValueError("profile warning registry ids must be unique/nonempty")
        by_id[rule_id] = rule
    return by_id


def _owned_blob_paths(build_dir: Path, manifest: dict[str, Any]) -> list[Path]:
    db_path = build_dir / "pharmaguide_core.db"
    blob_dir = build_dir / "detail_blobs"
    if not db_path.is_file() or not blob_dir.is_dir():
        raise ValueError("candidate requires pharmaguide_core.db and detail_blobs/")
    conn = sqlite3.connect(db_path)
    try:
        owned_ids = {
            str(row[0])
            for row in conn.execute("SELECT dsld_id FROM products_core")
        }
    finally:
        conn.close()
    actual_paths = sorted(blob_dir.glob("*.json"), key=lambda path: path.name)
    actual_ids = {path.stem for path in actual_paths}
    declared_count = manifest.get("detail_blob_count")
    if (
        actual_ids != owned_ids
        or declared_count != len(owned_ids)
        or len(actual_paths) != len(owned_ids)
    ):
        missing = sorted(owned_ids - actual_ids)[:20]
        extra = sorted(actual_ids - owned_ids)[:20]
        raise ValueError(
            "detail blob manifest ownership mismatch: "
            f"declared={declared_count!r} core={len(owned_ids)} "
            f"files={len(actual_paths)} missing={missing} extra={extra}"
        )
    return actual_paths


def _new_family_report() -> dict[str, dict[str, int]]:
    return {
        name: {"occurrences": 0, "bytes": 0}
        for name in (
            "ingredient_safety_hits",
            "rda_duplicates",
            "interaction_warning_prose",
            "warnings_profile_gated_duplicate",
            "legacy_section_breakdown",
            "row_ledger_diagnostics",
            "audit_diagnostics",
            "product_status_alias",
            "synergy_id_alias",
        )
    }


def _add_family(
    families: dict[str, dict[str, int]],
    family: str,
    key: str,
    value: Any,
) -> None:
    families[family]["occurrences"] += 1
    families[family]["bytes"] += _field_bytes(key, value)


def _account_removed_families(
    blob: dict[str, Any],
    projected: dict[str, Any],
    families: dict[str, dict[str, int]],
) -> None:
    ingredients = blob.get("ingredients")
    if isinstance(ingredients, list):
        for row in ingredients:
            if isinstance(row, dict) and "safety_hits" in row:
                _add_family(
                    families,
                    "ingredient_safety_hits",
                    "safety_hits",
                    row["safety_hits"],
                )

    rda = blob.get("rda_ul_data")
    if isinstance(rda, dict):
        for key in ("ingredients_with_rda", "adequacy_results"):
            if key in rda:
                _add_family(families, "rda_duplicates", key, rda[key])
        rows = rda.get("analyzed_ingredients")
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for key in ("data_by_group", "reference_data", "reference_matrix"):
                    if key in row:
                        _add_family(families, "rda_duplicates", key, row[key])

    source_interactions = [
        warning
        for warning in blob.get("warnings", [])
        if isinstance(warning, dict)
        and str(warning.get("source") or "") == "interaction_rules"
    ]
    refs = projected.get("warning_rule_refs")
    refs = refs if isinstance(refs, list) else []
    for index, warning in enumerate(source_interactions):
        source_size = len(_json_bytes(warning))
        ref_size = len(_json_bytes(refs[index])) if index < len(refs) else 0
        families["interaction_warning_prose"]["occurrences"] += 1
        families["interaction_warning_prose"]["bytes"] += max(
            0, source_size - ref_size
        )

    for key, family in (
        ("warnings_profile_gated", "warnings_profile_gated_duplicate"),
        ("section_breakdown", "legacy_section_breakdown"),
        ("row_ledger", "row_ledger_diagnostics"),
        ("row_ledger_summary", "row_ledger_diagnostics"),
        ("product_status", "product_status_alias"),
    ):
        if key in blob:
            _add_family(families, family, key, blob[key])
    for key in _AUDIT_KEYS:
        if key in blob:
            _add_family(families, "audit_diagnostics", key, blob[key])

    synergy = blob.get("synergy_detail")
    if isinstance(synergy, dict):
        clusters = synergy.get("clusters")
        if isinstance(clusters, list):
            for cluster in clusters:
                if isinstance(cluster, dict) and "id" in cluster:
                    _add_family(
                        families, "synergy_id_alias", "id", cluster["id"]
                    )


def build_schema3_payload_report(
    build_dir: Path,
    profile_warning_rules_path: Path,
) -> dict[str, Any]:
    build_dir = Path(build_dir)
    manifest_path = build_dir / "export_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("candidate is missing export_manifest.json")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    source_schema = str(manifest.get("schema_version") or "").strip()
    if not source_schema.startswith("2."):
        raise ValueError(
            f"schema-3 projection report requires a schema-2 source, got {source_schema!r}"
        )

    rules_by_id = _load_rules(Path(profile_warning_rules_path))
    paths = _owned_blob_paths(build_dir, manifest)
    families = _new_family_report()
    source_bytes = 0
    projected_bytes = 0
    checked_warnings = 0
    warning_failure_count = 0
    warning_failures: list[dict[str, Any]] = []
    fingerprint = hashlib.sha256()
    fingerprint.update(manifest_bytes)

    for path in paths:
        raw = path.read_bytes()
        fingerprint.update(path.name.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(hashlib.sha256(raw).digest())
        blob = json.loads(raw)
        if not isinstance(blob, dict):
            raise ValueError(f"detail blob {path.name} is not an object")
        projected = project_detail_blob(blob, export_schema_version="3.0.0")
        source_bytes += len(raw)
        projected_bytes += len(_json_bytes(projected))
        _account_removed_families(blob, projected, families)

        original_interactions = [
            warning
            for warning in blob.get("warnings", [])
            if isinstance(warning, dict)
            and str(warning.get("source") or "") == "interaction_rules"
        ]
        checked_warnings += len(original_interactions)
        try:
            refs = projected.get("warning_rule_refs")
            refs = refs if isinstance(refs, list) else []
            resolved = resolve_warning_rule_refs(refs, rules_by_id=rules_by_id)
            if resolved != original_interactions:
                raise ValueError("resolved interaction warning differs from source")

            profile_rows = blob.get("warnings_profile_gated")
            if isinstance(profile_rows, list):
                for profile_row in profile_rows:
                    if isinstance(profile_row, dict) and profile_row not in blob.get(
                        "warnings", []
                    ):
                        raise ValueError(
                            "profile-gated warning is not duplicated in canonical warnings"
                        )
        except (TypeError, ValueError) as exc:
            warning_failure_count += 1
            if len(warning_failures) < 50:
                warning_failures.append(
                    {"dsld_id": path.stem, "error": str(exc)}
                )

    saved = source_bytes - projected_bytes
    return {
        "source_schema_version": source_schema,
        "target_schema_version": "3.0.0",
        "product_count": len(paths),
        "input_fingerprint_sha256": fingerprint.hexdigest(),
        "bytes": {
            "schema2": source_bytes,
            "schema3": projected_bytes,
            "saved": saved,
            "reduction_pct": round(
                (saved / source_bytes * 100.0) if source_bytes else 0.0, 4
            ),
        },
        "removed_families": families,
        "warning_equivalence": {
            "checked": checked_warnings,
            "failures": warning_failure_count,
            "failure_samples": warning_failures,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument(
        "--profile-warning-rules",
        type=Path,
        default=SCRIPT_DIR / "data" / "ingredient_interaction_rules.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = build_schema3_payload_report(
        args.build_dir, args.profile_warning_rules
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["bytes"], sort_keys=True))
    return 1 if report["warning_equivalence"]["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
