"""Read-only, incremental Parquet index of v4 scoring artifacts for the dashboard.

The scorer owns every point. This module only projects what the artifacts already
record (``quality_pillars_v4.<pillar>.receipt``, gates, dose-safety evaluation) into
small columnar tables so pages never parse source JSON. It never computes a score.

Planes:
    candidate  scored JSON under ``<scan_dir>/output_*_scored/scored/`` (newest work)
    release    ``<build_root>/pharmaguide_core.db`` + ``detail_blobs/`` (what ships)
    backfill   older catalog DBs, pillar totals only

Layout under the cache root (gitignored ``scripts/.cache/dashboard``)::

    builds/<build_id>/index_meta.json
    builds/<build_id>/runs/<run_key>/<table>/<part>.parquet
    builds/<build_id>/findings.parquet, finding_seen.parquet
    current.json      pointer to the last validated build (swapped atomically)
    status.json       last refresh outcome

CLI::

    python -m scripts.dashboard.score_index refresh [--scan-dir D] [--build-root D]
    python -m scripts.dashboard.score_index backfill DB [DB ...]
    python -m scripts.dashboard.score_index status | gc
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import pyarrow as pa
import pyarrow.dataset as pds
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _path in (SCRIPTS_ROOT, REPO_ROOT):  # stage_manifest/scoring_v4 import as top-level; dashboard as scripts.*
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from stage_manifest import MANIFEST_NAME, StageManifestError, select_stage_input_files  # noqa: E402
from scoring_v4.quality_score import shipped_whole_score  # noqa: E402  (the export's one rounding rule)

INDEX_SCHEMA_VERSION = 1
INDEX_BUILD_VERSION = "1.0.0"
# Reused partitions are valid only for the projection code that wrote them.
PROJECTION_FINGERPRINT = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
QUALITY_CONFIG = SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json"
PILLARS = ("formulation", "dose", "evidence", "transparency", "verification", "safety_hygiene")
PILLAR_LABELS = {
    "formulation": "Formulation",
    "dose": "Dose",
    "evidence": "Evidence",
    "transparency": "Transparency",
    "verification": "Verification",
    "safety_hygiene": "Formula checks",
}
FIDELITY_FULL = "full_receipts"
FIDELITY_RELEASE = "receipts_without_module"  # blobs keep receipts, drop _v4_module_breakdown
FIDELITY_PILLARS = "pillar_totals_only"
RECONCILE_TOLERANCE = 0.05


def pillar_maxima() -> dict[str, float]:
    """Pillar capacity from the production config, never a literal."""
    pillars = json.loads(QUALITY_CONFIG.read_text(encoding="utf-8"))["pillars"]
    return {name: float(pillars[name]["weight"]) for name in PILLARS}


# --------------------------------------------------------------------------- schemas

def _schema(*fields: tuple[str, pa.DataType]) -> pa.Schema:
    return pa.schema([pa.field(name, kind) for name, kind in fields])


_S, _F, _B, _I = pa.string(), pa.float64(), pa.bool_(), pa.int64()
_LS = pa.list_(pa.string())

PRODUCTS_SCHEMA = _schema(
    ("dsld_id", _S), ("product_name", _S), ("brand_name", _S), ("module", _S),
    ("primary_type", _S), ("category", _S), ("source_part", _S), ("blob_sha256", _S),
    ("total", _F), ("tier", _S), ("quality_score_status", _S), ("quality_assessment_status", _S),
    ("product_safety_status", _S), ("safety_verdict", _S), ("not_scorable_reason", _S),
    ("score_unavailable_reason", _S), ("suppressed_reason", _S), ("blocking_reason", _S),
    ("safety_signal_reason", _S), ("safety_signals", _LS), ("confidence", _S), ("route_confidence", _S),
    *[(f"pillar_{name}", _F) for name in PILLARS],
    ("evidence_state", _S), ("evidence_display_state", _S), ("dose_basis", _S),
    ("dose_cap_applied", _B), ("dose_cap_nutrient", _S), ("dose_cap_pct_ul", _F),
    ("verification_tier", _S), ("verification_fail_open", _B), ("verification_cert", _F),
    ("has_deduction", _B), ("has_neutral", _B), ("has_cap", _B), ("has_floor", _B),
    ("neutral_only_pillars", _LS), ("receipt_entry_ids", _LS),
    ("nominal_deductions", _F), ("realized_deductions", _F), ("absorbed_points", _F),
    ("unawarded_total", _F), ("receipt_mismatch_max", _F), ("pillars_missing_receipt", _I),
    ("pillar_sum_mismatch", _F), ("unmapped_actives_total", _I), ("fallbacks_used", _I),
    ("completeness_score_cap", _F), ("completeness_verdict_ceiling", _S), ("completeness_missing", _LS),
    ("config_version", _S), ("config_fingerprint", _S), ("has_third_party_testing", _B),
    ("percentile_rank", _F),
)
LEDGER_SCHEMA = _schema(
    ("dsld_id", _S), ("pillar", _S), ("score", _F), ("max", _F), ("unawarded", _F),
    ("nominal_deductions", _F), ("realized_deductions", _F), ("absorbed", _F), ("entry_sum", _F),
    ("reason", _S), ("state", _S), ("has_receipt", _B),
)
RECEIPT_SCHEMA = _schema(
    ("dsld_id", _S), ("pillar", _S), ("seq", _I), ("entry_id", _S), ("kind", _S), ("source", _S),
    ("raw", _F), ("points", _F), ("basis", _S), ("withheld_by", _S),
)
DOSE_REF_SCHEMA = _schema(
    ("dsld_id", _S), ("nutrient", _S), ("canonical_id", _S), ("amount", _F), ("unit", _S),
    ("per_day_min", _F), ("per_day_max", _F), ("rda_ai", _F), ("pct_rda", _F), ("ul", _F),
    ("pct_ul", _F), ("ul_status", _S), ("ul_population", _S),
)
DOSE_FLAG_SCHEMA = _schema(
    ("dsld_id", _S), ("state", _S), ("nutrient", _S), ("canonical_id", _S), ("pct_ul", _F),
    ("pct_ul_at_minimum", _F), ("reason", _S), ("is_ceiling", _B), ("ceiling_kind", _S),
    ("ul", _F), ("ul_unit", _S), ("cap_public", _F),
)
EXPLANATION_SCHEMA = _schema(("dsld_id", _S), ("pillar", _S), ("role", _S), ("text", _S))
SLIM_SCHEMA = _schema(("dsld_id", _S), ("slim_json", _S))
LABEL_SCHEMA = _schema(("dsld_id", _S), ("record_json", _S))
ADDITIVE_SCHEMA = _schema(("dsld_id", _S), ("rule_id", _S), ("tier", _S), ("penalty", _F), ("labels", _LS))

TABLES: dict[str, pa.Schema] = {
    "products": PRODUCTS_SCHEMA,
    "ledgers": LEDGER_SCHEMA,
    "receipts": RECEIPT_SCHEMA,
    "dose_refs": DOSE_REF_SCHEMA,
    "dose_flags": DOSE_FLAG_SCHEMA,
    "explanations": EXPLANATION_SCHEMA,
    "slim": SLIM_SCHEMA,
    "label_records": LABEL_SCHEMA,
    "additives": ADDITIVE_SCHEMA,
}


# --------------------------------------------------------------------------- helpers

def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _config_identity(raw: Any) -> tuple[str | None, str | None]:
    """(quality_score version, fingerprint) from ``_v4_config_fingerprint``."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None, raw or None
    if isinstance(raw, dict):
        quality = raw.get("quality_score") or {}
        if isinstance(quality, dict):
            return quality.get("version"), _canonical(raw)
    return None, None


def _git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                             text=True, timeout=5, check=True)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# --------------------------------------------------------------------------- extraction

def label_trust_record(blob: dict[str, Any], core: dict[str, Any] | None = None) -> dict[str, Any]:
    """The blob subset ``data_loader.compute_label_trust`` reads (release plane only)."""
    core = core or {}
    rows = blob.get("display_ingredients")
    label_record = blob.get("label_record")
    return {
        "dsld_id": str(blob.get("dsld_id") or core.get("dsld_id")),
        "brand_name": blob.get("brand_name") or core.get("brand_name"),
        "primary_type": blob.get("primary_type") or core.get("primary_category"),
        "label_ledger_audit": blob.get("label_ledger_audit"),
        "display_ingredients": [
            {key: row.get(key) for key in ("display_disposition", "form_display_state", "identity_integrity_state")}
            if isinstance(row, dict) else row
            for row in rows
        ] if isinstance(rows, list) else rows,
        "label_record": {
            "history_status": label_record.get("history_status"),
            "formula_history": label_record.get("formula_history"),
        } if isinstance(label_record, dict) else label_record,
    }


def project_product(product: dict[str, Any], *, source_part: str, blob_sha256: str | None = None,
                    core: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Project one scored product (candidate) or detail blob + core row (release).

    Returns rows per table. Reads recorded values only.
    """
    core = core or {}
    pid = str(product.get("dsld_id") or core.get("dsld_id"))
    pillars = product.get("quality_pillars_v4") or {}
    if not isinstance(pillars, dict):
        pillars = {}
    provenance = product.get("v4_score_provenance") or {}

    # Release values come from products_core first: it is what ships.
    sources = (core, provenance, product) if core else (product, provenance)

    def pick(*keys: str) -> Any:
        for key in keys:
            for source in sources:
                if isinstance(source, dict) and source.get(key) not in (None, ""):
                    return source[key]
        return None

    ledgers, receipts = [], []
    ids: set[str] = set()
    kinds_seen: set[str] = set()
    neutral_only: list[str] = []
    nominal = realized = unawarded = 0.0
    mismatch = 0.0
    missing_receipt = 0
    for name in PILLARS:
        pillar = pillars.get(name)
        if not isinstance(pillar, dict):
            continue
        score = _num(pillar.get("score"))
        receipt = pillar.get("receipt") if isinstance(pillar.get("receipt"), dict) else None
        entries = (receipt or {}).get("entries") or []
        entry_sum = round(sum(_num(e.get("points")) or 0.0 for e in entries), 4) if receipt else None
        if receipt is None and score is not None:
            missing_receipt += 1
        if receipt is not None and score is not None:
            mismatch = max(mismatch, abs((entry_sum or 0.0) - score))
        nom = _num((receipt or {}).get("nominal_deductions")) or 0.0
        real = _num((receipt or {}).get("realized_deductions")) or 0.0
        una = _num((receipt or {}).get("unawarded"))
        nominal += nom
        realized += real
        unawarded += una or 0.0
        positive = {e.get("kind") for e in entries if (_num(e.get("points")) or 0) > 0}
        if "neutral" in positive and not positive & {"earned", "disclosure"}:
            neutral_only.append(name)
        state = pillar.get("display_state") if name == "evidence" else None
        ledgers.append({
            "dsld_id": pid, "pillar": name, "score": score, "max": _num(pillar.get("max")),
            "unawarded": una, "nominal_deductions": nom, "realized_deductions": real,
            "absorbed": round(real - nom, 4), "entry_sum": entry_sum,
            "reason": _text(pillar.get("reason")), "state": state, "has_receipt": receipt is not None,
        })
        for seq, entry in enumerate(entries):
            ids.add(str(entry.get("id")))
            kinds_seen.add(str(entry.get("kind")))
            receipts.append({
                "dsld_id": pid, "pillar": name, "seq": seq, "entry_id": _text(entry.get("id")),
                "kind": _text(entry.get("kind")), "source": _text(entry.get("source")),
                "raw": _num(entry.get("raw")), "points": _num(entry.get("points")),
                "basis": _text(entry.get("basis")), "withheld_by": _text(entry.get("withheld_by")),
            })

    total = _num(pick("quality_score_v4_100"))
    pillar_scores = {name: _num((pillars.get(name) or {}).get("score")) for name in PILLARS}
    if not pillars:  # release core keeps pillar totals even when a blob lacks them
        pillar_scores = {name: _num(core.get(f"pillar_{name}_v4")) for name in PILLARS}
    present = [value for value in pillar_scores.values() if value is not None]
    sum_mismatch = None
    if total is not None and len(present) == len(PILLARS):
        # Release ships a whole-number total by contract (build_final_db uses the scorer's
        # shipped_whole_score); the candidate total is the exact pillar sum.
        expected_total = shipped_whole_score(sum(present)) if core else sum(present)
        sum_mismatch = abs(expected_total - total)

    evidence = pillars.get("evidence") or {}
    dose_entries = ((pillars.get("dose") or {}).get("receipt") or {}).get("entries") or []
    verification = (pillars.get("verification") or {}).get("components") or {}
    dose_eval = product.get("dose_safety_evaluation") or product.get("v4_dose_safety") or {}
    ceiling = dose_eval.get("dose_ceiling") if isinstance(dose_eval, dict) else None
    completeness = product.get("_v4_completeness_gate") or product.get("v4_completeness_gate") or {}
    safety_gate = product.get("_v4_safety_gate") or product.get("v4_safety_gate") or {}
    version, fingerprint = _config_identity(pick("_v4_config_fingerprint", "config_fingerprint"))
    if version is None:
        version = _text(pick("quality_score_version"))
    if fingerprint is None:
        fingerprint = _text(core.get("v4_config_fingerprint"))
    fallbacks = product.get("scoring_fallbacks_used")
    third_party = core.get("has_third_party_testing")

    row = {
        "dsld_id": pid,
        "product_name": _text(pick("product_name")),
        "brand_name": _text(pick("brand_name")),
        "module": _text(pick("_v4_module", "module", "v4_module")),
        "primary_type": _text(pick("primary_type", "supplement_type")),
        "category": _text(pick("percentile_category", "primary_category")),
        "source_part": source_part,
        "blob_sha256": blob_sha256,
        "total": total,
        "tier": _text(pick("quality_tier")),
        "quality_score_status": _text(pick("quality_score_status")),
        "quality_assessment_status": _text(pick("quality_assessment_status")),
        "product_safety_status": _text(pick("product_safety_status")),
        "safety_verdict": _text(pick("safety_verdict")),
        "not_scorable_reason": _text(pick("not_scorable_reason")),
        "score_unavailable_reason": _text(pick("score_unavailable_reason")),
        "suppressed_reason": _text(pick("quality_score_suppressed_reason", "suppressed_reason")),
        "blocking_reason": _text(pick("blocking_reason")),
        "safety_signal_reason": _text(pick("safety_signal_reason")),
        "safety_signals": [str(s) for s in (safety_gate.get("safety_signals") or [])],
        "confidence": _text(pick("quality_score_confidence", "confidence")),
        "route_confidence": _text(pick("route_confidence")),
        **{f"pillar_{name}": pillar_scores[name] for name in PILLARS},
        "evidence_state": _text(evidence.get("evidence_result_state")),
        "evidence_display_state": _text(evidence.get("display_state")),
        "dose_basis": next((e.get("basis") for e in dose_entries if e.get("basis")), None),
        "dose_cap_applied": any(e.get("id") == "dose_safety_ceiling" for e in dose_entries),
        "dose_cap_nutrient": _text((ceiling or {}).get("label_nutrient") or (ceiling or {}).get("nutrient")),
        "dose_cap_pct_ul": _num((ceiling or {}).get("pct_ul")),
        "verification_tier": _text(verification.get("tier")),
        "verification_fail_open": verification.get("fail_open_neutral") if isinstance(verification.get("fail_open_neutral"), bool) else None,
        "verification_cert": _num(verification.get("cert")),
        "has_deduction": "deduction" in kinds_seen,
        "has_neutral": "neutral" in kinds_seen,
        "has_cap": "cap" in kinds_seen,
        "has_floor": "floor" in kinds_seen,
        "neutral_only_pillars": neutral_only,
        "receipt_entry_ids": sorted(ids),
        "nominal_deductions": round(nominal, 4) if receipts else None,
        "realized_deductions": round(realized, 4) if receipts else None,
        "absorbed_points": round(realized - nominal, 4) if receipts else None,
        "unawarded_total": round(unawarded, 4) if receipts else None,
        "receipt_mismatch_max": round(mismatch, 4) if receipts else None,
        "pillars_missing_receipt": missing_receipt,
        "pillar_sum_mismatch": round(sum_mismatch, 4) if sum_mismatch is not None else None,
        "unmapped_actives_total": int(product.get("unmapped_actives_total") or 0),
        "fallbacks_used": len(fallbacks) if isinstance(fallbacks, list) else 0,
        "completeness_score_cap": _num(completeness.get("score_cap")),
        "completeness_verdict_ceiling": _text(completeness.get("verdict_ceiling")),
        "completeness_missing": [str(f) for f in (completeness.get("missing_fields") or [])],
        "config_version": version,
        "config_fingerprint": fingerprint,
        "has_third_party_testing": bool(third_party) if third_party is not None else None,
        "percentile_rank": _num(core.get("percentile_rank")),
    }

    dose_explanation = ((pillars.get("dose") or {}).get("explanation") or {}).get("dose_receipt") or {}
    dose_refs = []
    for item in dose_explanation.get("reference_assessments") or []:
        population = item.get("ul_population")
        dose_refs.append({
            "dsld_id": pid, "nutrient": _text(item.get("nutrient")), "canonical_id": _text(item.get("canonical_id")),
            "amount": _num(item.get("amount")), "unit": _text(item.get("unit")),
            "per_day_min": _num(item.get("per_day_min")), "per_day_max": _num(item.get("per_day_max")),
            "rda_ai": _num(item.get("rda_ai")), "pct_rda": _num(item.get("pct_rda")), "ul": _num(item.get("ul")),
            "pct_ul": _num(item.get("pct_ul")), "ul_status": _text(item.get("ul_status")),
            "ul_population": _text(population.get("label") if isinstance(population, dict) else population),
        })
    dose_flags = []
    for flag in (dose_eval.get("flags") or []) if isinstance(dose_eval, dict) else []:
        dose_flags.append({
            "dsld_id": pid, "state": _text(flag.get("state")), "nutrient": _text(flag.get("nutrient")),
            "canonical_id": _text(flag.get("canonical_id")), "pct_ul": _num(flag.get("pct_ul")),
            "pct_ul_at_minimum": _num(flag.get("pct_ul_at_minimum")), "reason": _text(flag.get("reason")),
            "is_ceiling": False, "ceiling_kind": None, "ul": None, "ul_unit": None, "cap_public": None,
        })
    if isinstance(ceiling, dict):
        dose_flags.append({
            "dsld_id": pid, "state": "dose_ceiling", "nutrient": _text(ceiling.get("label_nutrient") or ceiling.get("nutrient")),
            "canonical_id": _text(ceiling.get("canonical_id")), "pct_ul": _num(ceiling.get("pct_ul")),
            "pct_ul_at_minimum": _num(ceiling.get("pct_ul_at_minimum")), "reason": None, "is_ceiling": True,
            "ceiling_kind": _text(ceiling.get("kind")), "ul": _num(ceiling.get("ul")),
            "ul_unit": _text(ceiling.get("ul_unit")), "cap_public": _num(ceiling.get("cap_public")),
        })

    explanations = [
        {"dsld_id": pid, "pillar": name, "role": "reason", "text": _text((pillars.get(name) or {}).get("reason"))}
        for name in PILLARS if (pillars.get(name) or {}).get("reason")
    ]
    score_explanation = product.get("v4_score_explanation") or {}
    for role in ("strengths", "drags"):
        for item in score_explanation.get(role) or []:
            explanations.append({"dsld_id": pid, "pillar": _text(item.get("pillar")),
                                 "role": role[:-1], "text": _text(item.get("reason"))})

    dims = ((product.get("_v4_module_breakdown") or {}).get("dimensions") or {})
    slim = {
        "id": pid, "total": total,
        "pillars": {name: {"score": (pillars.get(name) or {}).get("score"),
                           "components": {k: v for k, v in ((pillars.get(name) or {}).get("components") or {}).items()
                                          if not isinstance(v, (dict, list))}}
                    for name in PILLARS if name in pillars},
        "dims": {k: {"components": dict(v.get("components") or {}), "penalties": dict(v.get("penalties") or {})}
                 for k, v in dims.items() if isinstance(v, dict)},
    }
    additives = [
        {"dsld_id": pid, "rule_id": _text(hit.get("matched_rule_id")), "tier": _text(hit.get("penalty_tier")),
         "penalty": _num(hit.get("penalty_applied")),
         "labels": [str(label) for label in (hit.get("matched_labels") or [])]}
        for hit in product.get("_v4_inactive_penalty_details") or [] if isinstance(hit, dict)
    ]
    return {
        "products": [row], "ledgers": ledgers, "receipts": receipts, "dose_refs": dose_refs,
        "dose_flags": dose_flags, "explanations": explanations,
        "slim": [{"dsld_id": pid, "slim_json": _canonical(slim)}],
        "label_records": [{"dsld_id": pid, "record_json": _canonical(label_trust_record(product, core))}] if core else [],
        "additives": additives,
    }


def _merge(into: dict[str, list[dict[str, Any]]], rows: dict[str, list[dict[str, Any]]]) -> None:
    for table, items in rows.items():
        into.setdefault(table, []).extend(items)


def _write_tables(run_dir: Path, part: str, rows: dict[str, list[dict[str, Any]]]) -> None:
    for table, schema in TABLES.items():
        target = run_dir / table / f"{part}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows.get(table, []), schema=schema), target)


# --------------------------------------------------------------------------- sources

@dataclass(frozen=True)
class IndexPaths:
    scan_dir: Path
    build_root: Path
    cache_root: Path

    @property
    def builds(self) -> Path:
        return self.cache_root / "builds"

    @property
    def current_pointer(self) -> Path:
        return self.cache_root / "current.json"

    @property
    def status_file(self) -> Path:
        return self.cache_root / "status.json"


def default_paths(scan_dir: str | Path | None = None, build_root: str | Path | None = None,
                  cache_root: str | Path | None = None) -> IndexPaths:
    return IndexPaths(
        scan_dir=Path(scan_dir or os.environ.get("PG_DASHBOARD_SCAN_DIR") or SCRIPTS_ROOT / "products").resolve(),
        build_root=Path(build_root or os.environ.get("PG_DASHBOARD_BUILD_ROOT") or SCRIPTS_ROOT / "dist").resolve(),
        cache_root=Path(cache_root or os.environ.get("PG_DASHBOARD_CACHE") or SCRIPTS_ROOT / ".cache" / "dashboard").resolve(),
    )


def _scored_dirs(scan_dir: Path) -> list[Path]:
    return sorted(path for path in scan_dir.glob("output_*_scored/scored") if path.is_dir())


def candidate_sources(scan_dir: Path) -> list[dict[str, Any]]:
    """One record per scored batch directory; reads manifests only (cheap)."""
    sources = []
    for stage_dir in _scored_dirs(scan_dir):
        manifest_path = stage_dir / MANIFEST_NAME
        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {"_unreadable": True}
        if manifest.get("content_sha256"):
            identity = _canonical(manifest.get("content_sha256"))
        else:  # no manifest: fall back to (size, mtime_ns) of the files themselves
            identity = _canonical(sorted((p.name, p.stat().st_size, p.stat().st_mtime_ns)
                                         for p in stage_dir.glob("*.json")))
        part = stage_dir.parent.name.removeprefix("output_").removesuffix("_scored")
        fingerprints = manifest.get("input_fingerprints") or {}
        sources.append({
            "part": part, "stage_dir": str(stage_dir), "has_manifest": bool(manifest.get("content_sha256")),
            "cache_key": _sha(identity)[:16], "run_id": manifest.get("run_id"),
            "generated_at": manifest.get("generated_at"),
            "stage_code": fingerprints.get("stage_code_sha256_v1"),
            "reference_data": fingerprints.get("reference_data_sha256_v1"),
        })
    return sources


def release_source(build_root: Path) -> dict[str, Any] | None:
    db_path = build_root / "pharmaguide_core.db"
    if not db_path.exists():
        return None
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT dsld_id, detail_blob_sha256 FROM products_core ORDER BY dsld_id").fetchall()
    manifest = {}
    manifest_path = build_root / "export_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
    return {
        "db_path": str(db_path),
        "blob_hashes": {str(pid): sha for pid, sha in rows},
        "identity": _sha(_canonical(rows))[:16],
        "schema_version": manifest.get("schema_version"),
        "db_version": manifest.get("db_version"),
        "generated_at": manifest.get("generated_at"),
        "config_checksum": manifest.get("quality_score_config_checksum"),
        "scoring_version": manifest.get("scoring_version"),
    }


def source_state(paths: IndexPaths) -> dict[str, Any]:
    release = release_source(paths.build_root)
    return {
        "candidate": {s["part"]: s["cache_key"] for s in candidate_sources(paths.scan_dir)},
        "release": release["identity"] if release else None,
    }


# --------------------------------------------------------------------------- builds

class IndexBusy(RuntimeError):
    """Another refresh holds the lock."""


@contextmanager
def _refresh_lock(cache_root: Path) -> Iterator[None]:
    cache_root.mkdir(parents=True, exist_ok=True)
    handle = open(cache_root / "refresh.lock", "w")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise IndexBusy("another dashboard index refresh is running") from exc
        yield
    finally:
        handle.close()


def current_build(paths: IndexPaths) -> Path | None:
    try:
        pointer = json.loads(paths.current_pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    build = paths.builds / str(pointer.get("build_id"))
    meta = build / "index_meta.json"
    if not meta.exists():
        return None
    try:
        if json.loads(meta.read_text(encoding="utf-8")).get("index_schema_version") != INDEX_SCHEMA_VERSION:
            return None  # stale schema: treated as absent so the next refresh rebuilds
    except (OSError, json.JSONDecodeError):
        return None
    return build


def _load_meta(build: Path | None) -> dict[str, Any]:
    if build is None:
        return {}
    return json.loads((build / "index_meta.json").read_text(encoding="utf-8"))


def _link_tree(source: Path, target: Path) -> None:
    """Hard-link an immutable directory tree (copy when links are unavailable)."""
    for path in source.rglob("*"):
        dest = target / path.relative_to(source)
        if path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(path, dest)
        except OSError:
            shutil.copy2(path, dest)


def _run_key(plane: str, *parts: Any) -> str:
    return f"{plane}-" + _sha(_canonical([plane, INDEX_SCHEMA_VERSION, *parts]))[:16]


def _parse_candidate_part(source: dict[str, Any]) -> tuple[dict[str, list], int]:
    stage_dir = Path(source["stage_dir"])
    if source["has_manifest"]:
        files = select_stage_input_files(stage_dir, "score", require_manifest=True)
    else:
        files = sorted(p for p in stage_dir.glob("*.json") if not p.name.startswith("."))
    rows: dict[str, list] = {}
    count = 0
    for path in files:
        products = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(products, dict):
            products = products.get("products") or []
        for product in products:
            _merge(rows, project_product(product, source_part=source["part"]))
            count += 1
    return rows, count


def _release_core_rows(db_path: str) -> dict[str, dict[str, Any]]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return {str(row["dsld_id"]): dict(row) for row in conn.execute("SELECT * FROM products_core")}


def _read_run_table(run_dir: Path, table: str) -> pa.Table:
    directory = run_dir / table
    if not directory.exists():
        return pa.Table.from_pylist([], schema=TABLES[table])
    return pds.dataset(str(directory), format="parquet", schema=TABLES[table]).to_table()


def refresh(paths: IndexPaths, *, progress: Callable[[str, float], None] | None = None) -> dict[str, Any]:
    """Build a new index version and swap ``current.json`` only after validation."""
    say = progress or (lambda message, fraction: None)
    started = time.time()
    with _refresh_lock(paths.cache_root):
        previous = current_build(paths)
        prev_meta = _load_meta(previous)
        # Partitions written by other projection code are never reused (runs still carry forward).
        reuse_previous = previous if prev_meta.get("projection_fingerprint") == PROJECTION_FINGERPRINT else None
        build_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        staging = paths.builds / f".staging-{build_id}"
        final = paths.builds / build_id
        staging.mkdir(parents=True, exist_ok=False)
        try:
            # Carry every historical run forward (immutable, hard-linked).
            runs: list[dict[str, Any]] = list(prev_meta.get("runs") or [])
            for run in runs:
                _link_tree(previous / "runs" / run["run_key"], staging / "runs" / run["run_key"])
            known = {run["run_key"] for run in runs}

            if reuse_previous is None:
                # Re-project the latest runs with the current code; older runs keep their rows.
                latest_keys = set((prev_meta.get("latest") or {}).values())
                for key in latest_keys:
                    shutil.rmtree(staging / "runs" / str(key), ignore_errors=True)
                runs = [run for run in runs if run["run_key"] not in latest_keys]
                known = {run["run_key"] for run in runs}
            candidate = _refresh_candidate(paths, reuse_previous, prev_meta, staging, known, say)
            if candidate and candidate["run_key"] not in known:
                runs.append(candidate)
            release = _refresh_release(paths, reuse_previous, prev_meta, staging, known, say)
            if release and release["run_key"] not in known:
                runs.append(release)

            meta = {
                "index_schema_version": INDEX_SCHEMA_VERSION,
                "index_build_version": INDEX_BUILD_VERSION,
                "projection_fingerprint": PROJECTION_FINGERPRINT,
                "build_id": build_id,
                "built_at": _now(),
                "dashboard_indexer_git_sha": _git_sha(),
                "scan_dir": str(paths.scan_dir),
                "build_root": str(paths.build_root),
                "source_state": source_state(paths),
                "candidate_parts": candidate["parts"] if candidate else prev_meta.get("candidate_parts", {}),
                "latest": {"candidate": (candidate or {}).get("run_key"), "release": (release or {}).get("run_key")},
                "runs": runs,
                "pillar_max": pillar_maxima(),
            }
            say("Evaluating findings", 0.9)
            from scripts.dashboard import findings_rules  # local import: rules read the staged tables
            meta["findings"] = findings_rules.evaluate_build(staging, meta, previous)
            _validate(staging, meta)
            meta["refresh_seconds"] = round(time.time() - started, 1)
            (staging / "index_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
            staging.rename(final)
            tmp = paths.current_pointer.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"build_id": build_id}), encoding="utf-8")
            os.replace(tmp, paths.current_pointer)
            _write_status(paths, {"ok": True, "build_id": build_id, "at": _now(),
                                  "seconds": meta["refresh_seconds"]})
            say("Done", 1.0)
            return meta
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            _write_status(paths, {"ok": False, "error": f"{type(exc).__name__}: {exc}", "at": _now(),
                                  "kept_build": previous.name if previous else None})
            raise


def _refresh_candidate(paths, previous, prev_meta, staging, known, say) -> dict[str, Any] | None:
    sources = candidate_sources(paths.scan_dir)
    if not sources:
        return None
    prev_parts: dict[str, dict] = prev_meta.get("candidate_parts") or {}
    prev_run = (prev_meta.get("latest") or {}).get("candidate")
    work = staging / "_candidate"
    parts: dict[str, dict] = {}
    for index, source in enumerate(sources):
        say(f"Candidate: {source['part']}", 0.6 * index / len(sources))
        cached = prev_parts.get(source["part"])
        if previous and prev_run and cached and cached["cache_key"] == source["cache_key"]:
            for table in TABLES:
                src = previous / "runs" / prev_run / table / f"{source['part']}.parquet"
                dest = work / table / f"{source['part']}.parquet"
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.link(src, dest)
            parts[source["part"]] = {**cached}
            continue
        rows, count = _parse_candidate_part(source)
        _write_tables(work, source["part"], rows)
        configs = sorted({r["config_fingerprint"] for r in rows.get("products", []) if r["config_fingerprint"]})
        parts[source["part"]] = {**source, "products": count, "configs": configs}
    configs = sorted({c for part in parts.values() for c in part.get("configs", [])})
    run_key = _run_key(
        "candidate", configs,
        sorted((name, part["cache_key"]) for name, part in parts.items()),
        sorted({part.get("stage_code") or "" for part in parts.values()}),
        sorted({part.get("reference_data") or "" for part in parts.values()}),
    )
    if run_key in known:
        shutil.rmtree(work)  # identical inputs: the carried-forward run already holds these rows
    else:
        (staging / "runs").mkdir(parents=True, exist_ok=True)
        work.rename(staging / "runs" / run_key)
    versions = sorted({_config_identity(json.loads(c))[0] or "" for c in configs if c.startswith("{")})
    return {
        "run_key": run_key, "plane": "candidate", "fidelity": FIDELITY_FULL,
        "run_time": max((p.get("generated_at") or "" for p in parts.values()), default=None),
        "products": sum(p.get("products", 0) for p in parts.values()),
        "config_versions": versions, "config_fingerprints": configs,
        "artifact_stage_code_fingerprints": sorted({p.get("stage_code") for p in parts.values() if p.get("stage_code")}),
        "artifact_reference_data_fingerprints": sorted({p.get("reference_data") for p in parts.values() if p.get("reference_data")}),
        "source": str(paths.scan_dir), "parts": parts,
    }


def _refresh_release(paths, previous, prev_meta, staging, known, say) -> dict[str, Any] | None:
    source = release_source(paths.build_root)
    if source is None:
        return None
    run_key = _run_key("release", source["schema_version"], source["config_checksum"],
                       source["db_version"], source["identity"])
    if run_key in known:
        return next(run for run in prev_meta["runs"] if run["run_key"] == run_key)
    core = _release_core_rows(source["db_path"])
    reuse: dict[str, str] = {}
    prev_release = (prev_meta.get("latest") or {}).get("release")
    if previous and prev_release:
        prev_products = _read_run_table(previous / "runs" / prev_release, "products").select(["dsld_id", "blob_sha256"])
        for pid, sha in zip(prev_products.column("dsld_id").to_pylist(), prev_products.column("blob_sha256").to_pylist()):
            if sha and source["blob_hashes"].get(pid) == sha:
                reuse[pid] = sha
    rows: dict[str, list] = {}
    blob_dir = paths.build_root / "detail_blobs"
    todo = [pid for pid in core if pid not in reuse]
    for index, pid in enumerate(todo):
        if index % 500 == 0:
            say(f"Release blobs {index}/{len(todo)}", 0.6 + 0.3 * index / max(len(todo), 1))
        blob_path = blob_dir / f"{pid}.json"
        blob = json.loads(blob_path.read_text(encoding="utf-8")) if blob_path.exists() else {}
        _merge(rows, project_product(blob, source_part="release", blob_sha256=source["blob_hashes"].get(pid),
                                     core=core[pid]))
    run_dir = staging / "runs" / run_key
    _write_tables(run_dir, "changed", rows)
    if reuse:
        keep = pa.array(sorted(reuse))
        for table in TABLES:
            old = _read_run_table(previous / "runs" / prev_release, table)
            kept = old.filter(pds.field("dsld_id").isin(keep)) if old.num_rows else old
            pq.write_table(kept, run_dir / table / "reused.parquet")
    configs = sorted({r["config_fingerprint"] for r in rows.get("products", []) if r["config_fingerprint"]})
    return {
        "run_key": run_key, "plane": "release", "fidelity": FIDELITY_RELEASE,
        "run_time": source["generated_at"], "products": len(core),
        "config_versions": sorted({row.get("quality_score_version") or "" for row in core.values()}),
        "config_fingerprints": configs, "export_schema_version": source["schema_version"],
        "db_version": source["db_version"], "scoring_version": source["scoring_version"],
        "source": str(paths.build_root), "reused_products": len(reuse),
    }


def _validate(staging: Path, meta: dict[str, Any]) -> None:
    for run in meta["runs"]:
        run_dir = staging / "runs" / run["run_key"]
        if not run_dir.exists():
            raise RuntimeError(f"run {run['run_key']} is missing from the build")
        count = _read_run_table(run_dir, "products").num_rows
        if count != run["products"]:
            raise RuntimeError(f"run {run['run_key']}: {count} product rows, expected {run['products']}")


def _write_status(paths: IndexPaths, status: dict[str, Any]) -> None:
    paths.cache_root.mkdir(parents=True, exist_ok=True)
    tmp = paths.status_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    os.replace(tmp, paths.status_file)


def backfill(paths: IndexPaths, db_paths: Iterable[Path]) -> dict[str, Any]:
    """Add older catalogs as pillar-totals-only runs (deduplicated), as a new build."""
    with _refresh_lock(paths.cache_root):
        previous = current_build(paths)
        if previous is None:
            raise RuntimeError("run `refresh` before `backfill`")
        meta = _load_meta(previous)
        build_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        staging = paths.builds / f".staging-{build_id}"
        _link_tree(previous, staging)
        known = {run["run_key"] for run in meta["runs"]}
        added = []
        for db_path in db_paths:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                columns = {row[1] for row in conn.execute("PRAGMA table_info(products_core)")}
                if "quality_score_v4_100" not in columns:
                    continue
                core_rows = [dict(row) for row in conn.execute("SELECT * FROM products_core")]
            exported = max((row.get("exported_at") or "" for row in core_rows), default="")
            versions = sorted({row.get("quality_score_version") or "" for row in core_rows})
            run_key = _run_key("backfill", versions, exported, len(core_rows))
            if run_key in known:
                continue
            rows: dict[str, list] = {}
            for row in core_rows:
                projected = project_product({}, source_part="backfill", core=row)
                rows.setdefault("products", []).extend(projected["products"])
            _write_tables(staging / "runs" / run_key, "backfill", {"products": rows.get("products", [])})
            run = {"run_key": run_key, "plane": "backfill", "fidelity": FIDELITY_PILLARS,
                   "run_time": exported, "products": len(core_rows), "config_versions": versions,
                   "config_fingerprints": [], "source": str(db_path)}
            meta["runs"].append(run)
            known.add(run_key)
            added.append(run)
        meta.update({"build_id": build_id, "built_at": _now()})
        _validate(staging, meta)
        (staging / "index_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
        staging.rename(paths.builds / build_id)
        tmp = paths.current_pointer.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"build_id": build_id}), encoding="utf-8")
        os.replace(tmp, paths.current_pointer)
        return {"added": added, "build_id": build_id}


def gc(paths: IndexPaths, keep: int = 2) -> list[str]:
    """Remove builds older than the newest ``keep``; never the current build."""
    current = current_build(paths)
    builds = sorted((p for p in paths.builds.iterdir() if p.is_dir() and not p.name.startswith(".")),
                    key=lambda p: p.name) if paths.builds.exists() else []
    removed = []
    for build in builds[:-keep]:
        if current is not None and build == current:
            continue
        shutil.rmtree(build)
        removed.append(build.name)
    return removed


# --------------------------------------------------------------------------- reader

class IndexReader:
    """Column-projected, filter-pushed reads over the current build."""

    def __init__(self, paths: IndexPaths):
        self.paths = paths
        self.build = current_build(paths)
        self.meta = _load_meta(self.build)

    @property
    def available(self) -> bool:
        return self.build is not None

    def runs(self) -> list[dict[str, Any]]:
        return sorted(self.meta.get("runs") or [], key=lambda run: run.get("run_time") or "")

    def run(self, run_key: str | None) -> dict[str, Any] | None:
        return next((run for run in self.meta.get("runs") or [] if run["run_key"] == run_key), None)

    def latest(self, plane: str) -> str | None:
        return (self.meta.get("latest") or {}).get(plane)

    def table(self, run_key: str, table: str, columns: list[str] | None = None, filter=None) -> pa.Table:
        if self.build is None or run_key is None:
            return pa.Table.from_pylist([], schema=TABLES[table]).select(columns or TABLES[table].names)
        directory = self.build / "runs" / run_key / table
        if not directory.exists():
            return pa.Table.from_pylist([], schema=TABLES[table]).select(columns or TABLES[table].names)
        dataset = pds.dataset(str(directory), format="parquet", schema=TABLES[table])
        return dataset.to_table(columns=columns, filter=filter)

    def frame(self, run_key: str, table: str, columns: list[str] | None = None, filter=None):
        return self.table(run_key, table, columns, filter).to_pandas()

    def product(self, run_key: str, dsld_id: str) -> dict[str, Any]:
        """Everything Product Trace needs for one product, read lazily."""
        match = pds.field("dsld_id") == str(dsld_id)
        out = {name: self.frame(run_key, name, filter=match) for name in TABLES if name != "slim"}
        slim = self.table(run_key, "slim", filter=match).column("slim_json").to_pylist()
        out["slim"] = json.loads(slim[0]) if slim else None
        return out

    def label_records(self) -> list[dict[str, Any]]:
        """Release label-trust inputs for ``data_loader.compute_label_trust``."""
        run_key = self.latest("release")
        if run_key is None:
            return []
        return [json.loads(text) for text in self.table(run_key, "label_records").column("record_json").to_pylist()]

    def findings(self):
        import pandas as pd
        path = self.build / "findings.parquet" if self.build else None
        return pd.read_parquet(path) if path and path.exists() else pd.DataFrame()

    def staleness(self) -> dict[str, Any]:
        """Compare indexed source identities with what is on disk now (manifests only)."""
        now = source_state(self.paths)
        indexed = self.meta.get("source_state") or {}
        changed = sorted(part for part, key in now["candidate"].items() if indexed.get("candidate", {}).get(part) != key)
        removed = sorted(set(indexed.get("candidate", {})) - set(now["candidate"]))
        return {
            "indexed": self.available,
            "candidate_changed": changed,
            "candidate_removed": removed,
            "release_changed": now["release"] != indexed.get("release"),
            "stale": (not self.available) or bool(changed or removed) or now["release"] != indexed.get("release"),
        }


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["refresh", "backfill", "status", "gc"])
    parser.add_argument("databases", nargs="*", help="catalog DBs for backfill")
    parser.add_argument("--scan-dir", help="pipeline products dir (default scripts/products)")
    parser.add_argument("--build-root", help="release dist dir (default scripts/dist)")
    parser.add_argument("--cache-root", help="index cache dir (default scripts/.cache/dashboard)")
    parser.add_argument("--keep", type=int, default=2, help="builds kept by gc")
    args = parser.parse_args(argv)
    paths = default_paths(args.scan_dir, args.build_root, args.cache_root)
    if args.command == "refresh":
        meta = refresh(paths, progress=lambda message, fraction: print(f"[{fraction:4.0%}] {message}", flush=True))
        print(json.dumps({"build_id": meta["build_id"], "latest": meta["latest"],
                          "seconds": meta["refresh_seconds"], "findings": meta.get("findings")}, indent=2))
    elif args.command == "backfill":
        print(json.dumps(backfill(paths, [Path(p) for p in args.databases]), indent=2, default=str))
    elif args.command == "status":
        reader = IndexReader(paths)
        status = json.loads(paths.status_file.read_text()) if paths.status_file.exists() else {}
        print(json.dumps({"build": reader.build.name if reader.build else None, "status": status,
                          "staleness": reader.staleness(),
                          "runs": [{k: r.get(k) for k in ("run_key", "plane", "fidelity", "run_time", "products",
                                                          "config_versions")} for r in reader.runs()]},
                         indent=2))
    else:
        print(json.dumps({"removed": gc(paths, keep=args.keep)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
