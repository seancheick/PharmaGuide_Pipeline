#!/usr/bin/env python3
"""Audit pipeline ↔ Flutter release artifact contracts.

This is intentionally artifact-first. It reads the SQLite files, manifests,
detail indexes, and bundled Flutter assets that would actually ship. It does
not trust docs or generated release notes.

Default scope is local-only:
  - scripts/final_db_output
  - scripts/dist
  - /Users/seancheick/PharmaGuide ai/assets/db

Exit code is non-zero when any BLOCKER/HIGH finding is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


JSON_COLUMNS = (
    "ingredient_fingerprint",
    "key_ingredient_tags",
    "key_nutrients_summary",
    "top_warnings",
    "flags",
    "badges",
    "goal_matches",
    "secondary_categories",
    "share_highlights",
    "cert_programs",
    "decision_highlights",
    "interaction_summary_hint",
)

BLOCKING_WARNING_TYPES = (
    "banned_substance",
    "recalled",
    "adulterant",
    "contraindicated",
    "high_risk",
)


@dataclass
class Finding:
    severity: str
    code: str
    artifact: str
    message: str
    evidence: dict[str, Any]


class Audit:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.artifacts: dict[str, Any] = {}

    def add(
        self,
        severity: str,
        code: str,
        artifact: str,
        message: str,
        **evidence: Any,
    ) -> None:
        self.findings.append(
            Finding(
                severity=severity,
                code=code,
                artifact=artifact,
                message=message,
                evidence=evidence,
            )
        )

    def has_release_blockers(self) -> bool:
        return any(f.severity in {"BLOCKER", "HIGH"} for f in self.findings)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_checksum(manifest: dict[str, Any]) -> str | None:
    raw = manifest.get("checksum_sha256") or manifest.get("checksum")
    if not raw:
        return None
    text = str(raw)
    return text.removeprefix("sha256:")


def sqlite_scalar(db_path: Path, sql: str, params: tuple[Any, ...] = ()) -> Any:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def sqlite_rows(db_path: Path, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def embedded_manifest(db_path: Path) -> dict[str, str]:
    try:
        rows = sqlite_rows(db_path, "SELECT key, value FROM export_manifest")
    except sqlite3.Error:
        return {}
    return {str(r["key"]): str(r["value"]) for r in rows}


def table_exists(db_path: Path, table: str) -> bool:
    return bool(
        sqlite_rows(
            db_path,
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    )


def audit_core_artifact(
    audit: Audit,
    *,
    name: str,
    root: Path,
    has_blobs: bool,
) -> dict[str, Any] | None:
    db_path = root / "pharmaguide_core.db"
    manifest_path = root / "export_manifest.json"
    artifact_key = f"{name}:core"
    if not db_path.exists():
        audit.add("BLOCKER", "CORE_DB_MISSING", artifact_key, "missing pharmaguide_core.db", path=str(db_path))
        return None
    if not manifest_path.exists():
        audit.add("BLOCKER", "CORE_MANIFEST_MISSING", artifact_key, "missing export_manifest.json", path=str(manifest_path))
        return None

    manifest = read_json(manifest_path)
    db_hash = sha256_file(db_path)
    expected_hash = manifest_checksum(manifest)
    if expected_hash and db_hash != expected_hash:
        audit.add(
            "BLOCKER",
            "CORE_DB_CHECKSUM_MISMATCH",
            artifact_key,
            "core DB checksum disagrees with manifest",
            actual=db_hash,
            expected=expected_hash,
        )

    integrity = sqlite_scalar(db_path, "PRAGMA integrity_check")
    if integrity != "ok":
        audit.add("BLOCKER", "CORE_SQLITE_INTEGRITY", artifact_key, "SQLite integrity_check failed", result=integrity)

    product_count = int(sqlite_scalar(db_path, "SELECT COUNT(*) FROM products_core"))
    manifest_count = int(manifest.get("product_count") or 0)
    if manifest_count and product_count != manifest_count:
        audit.add(
            "BLOCKER",
            "CORE_PRODUCT_COUNT_MISMATCH",
            artifact_key,
            "products_core count disagrees with manifest",
            actual=product_count,
            expected=manifest_count,
        )

    embedded = embedded_manifest(db_path)
    for key in ("db_version", "schema_version"):
        if manifest.get(key) and embedded.get(key) and str(manifest[key]) != embedded[key]:
            audit.add(
                "BLOCKER",
                "CORE_EMBEDDED_MANIFEST_DRIFT",
                artifact_key,
                f"{key} disagrees between JSON manifest and SQLite export_manifest",
                json_value=manifest.get(key),
                sqlite_value=embedded.get(key),
            )

    empty_tags = int(
        sqlite_scalar(
            db_path,
            """
            SELECT COUNT(*)
            FROM products_core
            WHERE key_ingredient_tags IS NULL
               OR key_ingredient_tags = ''
               OR key_ingredient_tags = '[]'
            """,
        )
    )
    if empty_tags:
        audit.add("BLOCKER", "EMPTY_KEY_INGREDIENT_TAGS", artifact_key, "shipped products have empty key_ingredient_tags", count=empty_tags)

    not_scored = int(
        sqlite_scalar(
            db_path,
            """
            SELECT COUNT(*)
            FROM products_core
            WHERE verdict = 'NOT_SCORED'
               OR safety_verdict = 'NOT_SCORED'
            """,
        )
    )
    if not_scored:
        audit.add("BLOCKER", "NOT_SCORED_SHIPPED", artifact_key, "NOT_SCORED products reached products_core", count=not_scored)

    banned_safe = int(
        sqlite_scalar(
            db_path,
            """
            SELECT COUNT(*)
            FROM products_core
            WHERE has_banned_substance = 1
              AND (verdict = 'SAFE' OR safety_verdict = 'SAFE')
            """,
        )
    )
    if banned_safe:
        audit.add("BLOCKER", "BANNED_SAFE_CONTRADICTION", artifact_key, "banned product remains SAFE", count=banned_safe)

    malformed = _audit_json_columns(db_path)
    if malformed:
        audit.add("BLOCKER", "CORE_JSON_COLUMN_MALFORMED", artifact_key, "app-required JSON columns contain malformed JSON", sample=malformed[:20], count=len(malformed))

    detail_index_count = None
    blob_count = None
    if has_blobs:
        detail_index_path = root / "detail_index.json"
        blob_dir = root / "detail_blobs"
        if not detail_index_path.exists():
            audit.add("BLOCKER", "DETAIL_INDEX_MISSING", artifact_key, "missing detail_index.json", path=str(detail_index_path))
        else:
            detail_index = read_json(detail_index_path)
            detail_index_count = len(detail_index)
            manifest_detail_count = int(manifest.get("detail_blob_count") or 0)
            if manifest_detail_count and detail_index_count != manifest_detail_count:
                audit.add(
                    "BLOCKER",
                    "DETAIL_INDEX_COUNT_MISMATCH",
                    artifact_key,
                    "detail_index count disagrees with manifest",
                    actual=detail_index_count,
                    expected=manifest_detail_count,
                )
            if detail_index_count != product_count:
                audit.add(
                    "BLOCKER",
                    "DETAIL_INDEX_PRODUCT_COUNT_MISMATCH",
                    artifact_key,
                    "detail_index count disagrees with products_core count",
                    detail_index_count=detail_index_count,
                    product_count=product_count,
                )
        if not blob_dir.is_dir():
            audit.add("BLOCKER", "DETAIL_BLOBS_MISSING", artifact_key, "missing detail_blobs directory", path=str(blob_dir))
        else:
            blob_count = len(list(blob_dir.glob("*.json")))
            if blob_count != product_count:
                audit.add(
                    "BLOCKER",
                    "DETAIL_BLOB_COUNT_MISMATCH",
                    artifact_key,
                    "detail_blobs file count disagrees with products_core count",
                    blob_count=blob_count,
                    product_count=product_count,
                )

    summary = {
        "db_path": str(db_path),
        "manifest_path": str(manifest_path),
        "db_version": manifest.get("db_version"),
        "schema_version": manifest.get("schema_version"),
        "product_count": product_count,
        "db_sha256": db_hash,
        "manifest_sha256": expected_hash,
        "detail_index_count": detail_index_count,
        "detail_blob_count": blob_count,
        "empty_key_ingredient_tags": empty_tags,
        "not_scored": not_scored,
        "banned_safe": banned_safe,
    }
    audit.artifacts[artifact_key] = summary
    return summary


def _audit_json_columns(db_path: Path) -> list[dict[str, Any]]:
    columns = {r["name"] for r in sqlite_rows(db_path, "PRAGMA table_info(products_core)")}
    checked = [c for c in JSON_COLUMNS if c in columns]
    if not checked:
        return []
    select_cols = ", ".join(["dsld_id", *checked])
    bad: list[dict[str, Any]] = []
    for row in sqlite_rows(db_path, f"SELECT {select_cols} FROM products_core"):
        dsld_id = row["dsld_id"]
        for col in checked:
            raw = row[col]
            if raw is None or raw == "":
                continue
            try:
                json.loads(raw)
            except Exception as exc:
                bad.append({"dsld_id": dsld_id, "column": col, "error": str(exc), "value_sample": str(raw)[:120]})
    return bad


def audit_artifact_alignment(audit: Audit, summaries: list[dict[str, Any] | None]) -> None:
    present = [s for s in summaries if s]
    if len(present) < 2:
        return
    keys = ("db_version", "schema_version", "product_count", "db_sha256")
    baseline = present[0]
    for other in present[1:]:
        for key in keys:
            if baseline.get(key) != other.get(key):
                audit.add(
                    "BLOCKER",
                    "CORE_ARTIFACT_ALIGNMENT_DRIFT",
                    "core-alignment",
                    f"{key} differs between core artifacts",
                    baseline=baseline.get("db_path"),
                    baseline_value=baseline.get(key),
                    other=other.get("db_path"),
                    other_value=other.get(key),
                )


def audit_interaction_artifact(audit: Audit, *, name: str, root: Path) -> dict[str, Any] | None:
    db_path = root / "interaction_db.sqlite"
    manifest_path = root / "interaction_db_manifest.json"
    artifact_key = f"{name}:interaction"
    if not db_path.exists():
        audit.add("BLOCKER", "INTERACTION_DB_MISSING", artifact_key, "missing interaction_db.sqlite", path=str(db_path))
        return None
    if not manifest_path.exists():
        audit.add("BLOCKER", "INTERACTION_MANIFEST_MISSING", artifact_key, "missing interaction_db_manifest.json", path=str(manifest_path))
        return None

    manifest = read_json(manifest_path)
    db_hash = sha256_file(db_path)
    expected_hash = manifest_checksum(manifest)
    if expected_hash and db_hash != expected_hash:
        audit.add("BLOCKER", "INTERACTION_CHECKSUM_MISMATCH", artifact_key, "interaction DB checksum disagrees with manifest", actual=db_hash, expected=expected_hash)

    integrity = sqlite_scalar(db_path, "PRAGMA integrity_check")
    if integrity != "ok":
        audit.add("BLOCKER", "INTERACTION_SQLITE_INTEGRITY", artifact_key, "interaction SQLite integrity_check failed", result=integrity)

    user_version = int(sqlite_scalar(db_path, "PRAGMA user_version"))
    if user_version != 1:
        audit.add("BLOCKER", "INTERACTION_USER_VERSION_DRIFT", artifact_key, "interaction DB PRAGMA user_version is unsupported", actual=user_version, expected=1)

    required_tables = {"interactions", "drug_class_map", "research_pairs", "interaction_db_metadata"}
    missing_tables = sorted(t for t in required_tables if not table_exists(db_path, t))
    if missing_tables:
        audit.add("BLOCKER", "INTERACTION_TABLES_MISSING", artifact_key, "interaction DB required tables missing", missing_tables=missing_tables)
        return None

    live_interactions = int(sqlite_scalar(db_path, "SELECT COUNT(*) FROM interactions WHERE retired_at IS NULL"))
    manifest_total = int(manifest.get("total_interactions") or 0)
    if manifest_total and live_interactions != manifest_total:
        audit.add("BLOCKER", "INTERACTION_COUNT_MISMATCH", artifact_key, "live interaction count disagrees with manifest", actual=live_interactions, expected=manifest_total)

    metadata = {r["key"]: r["value"] for r in sqlite_rows(db_path, "SELECT key, value FROM interaction_db_metadata")}
    for key in ("schema_version", "total_interactions"):
        if key in manifest and key in metadata and str(manifest[key]) != str(metadata[key]):
            audit.add("BLOCKER", "INTERACTION_METADATA_DRIFT", artifact_key, f"{key} disagrees between JSON manifest and SQLite metadata", json_value=manifest[key], sqlite_value=metadata[key])

    bad_severities = [
        r["severity"]
        for r in sqlite_rows(
            db_path,
            """
            SELECT DISTINCT severity
            FROM interactions
            WHERE retired_at IS NULL
              AND severity NOT IN ('contraindicated', 'avoid', 'caution', 'monitor', 'safe')
            """,
        )
    ]
    if bad_severities:
        audit.add("BLOCKER", "INTERACTION_SEVERITY_UNKNOWN", artifact_key, "interaction DB emits severities Flutter may not parse", severities=bad_severities)

    research_pairs = int(sqlite_scalar(db_path, "SELECT COUNT(*) FROM research_pairs"))
    research_rxcui = int(
        sqlite_scalar(
            db_path,
            """
            SELECT COUNT(*)
            FROM research_pairs
            WHERE COALESCE(rxcui_a, '') != ''
               OR COALESCE(rxcui_b, '') != ''
            """,
        )
    )
    if research_pairs and research_rxcui == 0:
        audit.add(
            "MEDIUM",
            "TIER2_RESEARCH_RXCUI_BRIDGE_EMPTY",
            artifact_key,
            "research_pairs are bundled but have no RxCUI bridge; Tier 2 is not reachable by medication RxCUI",
            research_pairs=research_pairs,
        )

    summary = {
        "db_path": str(db_path),
        "manifest_path": str(manifest_path),
        "schema_version": manifest.get("schema_version"),
        "db_version": manifest.get("db_version"),
        "db_sha256": db_hash,
        "manifest_sha256": expected_hash,
        "user_version": user_version,
        "live_interactions": live_interactions,
        "research_pairs": research_pairs,
        "research_pairs_with_any_rxcui": research_rxcui,
    }
    audit.artifacts[artifact_key] = summary
    return summary


def audit_previous_assets(audit: Audit, flutter_root: Path) -> None:
    asset_dir = flutter_root / "assets" / "db"
    previous = sorted(str(p.relative_to(flutter_root)) for p in asset_dir.glob("*.previous"))
    if previous:
        audit.add(
            "LOW",
            "FLUTTER_PREVIOUS_DB_ARTIFACTS",
            "flutter:assets_db",
            "generated .previous DB artifacts remain in assets/db",
            files=previous,
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--flutter-root", type=Path, default=Path("/Users/seancheick/PharmaGuide ai"))
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--output", type=Path, help="optional path to write JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    pipeline_root: Path = args.pipeline_root
    flutter_root: Path = args.flutter_root

    audit = Audit()
    summaries = [
        audit_core_artifact(audit, name="final_db_output", root=pipeline_root / "final_db_output", has_blobs=True),
        audit_core_artifact(audit, name="dist", root=pipeline_root / "dist", has_blobs=True),
        audit_core_artifact(audit, name="flutter_assets", root=flutter_root / "assets" / "db", has_blobs=False),
    ]
    audit_artifact_alignment(audit, summaries)
    audit_interaction_artifact(audit, name="dist", root=pipeline_root / "dist")
    audit_interaction_artifact(audit, name="flutter_assets", root=flutter_root / "assets" / "db")
    audit_previous_assets(audit, flutter_root)

    report = {
        "status": "FAIL" if audit.has_release_blockers() else "PASS",
        "release_blocker_count": sum(1 for f in audit.findings if f.severity in {"BLOCKER", "HIGH"}),
        "finding_count": len(audit.findings),
        "artifacts": audit.artifacts,
        "findings": [asdict(f) for f in audit.findings],
    }

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if args.json:
        print(rendered)
    else:
        print(f"status={report['status']} release_blockers={report['release_blocker_count']} findings={report['finding_count']}")
        for f in audit.findings:
            print(f"{f.severity} {f.code} [{f.artifact}] {f.message}")
    return 1 if audit.has_release_blockers() else 0


if __name__ == "__main__":
    raise SystemExit(main())
