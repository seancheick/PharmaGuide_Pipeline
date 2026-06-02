#!/usr/bin/env python3
"""Phase A1 — Full-corpus v4-vs-shipped-v3 delta runner.

Audit-only. Scores every enriched product with the v4 shadow scorer and
compares to the **shipped v3 scored output** (NOT a fresh re-score). The
cutover question is "does v4 preserve what shipped?", not "does v4 match
today's local v3 code/config?" — so the baseline is the scored artifacts
already on disk (`output_*_scored/scored/...`). A `--rescore-v3` mode is
reserved for drift checks but is NOT the default.

Outputs (under reports/v4_corpus_delta/):
  - delta.csv          one row per product (scores, verdicts, flags, dims)
  - histogram.json     |delta| band distribution + summary
  - large_deltas.md    every |delta| >= --large-threshold (default 50),
                       grouped by class + flag — the bug-finding surface
  - verdict_flips.csv  v3 vs v4 verdict disagreements (feeds Tier-1 safety)
  - provenance.json    baseline artifact paths, mtimes, count, hash +
                       products_core reconciliation

Reuses helpers from v4_shadow_canary_report.py (no duplication):
  build_enriched_index, build_scored_index, extract_v3_sections,
  diagnose_compression, _iter_products, _dsld_id, _num, _safe_dict.

This module never mutates inputs and never changes scores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from score_supplements_v4_shadow import score_product_v4_shadow  # noqa: E402
import v4_shadow_canary_report as canary  # noqa: E402

DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_DIST_DB = SCRIPTS_ROOT / "dist" / "pharmaguide_core.db"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_corpus_delta"

# |delta| histogram band edges.
BANDS = [(0.0, 10.0), (10.0, 25.0), (25.0, 50.0), (50.0, 100.0), (100.0, float("inf"))]
BAND_LABELS = ["0-10", "10-25", "25-50", "50-100", "100+"]


def _band_label(abs_delta: float) -> str:
    for (lo, hi), label in zip(BANDS, BAND_LABELS):
        if lo <= abs_delta < hi:
            return label
    return BAND_LABELS[-1]


def _v3_completeness_status(scored: Dict[str, Any]) -> str:
    """SCORED / NOT_SCORED / NUTRITION_ONLY from the shipped v3 record.

    These are NOT safety severities — tracked separately so completeness-gate
    transitions don't pollute the safety-downgrade count (per plan B1).
    """
    verdict = str(scored.get("verdict") or "").strip().upper()
    if verdict in ("NOT_SCORED", "NUTRITION_ONLY"):
        return verdict
    basis = str(scored.get("score_basis") or "").strip().lower()
    if "nutrition_only" in basis:
        return "NUTRITION_ONLY"
    return "SCORED"


def _file_provenance(paths: List[Path]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in sorted(paths):
        try:
            stat = p.stat()
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            out.append({
                "path": str(p.relative_to(REPO_ROOT)),
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "bytes": stat.st_size,
                "sha256_16": h,
            })
        except OSError:
            continue
    return out


def build_rows(
    enriched_index: Dict[str, Dict[str, Any]],
    scored_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """One comparison row per shipped (scored) product that also has an
    enriched blob to feed v4. Shipped scored universe is the baseline.
    """
    rows: List[Dict[str, Any]] = []
    for dsld_id, scored in scored_index.items():
        v3_score = canary._num(scored.get("score_100_equivalent"))
        v3_verdict = scored.get("verdict")
        v3_safety_verdict = scored.get("safety_verdict")
        completeness = _v3_completeness_status(scored)
        v3_sections = canary.extract_v3_sections(scored)

        enriched = enriched_index.get(dsld_id)
        base = {
            "dsld_id": dsld_id,
            "brand_name": scored.get("brand_name") or (enriched or {}).get("brand_name"),
            "product_name": scored.get("product_name") or (enriched or {}).get("product_name"),
            "primary_class": (enriched or {}).get("primary_type") or "unknown",
            "v3_shipped_score": v3_score,
            "v3_verdict": v3_verdict,
            "v3_safety_verdict": v3_safety_verdict,
            "completeness_status": completeness,
            "v3_sections": v3_sections,
        }

        if enriched is None:
            rows.append({**base, "status": "missing_enriched", "v4_score": None,
                         "v4_raw_score": None, "v4_verdict": None, "v4_module": None,
                         "v4_dimensions": {}, "v4_dimension_metadata": {},
                         "v4_confidence_detail": None, "compression_flags": []})
            continue

        shadow = score_product_v4_shadow(enriched)
        breakdown = canary._safe_dict(shadow.get("shadow_score_v4_breakdown"))
        completeness_gate = canary._safe_dict(breakdown.get("completeness_gate"))
        module = canary._safe_dict(breakdown.get("module"))
        module_metadata = canary._safe_dict(module.get("metadata"))
        dimensions = canary._safe_dict(module.get("dimensions"))
        dimension_metadata = {
            name: canary._safe_dict(payload).get("metadata", {})
            for name, payload in dimensions.items()
        }
        confidence = breakdown.get("confidence")

        v4_score = canary._num(shadow.get("shadow_score_v4_100"))
        v4_raw = canary._num(module.get("raw_score_100"))

        row = {
            **base,
            "status": "scored" if v4_score is not None else "shadow_unscored",
            "v4_score": v4_score,
            "v4_raw_score": v4_raw,
            "v4_verdict": shadow.get("shadow_score_v4_verdict"),
            "v4_module": shadow.get("shadow_score_v4_module"),
            "v4_dimensions": {n: canary._safe_dict(p).get("score") for n, p in dimensions.items()},
            "v4_dimension_metadata": dimension_metadata,
            # Phase 4: verification is an additive bonus (0-8), no longer a core
            # dimension. Surface its score + the pre-rescale 0-15 trust score.
            "v4_verification_bonus": canary._num(
                canary._safe_dict(module.get("verification_bonus")).get("score")
            ),
            "v4_verification_trust_0_15": canary._num(
                canary._safe_dict(
                    canary._safe_dict(module.get("verification_bonus")).get("metadata")
                ).get("source_trust_score_0_15")
            ),
            # Additive bonuses / penalty that live outside `dimensions` (so the
            # side-by-side review surface shows the full score composition, not
            # just the 4 core dimensions).
            "v4_manufacturer_bonus": canary._num(
                canary._safe_dict(module.get("manufacturer_trust")).get("score")
            ),
            "v4_safety_hygiene": canary._num(
                canary._safe_dict(module.get("safety_hygiene_base")).get("score")
            ),
            "v4_manufacturer_violations": canary._num(
                canary._safe_dict(module.get("manufacturer_violations")).get("score")
            ),
            "v4_module_metadata": module_metadata,
            "v4_completeness_missing": list(completeness_gate.get("missing_fields") or []),
            "v4_completeness_soft_missing": list(completeness_gate.get("soft_missing") or []),
            "v4_completeness_score_cap": completeness_gate.get("score_cap"),
            "v4_completeness_verdict_ceiling": completeness_gate.get("verdict_ceiling"),
            "v4_confidence_detail": confidence if isinstance(confidence, dict) else None,
        }
        # deltas (production score + raw rubric) for diagnose_compression()
        if v3_score is not None and v4_score is not None:
            row["score_delta_vs_v3"] = round(v4_score - v3_score, 4)
        else:
            row["score_delta_vs_v3"] = None
        if v3_score is not None and v4_raw is not None:
            row["raw_score_delta_vs_v3"] = round(v4_raw - v3_score, 4)
        else:
            row["raw_score_delta_vs_v3"] = None
        row["compression_flags"] = canary.diagnose_compression(row)
        rows.append(row)
    return rows


def _band_summary(rows: List[Dict[str, Any]], delta_key: str) -> Dict[str, Any]:
    band_counts: Counter = Counter()
    deltas: List[float] = []
    for r in rows:
        d = canary._num(r.get(delta_key))
        if d is not None:
            deltas.append(d)
            band_counts[_band_label(abs(d))] += 1
    ds = sorted(deltas)
    n = len(ds)
    return {
        "band_counts": {label: band_counts.get(label, 0) for label in BAND_LABELS},
        "delta_stats": {
            "min": round(ds[0], 2) if n else None,
            "p50": round(ds[n // 2], 2) if n else None,
            "max": round(ds[-1], 2) if n else None,
            "mean": round(sum(ds) / n, 2) if n else None,
        },
    }


def summarize(rows: List[Dict[str, Any]], large_threshold: float) -> Dict[str, Any]:
    """Summary over ALL scored rows + a shipped-universe-only subset.

    Reports BOTH production-score and raw-rubric delta bands. Since Phase 9,
    production score is the raw rubric score; the two distributions should
    normally match. Both fields stay visible while downstream tooling migrates
    away from the old calibrated-score vocabulary.
    """
    flag_counts: Counter = Counter()
    module_counts: Counter = Counter()
    scored_rows = [r for r in rows if r.get("status") != "missing_enriched" and r.get("v4_score") is not None]
    shipped_rows = [r for r in scored_rows if r.get("in_shipped_universe")]
    for r in scored_rows:
        module_counts[str(r.get("v4_module"))] += 1
        for f in r.get("compression_flags", []):
            flag_counts[f] += 1
    production_all = _band_summary(scored_rows, "score_delta_vs_v3")
    raw_all = _band_summary(scored_rows, "raw_score_delta_vs_v3")
    return {
        "total_rows": len(rows),
        "scored": len(scored_rows),
        "shipped_scored": len(shipped_rows),
        "missing_enriched": sum(1 for r in rows if r.get("status") == "missing_enriched"),
        "production_band_counts": production_all["band_counts"],
        "production_delta_stats": production_all["delta_stats"],
        "raw_band_counts": raw_all["band_counts"],
        "raw_delta_stats": raw_all["delta_stats"],
        "shipped_production_bands": _band_summary(shipped_rows, "score_delta_vs_v3")["band_counts"],
        "shipped_raw_bands": _band_summary(shipped_rows, "raw_score_delta_vs_v3")["band_counts"],
        "compression_flag_counts": dict(flag_counts.most_common()),
        "module_counts": dict(module_counts.most_common()),
        "large_threshold": large_threshold,
        "raw_large_delta_count": sum(
            1 for r in scored_rows
            if (canary._num(r.get("raw_score_delta_vs_v3")) is not None
                and abs(canary._num(r.get("raw_score_delta_vs_v3"))) >= large_threshold)
        ),
        "production_large_delta_count": sum(
            1 for r in scored_rows
            if (canary._num(r.get("score_delta_vs_v3")) is not None
                and abs(canary._num(r.get("score_delta_vs_v3"))) >= large_threshold)
        ),
    }


def write_delta_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "dsld_id", "brand_name", "product_name", "primary_class", "v4_module",
        "v3_shipped_score", "v4_raw_score", "v4_score", "score_delta_vs_v3",
        "raw_score_delta_vs_v3", "v3_verdict", "v3_safety_verdict", "v4_verdict",
        "completeness_status", "in_shipped_universe", "compression_flags",
        "excluded_dimensions", "v4_completeness_missing",
        "v4_completeness_soft_missing", "v4_completeness_score_cap",
        "v4_completeness_verdict_ceiling", "status",
    ]
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            excluded = canary._safe_dict(r.get("v4_module_metadata")).get("excluded_dimensions", [])
            w.writerow([
                r.get("dsld_id"), r.get("brand_name"), r.get("product_name"),
                r.get("primary_class"), r.get("v4_module"),
                r.get("v3_shipped_score"), r.get("v4_raw_score"), r.get("v4_score"),
                r.get("score_delta_vs_v3"), r.get("raw_score_delta_vs_v3"),
                r.get("v3_verdict"), r.get("v3_safety_verdict"), r.get("v4_verdict"),
                r.get("completeness_status"),
                r.get("in_shipped_universe"),
                "|".join(r.get("compression_flags", [])),
                "|".join(excluded) if isinstance(excluded, list) else "",
                "|".join(r.get("v4_completeness_missing", [])),
                "|".join(r.get("v4_completeness_soft_missing", [])),
                r.get("v4_completeness_score_cap"),
                r.get("v4_completeness_verdict_ceiling"),
                r.get("status"),
            ])


def load_shipped_universe(db_path: Path) -> set:
    """dsld_id set actually shipped in products_core (active-only ship gate).

    The scored outputs include discontinued products that build_final_db
    filters out; the cutover question is about the SHIPPED universe.
    """
    if not db_path.exists():
        return set()
    try:
        with sqlite3.connect(db_path) as conn:
            return {str(row[0]) for row in conn.execute("SELECT dsld_id FROM products_core")}
    except sqlite3.Error:
        return set()


def write_large_deltas_md(rows: List[Dict[str, Any]], path: Path, threshold: float,
                          delta_key: str = "raw_score_delta_vs_v3") -> int:
    """Surface large deltas on the RAW score by default.

    Since Phase 9, production score equals raw rubric score; raw remains the
    clearest name for the bug-finding surface. Only shipped-universe rows are
    listed (what reaches users at cutover).
    """
    large = [
        r for r in rows
        if r.get("in_shipped_universe")
        and canary._num(r.get(delta_key)) is not None
        and abs(canary._num(r.get(delta_key))) >= threshold
    ]
    large.sort(key=lambda r: abs(canary._num(r.get(delta_key)) or 0.0), reverse=True)
    by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in large:
        by_class[str(r.get("primary_class") or "unknown")].append(r)

    lines = [
        f"# Large v3↔v4 deltas (|delta| ≥ {threshold:g})",
        "",
        f"- Total large-delta products: {len(large)}",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Baseline = shipped v3 scored outputs. Rows are selected by raw delta by default",
        "because v4 production score is now the raw rubric score.",
        "Negative = v4 scores LOWER than v3 (under-credit). Positive = v4 higher.",
        "",
    ]
    for cls in sorted(by_class):
        group = by_class[cls]
        lines.append(f"## {cls} ({len(group)})")
        lines.append("")
        lines.append("| dsld | product | module | v3 | v4 raw | Δ raw | v4 score | Δ score | flags |")
        lines.append("|---|---|---|---:|---:|---:|---:|---:|---|")
        for r in group:
            lines.append(
                f"| {r.get('dsld_id')} | {str(r.get('product_name'))[:40]} | "
                f"{r.get('v4_module')} | {r.get('v3_shipped_score')} | "
                f"{r.get('v4_raw_score')} | {r.get('raw_score_delta_vs_v3')} | "
                f"{r.get('v4_score')} | {r.get('score_delta_vs_v3')} | "
                f"{', '.join(r.get('compression_flags', []))} |"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n")
    return len(large)


def write_verdict_flips_csv(rows: List[Dict[str, Any]], path: Path) -> int:
    # Safety lattice (per plan B1): higher = more cautious. NOT_SCORED /
    # NUTRITION_ONLY are NOT safety severities — tracked but not downgrades.
    SAFETY_RANK = {"BLOCKED": 4, "UNSAFE": 3, "CAUTION": 2, "POOR": 1, "SAFE": 0}
    flips = []
    for r in rows:
        v3v = str(r.get("v3_verdict") or "")
        v4v = str(r.get("v4_verdict") or "")
        if v3v and v4v and v3v != v4v:
            v3_rank = SAFETY_RANK.get(v3v)
            v4_rank = SAFETY_RANK.get(v4v)
            is_safety_downgrade = (
                v3_rank is not None and v4_rank is not None
                and v3_rank >= SAFETY_RANK["CAUTION"] and v4_rank < v3_rank
            )
            r["_flip_kind"] = (
                "SAFETY_DOWNGRADE" if is_safety_downgrade
                else "completeness_transition" if v4v in ("NOT_SCORED", "NUTRITION_ONLY")
                else "other"
            )
            flips.append(r)
    flips.sort(key=lambda r: (r.get("_flip_kind") != "SAFETY_DOWNGRADE", not r.get("in_shipped_universe")))
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["flip_kind", "in_shipped_universe", "dsld_id", "product_name",
                    "primary_class", "v3_verdict", "v3_safety_verdict", "v4_verdict",
                    "completeness_status", "v3_shipped_score", "v4_score"])
        for r in flips:
            w.writerow([
                r.get("_flip_kind"), r.get("in_shipped_universe"),
                r.get("dsld_id"), r.get("product_name"), r.get("primary_class"),
                r.get("v3_verdict"), r.get("v3_safety_verdict"), r.get("v4_verdict"),
                r.get("completeness_status"), r.get("v3_shipped_score"), r.get("v4_score"),
            ])
    return sum(1 for r in flips if r.get("_flip_kind") == "SAFETY_DOWNGRADE" and r.get("in_shipped_universe"))


def reconcile_products_core(unique_count: int, db_path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {"products_core_db": str(db_path), "products_core_count": None,
                            "scored_universe_count": unique_count, "matches": None}
    if not db_path.exists():
        info["note"] = "products_core db not found — reconciliation skipped"
        return info
    try:
        with sqlite3.connect(db_path) as conn:
            info["products_core_count"] = conn.execute(
                "SELECT COUNT(*) FROM products_core"
            ).fetchone()[0]
        info["matches"] = info["products_core_count"] == unique_count
        if not info["matches"]:
            info["delta"] = unique_count - (info["products_core_count"] or 0)
            info["note"] = ("scored universe differs from products_core — "
                            "investigate dedup/active-gate before trusting deltas")
    except sqlite3.Error as exc:
        info["note"] = f"reconciliation error: {exc}"
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-root", type=Path, default=DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--dist-db", type=Path, default=DEFAULT_DIST_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--large-threshold", type=float, default=50.0)
    parser.add_argument("--rescore-v3", action="store_true",
                        help="(reserved) re-score v3 from current code instead of shipped artifacts")
    args = parser.parse_args()

    if args.rescore_v3:
        print("ERROR: --rescore-v3 not implemented; default baseline is shipped v3 artifacts.",
              file=sys.stderr)
        return 2

    enriched_index = canary.build_enriched_index(args.products_root)
    scored_index = canary.build_scored_index(args.products_root)
    if not scored_index:
        print(f"ERROR: no shipped scored outputs under {args.products_root}", file=sys.stderr)
        return 1

    shipped_universe = load_shipped_universe(args.dist_db)
    rows = build_rows(enriched_index, scored_index)
    for r in rows:
        r["in_shipped_universe"] = (not shipped_universe) or (r.get("dsld_id") in shipped_universe)
    summary = summarize(rows, args.large_threshold)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    write_delta_csv(rows, out / "delta.csv")
    large_n = write_large_deltas_md(rows, out / "large_deltas.md", args.large_threshold)
    shipped_safety_downgrades = write_verdict_flips_csv(rows, out / "verdict_flips.csv")

    enriched_files = list(args.products_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"))
    scored_files = list(args.products_root.glob("output_*_scored/scored/scored_cleaned_batch_*.json"))
    provenance = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "baseline": "shipped_v3_scored_outputs",
        "enriched_files": _file_provenance(enriched_files),
        "scored_files": _file_provenance(scored_files),
        "enriched_unique_dsld": len(enriched_index),
        "scored_unique_dsld": len(scored_index),
        "products_core_reconciliation": reconcile_products_core(len(scored_index), args.dist_db),
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    summary["shipped_safety_downgrades"] = shipped_safety_downgrades
    summary["raw_large_deltas_written"] = large_n
    (out / "histogram.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    recon = provenance["products_core_reconciliation"]
    if recon.get("matches") is False:
        print(f"\nNOTE: scored universe ({recon['scored_universe_count']}) != "
              f"products_core ({recon['products_core_count']}) — shipped-universe rows "
              f"tagged in_shipped_universe; headline gates use the shipped subset.",
              file=sys.stderr)
    if shipped_safety_downgrades:
        print(f"\n*** BLOCKER: {shipped_safety_downgrades} shipped products are SAFETY DOWNGRADES "
              f"(v3 CAUTION+ → lower v4). See verdict_flips.csv (flip_kind=SAFETY_DOWNGRADE). ***",
              file=sys.stderr)
    print(f"\nWrote {out}/ : delta.csv, large_deltas.md (raw |Δ|≥{args.large_threshold:g}: {large_n}), "
          f"verdict_flips.csv, histogram.json, provenance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
