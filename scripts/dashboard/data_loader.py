from __future__ import annotations

import ast
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


DEFAULT_ALERT_THRESHOLDS = {
    "coverage_min_pct": 95,
    "max_errors": 0,
    "ban_increase_alert": True,
    "max_unmapped": 100,
    "max_build_age_days": 7,
    "max_sync_lag_hours": 24,
}

VERDICT_ORDER = ["SAFE", "CAUTION", "POOR", "UNSAFE", "BLOCKED", "NOT_SCORED"]
SAFETY_COUNT_KEYS = [
    "has_banned_substance",
    "has_recalled_ingredient",
    "has_harmful_additives",
    "has_allergen_risks",
    "has_watchlist_hit",
    "has_high_risk_hit",
]


@dataclass
class DashboardData:
    db_path: Path | None = None
    db_conn: sqlite3.Connection | None = None
    export_manifest: dict[str, Any] | None = None
    export_audit: dict[str, Any] | None = None
    detail_index: dict[str, Any] | None = None
    detail_blobs_dir: Path | None = None

    enrichment_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    scoring_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    coverage_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    form_fallback_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    parent_fallback_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    dataset_reports: dict[str, dict[str, Any]] = field(default_factory=dict)

    processing_state: dict[str, Any] | None = None
    scoring_config: dict[str, Any] | None = None
    batch_run_files: list[Path] = field(default_factory=list)
    batch_history: list[dict[str, Any]] = field(default_factory=list)
    latest_batch_summary: dict[str, Any] | None = None

    latest_enriched_at: datetime | None = None
    latest_scored_at: datetime | None = None
    latest_export_at: datetime | None = None
    latest_batch_at: datetime | None = None

    scan_dir: Path = Path(".")
    build_root: Path = Path(".")
    dataset_root: Path | None = None
    discovered_datasets: list[str] = field(default_factory=list)
    missing_artifacts: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    release_artifact_status: dict[str, Any] = field(default_factory=dict)

    integrity_data: dict[str, Any] | None = None
    remote_manifest: dict[str, Any] | None = None
    sync_failures: list[dict[str, Any]] = field(default_factory=list)
    storage_health: dict[str, Any] | None = None

    build_history: list[dict[str, Any]] = field(default_factory=list)
    alert_thresholds: dict[str, Any] = field(default_factory=dict)
    shared_metrics: dict[str, Any] = field(default_factory=dict)
    blob_analytics: dict[str, Any] = field(default_factory=dict)
    product_catalog: pd.DataFrame = field(default_factory=pd.DataFrame)

    caers_signals: dict[str, Any] = field(default_factory=dict)
    caers_metadata: dict[str, Any] = field(default_factory=dict)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _parse_report_filename_timestamp(path: Path) -> datetime | None:
    match = re.search(r"(\d{8}_\d{6})", path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_processing_summary_generated_at(text: str | None) -> datetime | None:
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("Generated:"):
            generated = line.split("Generated:", 1)[1].strip().replace(" ", "T")
            try:
                parsed = datetime.fromisoformat(generated)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                local_tz = datetime.now().astimezone().tzinfo or timezone.utc
                parsed = parsed.replace(tzinfo=local_tz)
            return parsed.astimezone(timezone.utc)
    return None


def _report_timestamp(path: Path, content: dict[str, Any] | None = None, text: str | None = None) -> datetime | None:
    candidates = []
    if content:
        for key in ("generated_at", "completed_at", "last_updated", "timestamp", "created_at"):
            parsed = _parse_datetime(content.get(key))
            if parsed:
                candidates.append(parsed)
    summary_generated = _parse_processing_summary_generated_at(text)
    if summary_generated:
        candidates.append(summary_generated)
    filename_timestamp = _parse_report_filename_timestamp(path)
    if filename_timestamp:
        candidates.append(filename_timestamp)
    if candidates:
        return max(candidates)
    return _mtime(path)


@st.cache_resource
def get_sqlite_connection(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _dashboard_root() -> Path:
    return Path(__file__).resolve().parent


def _load_alert_thresholds() -> dict[str, Any]:
    alert_path = _dashboard_root() / "dashboard_alerts.json"
    data = safe_load_json(alert_path)
    if not data:
        return dict(DEFAULT_ALERT_THRESHOLDS)
    merged = dict(DEFAULT_ALERT_THRESHOLDS)
    merged.update(data)
    return merged


def _discover_build_history(build_root: Path, dataset_root: Path | None) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add_candidate(root: Path) -> None:
        manifest_path = root / "export_manifest.json"
        db_path = root / "pharmaguide_core.db"
        audit_path = root / "export_audit_report.json"
        if not manifest_path.exists() and not db_path.exists():
            return
        manifest = safe_load_json(manifest_path) or {}
        audit = safe_load_json(audit_path) or {}
        counts = audit.get("counts", {})
        generated_at = _parse_datetime(manifest.get("generated_at")) or _mtime(manifest_path) or _mtime(db_path)
        label = manifest.get("db_version") or root.name
        candidates[str(root.resolve())] = {
            "label": label,
            "build_root": root.resolve(),
            "manifest_path": manifest_path.resolve() if manifest_path.exists() else None,
            "db_path": db_path.resolve() if db_path.exists() else None,
            "audit_path": audit_path.resolve() if audit_path.exists() else None,
            "generated_at": generated_at,
            "product_count": manifest.get("product_count"),
            "scoring_version": manifest.get("scoring_version"),
            "pipeline_version": manifest.get("pipeline_version"),
            "detail_blob_count": manifest.get("detail_blob_count"),
            "error_count": counts.get("total_errors", 0),
            "enriched_only_count": counts.get("enriched_only", 0),
            "scored_only_count": counts.get("scored_only", 0),
            "manifest": manifest,
            "audit": audit,
        }

    add_candidate(build_root)
    parent = build_root.parent
    if parent.exists():
        for child in parent.iterdir():
            if child.is_dir():
                add_candidate(child)
    if dataset_root:
        builds_dir = dataset_root / "builds"
        if builds_dir.exists():
            for child in builds_dir.iterdir():
                if child.is_dir():
                    add_candidate(child)

    history = list(candidates.values())
    history.sort(key=lambda item: item.get("generated_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return history


def _discover_output_dirs(scan_dir: Path) -> list[Path]:
    return sorted([path for path in scan_dir.glob("output_*") if path.is_dir()])


def _dataset_name(output_dir: Path) -> str:
    return output_dir.name.replace("output_", "").replace("_", " ").strip() or output_dir.name


def _load_unmapped_report(path: Path, key: str) -> list[dict[str, Any]]:
    payload = safe_load_json(path) or {}
    rows = payload.get(key, [])
    if not isinstance(rows, list):
        return []
    return rows


def _parse_dataset_report(output_dir: Path) -> dict[str, Any]:
    report_dir = output_dir / "reports"
    unmapped_dir = output_dir / "unmapped"
    cleaned_dir = output_dir / "cleaned"
    errors_dir = output_dir / "errors"

    artifacts = {
        "reports_dir": report_dir.exists(),
        "cleaned_dir": cleaned_dir.exists(),
        "errors_dir": errors_dir.exists(),
        "unmapped_dir": unmapped_dir.exists(),
    }

    processing_summary_path = report_dir / "processing_summary.txt"
    processing_summary_text = processing_summary_path.read_text() if processing_summary_path.exists() else None

    report = {
        "output_dir": output_dir,
        "artifacts": artifacts,
        "cleaned_files": sorted(cleaned_dir.glob("*.json")) if cleaned_dir.exists() else [],
        "error_files": sorted(errors_dir.glob("*_error.json")) if errors_dir.exists() else [],
        "processing_summary_path": processing_summary_path,
        "processing_summary_text": processing_summary_text,
        "unmapped_active": _load_unmapped_report(unmapped_dir / "unmapped_active_ingredients.json", "unmapped_ingredients"),
        "unmapped_inactive": _load_unmapped_report(unmapped_dir / "unmapped_inactive_ingredients.json", "unmapped_ingredients"),
        "needs_review_active": _load_unmapped_report(unmapped_dir / "needs_verification_active_ingredients.json", "ingredients"),
        "needs_review_inactive": _load_unmapped_report(unmapped_dir / "needs_verification_inactive_ingredients.json", "ingredients"),
    }
    report["cleaned_count"] = len(report["cleaned_files"])
    report["error_count"] = len(report["error_files"])
    report_file_times = []
    pipeline_report_times = []
    for path in report_dir.glob("*"):
        text = None
        content = None
        if path.suffix == ".json":
            content = safe_load_json(path)
            if not content:
                content = None
        elif path.name == "processing_summary.txt":
            text = processing_summary_text
        timestamp = _report_timestamp(path, content=content, text=text)
        if timestamp:
            report_file_times.append(timestamp)
            if content is not None or text is not None:
                pipeline_report_times.append(timestamp)
    report["latest_activity_at"] = max(
        [_mtime(output_dir)]
        + [_mtime(path) for path in report["cleaned_files"] + report["error_files"] if _mtime(path)]
        + report_file_times,
        default=None,
    )
    report["latest_pipeline_at"] = max(pipeline_report_times, default=None)
    report["missing_expected"] = [
        name for name, present in artifacts.items() if not present and name != "reports_dir"
    ]
    return report


def _extract_dataset_from_path(text: str) -> str | None:
    patterns = [
        r"/brands/([^/]+)/",
        r"/output_([^/]+)/",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace("_", " ")
    return None


def _parse_batch_summary_text(path: Path) -> dict[str, Any]:
    lines = path.read_text(errors="replace").splitlines()
    info: dict[str, Any] = {
        "path": path,
        "name": path.name,
        "kind": "batch_log",
        "summary": {},
        "datasets": {},
        "error_lines": [],
        "started": None,
        "ended": None,
    }
    for line in lines:
        if "Started:" in line:
            info["started"] = _parse_datetime(line.split("Started:", 1)[1].strip().replace(" ", "T") + "+00:00")
        elif "Ended:" in line:
            info["ended"] = _parse_datetime(line.split("Ended:", 1)[1].strip().replace(" ", "T") + "+00:00")
        elif "Summary:" in line:
            raw = line.split("Summary:", 1)[1].strip()
            try:
                info["summary"] = ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                info["summary"] = {}
        elif "ERROR -" in line:
            message = line.split("ERROR -", 1)[1].strip()
            info["error_lines"].append(message)
            dataset = _extract_dataset_from_path(message) or "Unknown"
            dataset_state = info["datasets"].setdefault(
                dataset,
                {"status": "FAILED", "last_stage": "CLEAN", "errors": []},
            )
            dataset_state["errors"].append(message)

    if not info["datasets"]:
        dataset = _extract_dataset_from_path(path.read_text(errors="replace")) or "Unknown"
        errors = info["summary"].get("errors", 0)
        info["datasets"][dataset] = {
            "status": "FAILED" if errors else "SUCCESS",
            "last_stage": "CLEAN",
            "errors": info["error_lines"],
        }

    for dataset_state in info["datasets"].values():
        dataset_state["stage_marks"] = {
            "CLEAN": dataset_state["status"] == "SUCCESS" or dataset_state["status"] == "FAILED",
            "ENRICH": False,
            "SCORE": False,
            "EXPORT": False,
        }

    timestamp = info.get("started") or info.get("ended") or _mtime(path)
    info["timestamp"] = timestamp
    return info


def _discover_batch_history(scan_dir: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    batch_files = sorted(scan_dir.glob("batch_run_summary_*.txt"))
    report_files = sorted((scan_dir / "reports").glob("batch_run_summary_*.txt")) if (scan_dir / "reports").exists() else []
    batch_logs = sorted((scan_dir / "logs").glob("batch_*_log.txt")) if (scan_dir / "logs").exists() else []
    legacy_logs = []
    parent_logs_dir = scan_dir.parent / "logs"
    if parent_logs_dir.exists() and parent_logs_dir != scan_dir / "logs":
        legacy_logs = sorted(parent_logs_dir.glob("batch_*_log.txt"))
    all_files = batch_files + report_files + batch_logs + legacy_logs
    history = [_parse_batch_summary_text(path) for path in all_files]
    history.sort(key=lambda item: item.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    sorted_files = [item["path"] for item in history]
    return sorted_files, history


def _parse_processing_summary_metrics(text: str | None) -> dict[str, Any]:
    if not text:
        return {}

    generated_at = None
    total_processed = None
    total_errors = None
    total_cleaned = None
    processing_seconds = None

    generated_match = re.search(r"Generated:\s+([0-9:\-\s]+)", text)
    if generated_match:
        generated_at = _parse_datetime(generated_match.group(1).strip().replace(" ", "T") + "+00:00")

    processed_match = re.search(r"Total Files Processed:\s+(\d+)", text)
    if processed_match:
        total_processed = int(processed_match.group(1))

    errors_match = re.search(r"Errors:\s+(\d+)", text)
    if errors_match:
        total_errors = int(errors_match.group(1))

    cleaned_match = re.search(r"Successfully cleaned:\s+(\d+)", text)
    if cleaned_match:
        total_cleaned = int(cleaned_match.group(1))

    time_match = re.search(r"Processing Time:\s+([0-9.]+)\s+minutes", text)
    if time_match:
        processing_seconds = round(float(time_match.group(1)) * 60, 2)

    return {
        "generated_at": generated_at,
        "processed": total_processed,
        "errors": total_errors,
        "cleaned": total_cleaned,
        "processing_time": processing_seconds,
    }


def _db_lookup(db_conn: sqlite3.Connection | None) -> dict[str, dict[str, Any]]:
    if db_conn is None:
        return {}
    columns = {
        row["name"]
        for row in db_conn.execute("PRAGMA table_info(products_core)").fetchall()
    }

    def select_expr(column: str, alias: str | None = None) -> str:
        target = alias or column
        return f"{column} AS {target}" if column in columns else f"NULL AS {target}"

    query = f"""
        SELECT
            {select_expr('dsld_id')},
            {select_expr('product_name')},
            {select_expr('brand_name')},
            {select_expr('score_100_equivalent')},
            {select_expr('grade')},
            {select_expr('verdict')},
            {select_expr('supplement_type')},
            {select_expr('mapped_coverage')},
            {select_expr('has_banned_substance')},
            {select_expr('has_recalled_ingredient')},
            {select_expr('has_harmful_additives')},
            {select_expr('has_allergen_risks')}
        FROM products_core
    """
    rows = db_conn.execute(query).fetchall()
    return {
        str(row["dsld_id"]): {
            "dsld_id": str(row["dsld_id"]),
            "product_name": row["product_name"],
            "brand_name": row["brand_name"],
            "score": row["score_100_equivalent"],
            "grade": row["grade"],
            "verdict": row["verdict"],
            "supplement_type": row["supplement_type"],
            "mapped_coverage": row["mapped_coverage"],
            "has_banned_substance": bool(row["has_banned_substance"]),
            "has_recalled_ingredient": bool(row["has_recalled_ingredient"]),
            "has_harmful_additives": bool(row["has_harmful_additives"]),
            "has_allergen_risks": bool(row["has_allergen_risks"]),
        }
        for row in rows
    }


def _load_product_catalog(db_conn: sqlite3.Connection | None) -> pd.DataFrame:
    if db_conn is None:
        return pd.DataFrame()

    columns = {
        row["name"]
        for row in db_conn.execute("PRAGMA table_info(products_core)").fetchall()
    }

    def select_expr(column: str, alias: str | None = None) -> str:
        target = alias or column
        return f"{column} AS {target}" if column in columns else f"NULL AS {target}"

    query = """
        SELECT
            {dsld_id},
            {product_name},
            {brand_name},
            {supplement_type},
            {primary_category},
            {verdict},
            {score_100_equivalent},
            {score_ingredient_quality},
            {score_ingredient_quality_max},
            {mapped_coverage},
            {is_non_gmo},
            {contains_omega3},
            {contains_probiotics},
            {has_banned_substance},
            {has_recalled_ingredient},
            {has_harmful_additives},
            {has_allergen_risks},
            {score_safety_purity},
            {score_safety_purity_max},
            {score_evidence_research},
            {score_evidence_research_max},
            {score_brand_trust},
            {score_brand_trust_max},
            {is_trusted_manufacturer},
            {has_third_party_testing},
            {has_full_disclosure},
            {blocking_reason}
        FROM products_core
    """.format(
        dsld_id=select_expr("dsld_id"),
        product_name=select_expr("product_name"),
        brand_name=select_expr("brand_name"),
        supplement_type=select_expr("supplement_type"),
        primary_category=select_expr("primary_category"),
        verdict=select_expr("verdict"),
        score_100_equivalent=select_expr("score_100_equivalent", "score"),
        score_ingredient_quality=select_expr("score_ingredient_quality", "section_a_score"),
        score_ingredient_quality_max=select_expr("score_ingredient_quality_max", "section_a_max"),
        mapped_coverage=select_expr("mapped_coverage"),
        is_non_gmo=select_expr("is_non_gmo"),
        contains_omega3=select_expr("contains_omega3"),
        contains_probiotics=select_expr("contains_probiotics"),
        has_banned_substance=select_expr("has_banned_substance"),
        has_recalled_ingredient=select_expr("has_recalled_ingredient"),
        has_harmful_additives=select_expr("has_harmful_additives"),
        has_allergen_risks=select_expr("has_allergen_risks"),
        score_safety_purity=select_expr("score_safety_purity", "section_b_score"),
        score_safety_purity_max=select_expr("score_safety_purity_max", "section_b_max"),
        score_evidence_research=select_expr("score_evidence_research", "section_c_score"),
        score_evidence_research_max=select_expr("score_evidence_research_max", "section_c_max"),
        score_brand_trust=select_expr("score_brand_trust", "section_d_score"),
        score_brand_trust_max=select_expr("score_brand_trust_max", "section_d_max"),
        is_trusted_manufacturer=select_expr("is_trusted_manufacturer"),
        has_third_party_testing=select_expr("has_third_party_testing"),
        has_full_disclosure=select_expr("has_full_disclosure"),
        blocking_reason=select_expr("blocking_reason"),
    )
    frame = pd.read_sql_query(query, db_conn)
    if frame.empty:
        return frame
    frame["dsld_id"] = frame["dsld_id"].astype(str)
    return frame


def filter_product_catalog(data: DashboardData) -> pd.DataFrame:
    frame = data.product_catalog.copy()
    if frame.empty:
        return frame

    dataset_scope = st.session_state.get("dataset_filter", "All Datasets")
    if dataset_scope != "All Datasets":
        frame = frame[
            frame["brand_name"].fillna("").str.contains(str(dataset_scope), case=False, na=False)
        ]

    brand_filter = st.session_state.get("brand_filter") or []
    if brand_filter:
        frame = frame[frame["brand_name"].isin(brand_filter)]

    supp_type_filter = st.session_state.get("supplement_type_filter") or []
    if supp_type_filter:
        frame = frame[frame["supplement_type"].isin(supp_type_filter)]

    primary_category_filter = st.session_state.get("primary_category_filter") or []
    if primary_category_filter:
        frame = frame[frame["primary_category"].isin(primary_category_filter)]

    verdict_filter = st.session_state.get("verdict_filter") or []
    if verdict_filter:
        frame = frame[frame["verdict"].isin(verdict_filter)]

    min_score = float(st.session_state.get("min_score_filter", 0.0) or 0.0)
    frame = frame[frame["score"].fillna(0.0) >= min_score]

    min_section_a = float(st.session_state.get("min_section_a_filter", 0.0) or 0.0)
    frame = frame[frame["section_a_score"].fillna(0.0) >= min_section_a]

    if st.session_state.get("only_section_a_ceiling", False):
        frame = frame[
            frame["section_a_score"].fillna(0.0) >= frame["section_a_max"].fillna(0.0)
        ]

    if st.session_state.get("only_harmful_flags", False):
        frame = frame[frame["has_harmful_additives"] == 1]

    if st.session_state.get("only_omega_bonus_candidates", False):
        frame = frame[frame["contains_omega3"] == 1]

    if st.session_state.get("only_non_gmo_verified", False):
        frame = frame[frame["is_non_gmo"] == 1]

    return frame.reset_index(drop=True)


def _compute_blob_analytics(detail_blobs_dir: Path | None, db_conn: sqlite3.Connection | None) -> dict[str, Any]:
    if detail_blobs_dir is None or not detail_blobs_dir.exists():
        return {
            "ingredient_forms": [],
            "ingredient_usage": [],
            "low_quality_ingredients": [],
            "bonus_frequency": [],
            "penalty_frequency": [],
            "driver_impacts": [],
            "ingredient_products": {},
            "completeness_records": [],
        }

    lookup = _db_lookup(db_conn)
    form_stats: dict[tuple[str, str], dict[str, Any]] = {}
    ingredient_usage: Counter[str] = Counter()
    quality_scores: defaultdict[str, list[float]] = defaultdict(list)
    bonus_frequency: Counter[str] = Counter()
    penalty_frequency: Counter[str] = Counter()
    driver_impacts: defaultdict[str, list[float]] = defaultdict(list)
    ingredient_products: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    risk_stats: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "occurrences": 0,
            "risk_product_count": 0,
            "unsafe_product_count": 0,
            "banned_hits": 0,
            "recalled_hits": 0,
            "harmful_hits": 0,
            "allergen_hits": 0,
        }
    )
    product_explainers: list[dict[str, Any]] = []
    completeness_records: list[dict[str, Any]] = []

    for blob_path in sorted(detail_blobs_dir.glob("*.json")):
        blob = safe_load_json(blob_path)
        if not blob:
            continue
        dsld_id = str(blob.get("dsld_id") or blob_path.stem)
        product_meta = lookup.get(dsld_id, {"dsld_id": dsld_id})
        ingredients = blob.get("ingredients") or []
        inactive_ingredients = blob.get("inactive_ingredients") or []
        warnings = blob.get("warnings") or []
        manufacturer_detail = blob.get("manufacturer_detail") or {}
        evidence_data = blob.get("evidence_data") or {}
        interaction_summary = blob.get("interaction_summary") or {}
        bonuses = blob.get("score_bonuses") or []
        penalties = blob.get("score_penalties") or []

        completeness_checks = {
            "ingredients_mapped": bool(ingredients) and all(bool(ing.get("mapped", True)) for ing in ingredients),
            "manufacturer_present": bool(manufacturer_detail),
            "evidence_present": bool(evidence_data),
            "interaction_screened": bool(interaction_summary),
            "dosage_present": bool(ingredients) and all(bool(ing.get("quantity") or ing.get("normalized_amount")) for ing in ingredients),
            "warnings_present": warnings is not None,
        }
        completeness_pct = round(sum(completeness_checks.values()) / len(completeness_checks) * 100, 1)
        completeness_records.append(
            {
                **product_meta,
                "completeness_pct": completeness_pct,
                "missing_fields": [key for key, value in completeness_checks.items() if not value],
            }
        )

        for ingredient in ingredients:
            ingredient_name = (
                ingredient.get("standard_name")
                or ingredient.get("standardName")
                or ingredient.get("name")
                or "Unknown"
            )
            form_name = ingredient.get("form") or ingredient.get("matched_form") or "Unknown"
            form_key = (ingredient_name, form_name)
            stat = form_stats.setdefault(form_key, {"count": 0, "total_product_score": 0.0, "bio_scores": []})
            stat["count"] += 1
            stat["total_product_score"] += float(product_meta.get("score") or 0.0)
            if ingredient.get("bio_score") is not None:
                stat["bio_scores"].append(float(ingredient["bio_score"]))
                quality_scores[ingredient_name].append(float(ingredient["bio_score"]))
            ingredient_usage[ingredient_name] += 1
            ingredient_risk = risk_stats[ingredient_name]
            ingredient_risk["occurrences"] += 1
            ingredient_risk["banned_hits"] += int(bool(product_meta.get("has_banned_substance")))
            ingredient_risk["recalled_hits"] += int(bool(product_meta.get("has_recalled_ingredient")))
            ingredient_risk["harmful_hits"] += int(bool(product_meta.get("has_harmful_additives")))
            ingredient_risk["allergen_hits"] += int(bool(product_meta.get("has_allergen_risks")))
            if any(
                bool(product_meta.get(flag))
                for flag in (
                    "has_banned_substance",
                    "has_recalled_ingredient",
                    "has_harmful_additives",
                    "has_allergen_risks",
                )
            ):
                ingredient_risk["risk_product_count"] += 1
            if product_meta.get("verdict") == "UNSAFE":
                ingredient_risk["unsafe_product_count"] += 1
            ingredient_products[ingredient_name.lower()].append(
                {
                    **product_meta,
                    "ingredient_name": ingredient_name,
                    "form": form_name,
                    "bio_score": ingredient.get("bio_score"),
                }
            )

        for bonus in bonuses:
            label = bonus.get("label") or bonus.get("id") or "Unknown bonus"
            score = float(bonus.get("score") or 0.0)
            bonus_frequency[label] += 1
            driver_impacts[label].append(score)

        for penalty in penalties:
            label = penalty.get("label") or penalty.get("id") or "Unknown penalty"
            score = float(penalty.get("score") or 0.0)
            penalty_frequency[label] += 1
            driver_impacts[label].append(-score if score else 0.0)

        top_bonuses = sorted(
            [
                f"{item.get('label') or item.get('id') or 'Bonus'} (+{float(item.get('score') or 0.0):.1f})"
                for item in bonuses
            ],
            key=lambda text: float(text.rsplit("(", 1)[1].rstrip(")").replace("+", "")),
            reverse=True,
        )[:3]
        top_penalties = sorted(
            [
                f"{item.get('label') or item.get('id') or 'Penalty'} (-{abs(float(item.get('score') or 0.0)):.1f})"
                for item in penalties
            ],
            key=lambda text: abs(float(text.rsplit("(", 1)[1].rstrip(")").replace("-", ""))),
            reverse=True,
        )[:3]
        product_explainers.append(
            {
                **product_meta,
                "ingredient_count": len(ingredients),
                "top_bonuses": top_bonuses,
                "top_penalties": top_penalties,
                "explanation": "; ".join(
                    [
                        f"Strengths: {', '.join(top_bonuses)}" if top_bonuses else "",
                        f"Trade-offs: {', '.join(top_penalties)}" if top_penalties else "",
                    ]
                ).strip("; "),
            }
        )

    ingredient_forms = [
        {
            "ingredient_name": ingredient_name,
            "form": form_name,
            "occurrences": stats["count"],
            "avg_product_score": round(stats["total_product_score"] / stats["count"], 2),
            "avg_bio_score": round(sum(stats["bio_scores"]) / len(stats["bio_scores"]), 2) if stats["bio_scores"] else None,
        }
        for (ingredient_name, form_name), stats in form_stats.items()
    ]
    ingredient_forms.sort(key=lambda row: (row["avg_product_score"], row["occurrences"]), reverse=True)

    low_quality_ingredients = [
        {
            "ingredient_name": ingredient_name,
            "occurrences": len(scores),
            "avg_bio_score": round(sum(scores) / len(scores), 2),
        }
        for ingredient_name, scores in quality_scores.items()
        if scores
    ]
    low_quality_ingredients.sort(key=lambda row: (row["avg_bio_score"], -row["occurrences"]))

    bonus_rows = [{"label": label, "count": count} for label, count in bonus_frequency.most_common(25)]
    penalty_rows = [{"label": label, "count": count} for label, count in penalty_frequency.most_common(25)]
    driver_rows = []
    for label, scores in driver_impacts.items():
        if not scores:
            continue
        driver_rows.append(
            {
                "driver": label,
                "count": len(scores),
                "avg_impact": round(sum(scores) / len(scores), 2) if scores else 0.0,
            }
        )
    driver_rows.sort(key=lambda row: abs(row["avg_impact"]), reverse=True)

    ingredient_usage_rows = [{"ingredient_name": label, "occurrences": count} for label, count in ingredient_usage.most_common(50)]
    high_risk_rows = []
    for ingredient_name, stats in risk_stats.items():
        high_risk_rows.append(
            {
                "ingredient_name": ingredient_name,
                "occurrences": stats["occurrences"],
                "risk_product_count": stats["risk_product_count"],
                "unsafe_product_count": stats["unsafe_product_count"],
                "banned_hits": stats["banned_hits"],
                "recalled_hits": stats["recalled_hits"],
                "harmful_hits": stats["harmful_hits"],
                "allergen_hits": stats["allergen_hits"],
            }
        )
    high_risk_rows.sort(
        key=lambda row: (
            row["risk_product_count"],
            row["unsafe_product_count"],
            row["banned_hits"],
            row["occurrences"],
        ),
        reverse=True,
    )
    completeness_records.sort(key=lambda row: row["completeness_pct"])
    product_explainers.sort(key=lambda row: (float(row.get("score") or 0.0), row.get("ingredient_count", 0)), reverse=True)

    return {
        "ingredient_forms": ingredient_forms,
        "ingredient_usage": ingredient_usage_rows,
        "high_risk_ingredients": high_risk_rows[:50],
        "low_quality_ingredients": low_quality_ingredients[:50],
        "bonus_frequency": bonus_rows,
        "penalty_frequency": penalty_rows,
        "driver_impacts": driver_rows[:50],
        "ingredient_products": dict(ingredient_products),
        "product_explainers": product_explainers,
        "completeness_records": completeness_records,
    }


def _compute_blob_analytics_from_db(db_conn: sqlite3.Connection | None) -> dict[str, Any]:
    """Fallback analytics computed from the SQLite DB when detail blobs are unavailable."""
    if db_conn is None:
        return {}

    import json as _json

    # Bonus/penalty frequency from badges and safety flags
    bonus_counts: Counter[str] = Counter()
    penalty_counts: Counter[str] = Counter()
    driver_impacts: defaultdict[str, list[float]] = defaultdict(list)

    rows = db_conn.execute(
        """SELECT has_banned_substance, has_recalled_ingredient,
                  has_harmful_additives, has_allergen_risks, has_third_party_testing,
                  has_full_disclosure, is_organic, is_non_gmo, is_trusted_manufacturer,
                  score_ingredient_quality, score_safety_purity,
                  score_evidence_research, score_brand_trust
           FROM products_core"""
    ).fetchall()

    for (banned, recalled, harmful, allergens, tpt, fd, organic, nongmo,
         trusted, s_iq, s_sp, s_er, s_bt) in rows:
        # Bonuses
        if tpt:
            bonus_counts["Third-party tested"] += 1
        if fd:
            bonus_counts["Full disclosure"] += 1
        if organic:
            bonus_counts["Organic"] += 1
        if nongmo:
            bonus_counts["Non-GMO"] += 1
        if trusted:
            bonus_counts["Trusted manufacturer"] += 1
        # Penalties
        if banned:
            penalty_counts["Banned substance"] += 1
        if recalled:
            penalty_counts["Recalled ingredient"] += 1
        if harmful:
            penalty_counts["Harmful additives"] += 1
        if allergens:
            penalty_counts["Allergen risks"] += 1
        # Section drivers
        if s_iq is not None:
            driver_impacts["Ingredient Quality (A)"].append(float(s_iq))
        if s_sp is not None:
            driver_impacts["Safety & Purity (B)"].append(float(s_sp))
        if s_er is not None:
            driver_impacts["Evidence & Research (C)"].append(float(s_er))
        if s_bt is not None:
            driver_impacts["Brand Trust (D)"].append(float(s_bt))

    bonus_rows = [{"label": label, "count": count}
                  for label, count in bonus_counts.most_common(25)]
    penalty_rows = [{"label": label, "count": count}
                    for label, count in penalty_counts.most_common(25)]
    driver_rows = []
    for label, scores in driver_impacts.items():
        if scores:
            driver_rows.append({
                "driver": label,
                "count": len(scores),
                "avg_impact": round(sum(scores) / len(scores), 2) if scores else 0.0,
            })
    driver_rows.sort(key=lambda r: abs(r["avg_impact"]), reverse=True)

    # High-risk ingredients from safety flags — one row per flag type
    flag_map = {
        "Banned substances": "has_banned_substance",
        "Recalled ingredients": "has_recalled_ingredient",
        "Harmful additives": "has_harmful_additives",
        "Allergen risks": "has_allergen_risks",
    }
    high_risk_rows = []
    for label, col in flag_map.items():
        row = db_conn.execute(
            f"SELECT COUNT(*) FROM products_core WHERE {col} = 1"
        ).fetchone()
        count = row[0] if row else 0
        if count > 0:
            high_risk_rows.append({
                "ingredient_name": label,
                "occurrences": count,
                "risk_product_count": count,
                "unsafe_product_count": 0,
                "banned_hits": count if "banned" in col else 0,
                "recalled_hits": count if "recalled" in col else 0,
                "harmful_hits": count if "harmful" in col else 0,
                "allergen_hits": count if "allergen" in col else 0,
            })
    high_risk_rows.sort(key=lambda r: r["risk_product_count"], reverse=True)

    # Product explainers from decision_highlights
    explainer_rows = []
    dh_rows = db_conn.execute(
        """SELECT dsld_id, product_name, brand_name, decision_highlights,
                  score_100_equivalent, supplement_type
           FROM products_core
           WHERE decision_highlights IS NOT NULL AND decision_highlights != ''
           ORDER BY score_100_equivalent DESC
           LIMIT 200"""
    ).fetchall()
    for dsld_id, name, brand, dh_raw, score, stype in dh_rows:
        try:
            dh = _json.loads(dh_raw)
            explanation = dh.get("positive", "")
            if dh.get("caution"):
                explanation += f" {dh['caution']}"
        except (ValueError, TypeError):
            explanation = ""
        explainer_rows.append({
            "dsld_id": dsld_id,
            "product_name": name,
            "brand_name": brand,
            "score": score,
            "supplement_type": stype,
            "explanation": explanation or "No explainer available.",
            "top_bonuses": [],
            "top_penalties": [],
        })

    return {
        "ingredient_forms": [],
        "ingredient_usage": [],
        "high_risk_ingredients": high_risk_rows[:50],
        "low_quality_ingredients": [],
        "bonus_frequency": bonus_rows,
        "penalty_frequency": penalty_rows,
        "driver_impacts": driver_rows[:50],
        "ingredient_products": {},
        "product_explainers": explainer_rows,
        "completeness_records": [],
    }


def _compute_shared_metrics(
    db_conn: sqlite3.Connection | None,
    export_manifest: dict[str, Any] | None,
    export_audit: dict[str, Any] | None,
    integrity_data: dict[str, Any] | None,
) -> dict[str, Any]:
    counts = (export_audit or {}).get("counts", {})
    verdict_counts = {verdict: 0 for verdict in VERDICT_ORDER}
    safety_counts = {key: int(counts.get(key, 0)) for key in SAFETY_COUNT_KEYS}
    product_count = int((export_manifest or {}).get("product_count") or counts.get("total_exported", 0))
    average_score = None
    average_coverage_pct = None
    blocked_count = 0

    if db_conn is not None:
        rows = db_conn.execute("SELECT verdict, COUNT(*) AS count FROM products_core GROUP BY verdict").fetchall()
        for row in rows:
            verdict_counts[row["verdict"]] = int(row["count"])
        avg_row = db_conn.execute(
            "SELECT AVG(score_100_equivalent) AS avg_score, AVG(mapped_coverage) AS avg_coverage FROM products_core"
        ).fetchone()
        average_score = round(float(avg_row["avg_score"] or 0.0), 1)
        average_coverage_pct = round(float(avg_row["avg_coverage"] or 0.0) * 100, 1)
        blocked_count = int(
            db_conn.execute("SELECT COUNT(*) AS count FROM products_core WHERE verdict = 'BLOCKED'").fetchone()["count"]
        )
        product_count = int(
            db_conn.execute("SELECT COUNT(*) AS count FROM products_core").fetchone()["count"]
        )

    enriched_input_count = None
    scored_input_count = None
    error_count = int(counts.get("total_errors", 0))
    enriched_only_count = int(counts.get("enriched_only", 0))
    scored_only_count = int(counts.get("scored_only", 0))
    strict_mode = False
    if integrity_data:
        enriched_input_count = integrity_data.get("enriched_input_count")
        scored_input_count = integrity_data.get("scored_input_count")
        error_count = len(integrity_data.get("errors", [])) or error_count
        enriched_only_count = integrity_data.get("enriched_only_count", enriched_only_count)
        scored_only_count = integrity_data.get("scored_only_count", scored_only_count)
        strict_mode = bool(integrity_data.get("strict_mode", False))

    if enriched_input_count is None:
        enriched_input_count = product_count + enriched_only_count + error_count
    if scored_input_count is None:
        scored_input_count = product_count + scored_only_count + error_count

    pipeline_yield_pct = round((product_count / enriched_input_count) * 100, 1) if enriched_input_count else None

    return {
        "product_count": product_count,
        "verdict_counts": verdict_counts,
        "safety_counts": safety_counts,
        "average_score": average_score,
        "average_coverage_pct": average_coverage_pct,
        "enriched_input_count": enriched_input_count,
        "scored_input_count": scored_input_count,
        "exported_count": product_count,
        "error_count": error_count,
        "enriched_only_count": enriched_only_count,
        "scored_only_count": scored_only_count,
        "pipeline_yield_pct": pipeline_yield_pct,
        "strict_mode": strict_mode,
        "blocked_count": blocked_count,
    }


def resolve_product_source_paths(scan_dir: Path, dsld_id: str) -> dict[str, Path | None]:
    enriched_match = next(iter(scan_dir.glob(f"output_*/enriched/{dsld_id}.json")), None)
    scored_match = next(iter(scan_dir.glob(f"output_*/scored/{dsld_id}.json")), None)
    return {
        "enriched": enriched_match.resolve() if enriched_match else None,
        "scored": scored_match.resolve() if scored_match else None,
    }


@st.cache_resource(ttl=300)
def load_dashboard_data(config: Any) -> DashboardData:
    data = DashboardData(scan_dir=config.scan_dir, build_root=config.build_root, dataset_root=config.dataset_root)

    data.db_path = config.build_root / "pharmaguide_core.db"
    data.db_conn = get_sqlite_connection(data.db_path)
    data.export_manifest = safe_load_json(config.build_root / "export_manifest.json")
    data.export_audit = safe_load_json(config.build_root / "export_audit_report.json")
    data.detail_index = safe_load_json(config.build_root / "detail_index.json")
    data.detail_blobs_dir = config.build_root / "detail_blobs"
    data.processing_state = safe_load_json(config.scan_dir / "logs" / "processing_state.json")
    data.scoring_config = safe_load_json(Path("scripts/config/scoring_config.json"))

    data.integrity_data = (data.export_manifest or {}).get("integrity", {}) or None
    data.alert_thresholds = _load_alert_thresholds()
    data.build_history = _discover_build_history(config.build_root, config.dataset_root)

    if data.export_manifest:
        data.latest_export_at = _parse_datetime(data.export_manifest.get("generated_at"))
    if data.processing_state:
        data.latest_batch_at = _parse_datetime(data.processing_state.get("last_updated"))

    data.release_artifact_status = {
        "db": data.db_path.exists(),
        "manifest": (config.build_root / "export_manifest.json").exists(),
        "audit": (config.build_root / "export_audit_report.json").exists(),
        "detail_index": (config.build_root / "detail_index.json").exists(),
        "blobs": bool(data.detail_blobs_dir and data.detail_blobs_dir.exists()),
    }

    if not data.release_artifact_status["db"]:
        data.warnings.append(f"Database not found at {data.db_path}")
    if not data.release_artifact_status["manifest"]:
        data.warnings.append(f"Manifest not found at {config.build_root / 'export_manifest.json'}")
    if not data.release_artifact_status["detail_index"]:
        data.warnings.append(f"Detail index not found at {config.build_root / 'detail_index.json'}")

    for output_dir in _discover_output_dirs(config.scan_dir):
        dataset_name = _dataset_name(output_dir)
        dataset_report = _parse_dataset_report(output_dir)
        data.dataset_reports[dataset_name] = dataset_report
        data.discovered_datasets.append(dataset_name)
        if dataset_report["latest_pipeline_at"]:
            if data.latest_enriched_at is None or dataset_report["latest_pipeline_at"] > data.latest_enriched_at:
                data.latest_enriched_at = dataset_report["latest_pipeline_at"]
        data.missing_artifacts[dataset_name] = dataset_report["missing_expected"]

        report_dir = output_dir / "reports"
        for report_path in report_dir.glob("*.json"):
            content = safe_load_json(report_path)
            if not content:
                continue
            if "enrichment_summary" in report_path.name:
                data.enrichment_summaries[dataset_name] = content
                timestamp = _report_timestamp(report_path, content=content)
                if timestamp and (data.latest_enriched_at is None or timestamp > data.latest_enriched_at):
                    data.latest_enriched_at = timestamp
            elif "scoring_summary" in report_path.name:
                data.scoring_summaries[dataset_name] = content
                timestamp = _report_timestamp(report_path, content=content)
                if timestamp and (data.latest_scored_at is None or timestamp > data.latest_scored_at):
                    data.latest_scored_at = timestamp
            elif "coverage_report" in report_path.name:
                data.coverage_reports[dataset_name] = content
            elif "form_fallback" in report_path.name:
                data.form_fallback_reports[dataset_name] = content
            elif "parent_fallback" in report_path.name:
                data.parent_fallback_reports[dataset_name] = content

    data.discovered_datasets = sorted(set(data.discovered_datasets))

    data.batch_run_files, data.batch_history = _discover_batch_history(config.scan_dir)
    if data.batch_history:
        data.latest_batch_summary = data.batch_history[0]
        latest_log_at = data.batch_history[0].get("timestamp")
        if latest_log_at and (data.latest_batch_at is None or latest_log_at > data.latest_batch_at):
            data.latest_batch_at = latest_log_at

    live_pipeline_candidates = [
        timestamp for timestamp in [
            data.latest_batch_at,
            data.latest_enriched_at,
            data.latest_scored_at,
        ] if timestamp is not None
    ]
    if live_pipeline_candidates:
        data.latest_batch_at = max(live_pipeline_candidates)

    data.shared_metrics = _compute_shared_metrics(data.db_conn, data.export_manifest, data.export_audit, data.integrity_data)
    data.blob_analytics = _compute_blob_analytics(data.detail_blobs_dir, data.db_conn)
    # Fallback: if detail blobs are missing, compute analytics from the DB
    if not data.blob_analytics.get("bonus_frequency") and data.db_conn is not None:
        data.blob_analytics = _compute_blob_analytics_from_db(data.db_conn)
    data.product_catalog = _load_product_catalog(data.db_conn)

    # Load CAERS adverse event signals
    caers_path = Path("scripts/data/caers_adverse_event_signals.json")
    caers_raw = safe_load_json(caers_path)
    if caers_raw:
        data.caers_signals = caers_raw.get("signals", {})
        data.caers_metadata = caers_raw.get("_metadata", {})

    return data
