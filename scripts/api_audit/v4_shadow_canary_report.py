#!/usr/bin/env python3
"""P1.5 v4 shadow canary comparator.

Audit-only tool. It runs the v4 shadow scorer against the curated canary
set, compares v4 rank order to the v3 shipped-score baseline inside each
primary class, and emits an omega decision signal:

    generic_ok_for_now        — omega rank order within +/- 1
    review_omega_module       — omega rank order drift exceeds +/- 1
    insufficient_omega_data   — fewer than 2 omega canaries scored

The tool does not tune or mutate scores.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from score_supplements_v4_shadow import score_product_v4_shadow


OMEGA_CLASSES = {"fish_oil", "omega", "omega_3", "omega-3"}
OMEGA_REVIEW_SCORE_DROP = -15.0
DEFAULT_CANARY_PATH = SCRIPTS_ROOT / "data" / "canary_products.json"
DEFAULT_ENRICHED_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_REPORT_ROOT = SCRIPTS_ROOT / "api_audit" / "reports"


def load_canaries(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text())
    rows = data.get("canaries", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"Canary file must contain a list or canaries[]: {path}")
    normalized: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["canary_index"] = idx
        item["dsld_id"] = str(item.get("dsld_id") or "").strip()
        normalized.append(item)
    return [row for row in normalized if row.get("dsld_id")]


def build_enriched_index(root: Path) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for path in root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        for product in _iter_products(path):
            dsld_id = _dsld_id(product)
            if dsld_id:
                index.setdefault(dsld_id, product)
    return index


def build_scored_index(root: Path) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for path in root.glob("output_*_scored/scored/scored_cleaned_batch_*.json"):
        for product in _iter_products(path):
            dsld_id = _dsld_id(product)
            if dsld_id:
                index.setdefault(dsld_id, product)
    return index


def score_canaries(
    canaries: Iterable[Dict[str, Any]],
    enriched_index: Dict[str, Dict[str, Any]],
    scored_index: Dict[str, Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    scored_index = scored_index or {}
    rows: List[Dict[str, Any]] = []
    for canary in canaries:
        dsld_id = str(canary.get("dsld_id") or "")
        v3_sections = extract_v3_sections(scored_index.get(dsld_id, {}))
        base = {
            "canary_index": canary.get("canary_index"),
            "dsld_id": dsld_id,
            "brand_name": canary.get("brand_name"),
            "product_name": canary.get("product_name"),
            "primary_class": canary.get("primary_class"),
            "v3_shipped_score": canary.get("v3_shipped_score"),
            "v3_shipped_verdict": canary.get("v3_shipped_verdict"),
            "v3_sections": v3_sections,
            "edge_cases": list(canary.get("edge_cases", [])) if isinstance(canary.get("edge_cases"), list) else [],
        }
        product = enriched_index.get(dsld_id)
        if product is None:
            rows.append(
                {
                    **base,
                    "status": "missing_enriched",
                    "v4_score": None,
                    "v4_verdict": None,
                    "v4_confidence": None,
                    "v4_module": None,
                    "v4_dimensions": {},
                    "v4_confidence_detail": None,
                }
            )
            continue

        shadow = score_product_v4_shadow(product)
        breakdown = shadow.get("shadow_score_v4_breakdown", {})
        module = _safe_dict(breakdown.get("module"))
        dimensions = _safe_dict(module.get("dimensions"))
        confidence = breakdown.get("confidence") if isinstance(breakdown, dict) else None
        rows.append(
            {
                **base,
                "status": "scored" if shadow.get("shadow_score_v4_100") is not None else "shadow_unscored",
                "v4_score": shadow.get("shadow_score_v4_100"),
                "v4_verdict": shadow.get("shadow_score_v4_verdict"),
                "v4_confidence": shadow.get("shadow_score_v4_confidence"),
                "v4_module": shadow.get("shadow_score_v4_module"),
                "v4_dimensions": {
                    name: _safe_dict(payload).get("score")
                    for name, payload in dimensions.items()
                },
                "v4_confidence_detail": confidence if isinstance(confidence, dict) else None,
            }
        )
    return assign_rank_deltas(rows, group_key="primary_class")


def assign_rank_deltas(rows: List[Dict[str, Any]], group_key: str) -> List[Dict[str, Any]]:
    output = [dict(row) for row in rows]
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in output:
        groups.setdefault(str(row.get(group_key) or "unknown"), []).append(row)

    for group_rows in groups.values():
        expected = sorted(
            [row for row in group_rows if _num(row.get("v3_shipped_score")) is not None],
            key=lambda row: (_num(row.get("v3_shipped_score")) or -1.0),
            reverse=True,
        )
        actual = sorted(
            [row for row in group_rows if _num(row.get("v4_score")) is not None],
            key=lambda row: (_num(row.get("v4_score")) or -1.0),
            reverse=True,
        )
        expected_rank = {id(row): idx for idx, row in enumerate(expected, 1)}
        actual_rank = {id(row): idx for idx, row in enumerate(actual, 1)}
        for row in group_rows:
            erank = expected_rank.get(id(row))
            arank = actual_rank.get(id(row))
            row["expected_rank_in_group"] = erank
            row["actual_rank_in_group"] = arank
            row["rank_delta"] = (arank - erank) if erank is not None and arank is not None else None
            before = _num(row.get("v3_shipped_score"))
            after = _num(row.get("v4_score"))
            row["score_delta_vs_v3"] = round(after - before, 4) if before is not None and after is not None else None
            row["compression_flags"] = diagnose_compression(row)
    return output


def extract_v3_sections(scored_product: Dict[str, Any]) -> Dict[str, float | None]:
    breakdown = _safe_dict(scored_product.get("breakdown"))
    section_b = _safe_dict(breakdown.get("B"))
    return {
        "A": _num(_safe_dict(breakdown.get("A")).get("score")),
        "B": _num(section_b.get("score")),
        "C": _num(_safe_dict(breakdown.get("C")).get("score")),
        "D": _num(_safe_dict(breakdown.get("D")).get("score")),
        "E": _num(_safe_dict(breakdown.get("E")).get("score")),
        "violation_penalty": _num(breakdown.get("violation_penalty")),
        "B_bonuses": _num(section_b.get("bonuses")),
        "B_penalties": _num(section_b.get("penalties")),
    }


def diagnose_compression(row: Dict[str, Any]) -> List[str]:
    """Explain likely causes when v4 canary scores drop materially.

    This is diagnostic only. It should make P1.5 tuning conversations
    concrete before any rubric change is made.
    """
    flags: List[str] = []
    score_delta = _num(row.get("score_delta_vs_v3"))
    if score_delta is None or score_delta > -15.0:
        return flags

    v3_sections = _safe_dict(row.get("v3_sections"))
    v4_dimensions = _safe_dict(row.get("v4_dimensions"))
    v3_b = _num(v3_sections.get("B"))
    v4_trust = _num(v4_dimensions.get("trust")) or 0.0
    v4_transparency = _num(v4_dimensions.get("transparency")) or 0.0
    if v3_b is not None and v3_b >= 20.0 and (v4_trust + v4_transparency) <= 10.0:
        flags.append("v3_safety_purity_base_not_represented")

    confidence = _safe_dict(row.get("v4_confidence_detail"))
    label = _safe_dict(confidence.get("label_completeness"))
    label_drivers = set(str(driver) for driver in _safe_list(label.get("drivers")))
    if row.get("v4_dimensions", {}).get("dose") is None and "dose_window_not_evaluable_by_rda_proxy" in label_drivers:
        flags.append("dose_not_evaluable_with_large_score_drop")

    evidence_score = _num(v4_dimensions.get("evidence"))
    if evidence_score is not None and evidence_score < 6.0:
        flags.append("low_evidence_dimension")

    trust_score = _num(v4_dimensions.get("trust"))
    if trust_score is not None and trust_score <= 0.0:
        flags.append("zero_testing_trust_dimension")

    return flags


def summarize_records(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [row for row in rows if _num(row.get("v4_score")) is not None]
    missing = [row for row in rows if row.get("status") == "missing_enriched"]
    rank_deltas = [abs(int(row["rank_delta"])) for row in scored if row.get("rank_delta") is not None]
    omega_rows = [
        row for row in scored
        if str(row.get("primary_class") or "").strip().lower() in OMEGA_CLASSES
    ]
    omega_rank_deltas = [
        abs(int(row["rank_delta"])) for row in omega_rows if row.get("rank_delta") is not None
    ]
    omega_review_reasons: List[str] = []
    if omega_rank_deltas and max(omega_rank_deltas) > 1:
        omega_review_reasons.append("rank_order_drift")
    if any((_num(row.get("score_delta_vs_v3")) or 0.0) <= OMEGA_REVIEW_SCORE_DROP for row in omega_rows):
        omega_review_reasons.append("large_score_drop")
    if any(
        str(row.get("v3_shipped_verdict") or "").upper() == "SAFE"
        and str(row.get("v4_verdict") or "").upper() == "POOR"
        for row in omega_rows
    ):
        omega_review_reasons.append("safe_to_poor_transition")

    if len(omega_rows) < 2:
        omega_decision = "insufficient_omega_data"
    elif omega_review_reasons:
        omega_decision = "review_omega_module"
    else:
        omega_decision = "generic_ok_for_now"

    return {
        "total_canaries": len(rows),
        "scored": len(scored),
        "missing_enriched": len(missing),
        "max_abs_rank_delta": max(rank_deltas) if rank_deltas else None,
        "compression_flag_counts": _flag_counts(scored),
        "verdict_counts": _counts(row.get("v4_verdict") for row in scored),
        "confidence_counts": _counts(row.get("v4_confidence") for row in scored),
        "module_counts": _counts(row.get("v4_module") for row in scored),
        "omega": {
            "count": len(omega_rows),
            "max_abs_rank_delta": max(omega_rank_deltas) if omega_rank_deltas else None,
            "decision": omega_decision,
            "review_reasons": omega_review_reasons,
        },
    }


def write_reports(rows: List[Dict[str, Any]], summary: Dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "v4_shadow_canary_report.json"
    md_path = out_dir / "v4_shadow_canary_report.md"
    payload = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase": "P1.5_canary_comparator",
        },
        "summary": summary,
        "records": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    md_path.write_text(_markdown(summary, rows))
    return json_path, md_path


def _markdown(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# v4 Shadow Canary Report",
        "",
        f"- Total canaries: {summary['total_canaries']}",
        f"- Scored: {summary['scored']}",
        f"- Missing enriched: {summary['missing_enriched']}",
        f"- Max abs rank delta: {summary['max_abs_rank_delta']}",
        f"- Omega decision: **{summary['omega']['decision']}**",
        f"- Compression flags: {summary.get('compression_flag_counts', {})}",
        "",
        "| # | DSLD | Class | Product | v3 | v4 | Verdict | Conf | Rank Δ | Score Δ | Flags |",
        "|---:|---|---|---|---:|---:|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {idx} | {dsld} | {klass} | {product} | {v3} | {v4} | {verdict} | {conf} | {rank} | {delta} | {flags} |".format(
                idx=row.get("canary_index") or "",
                dsld=row.get("dsld_id") or "",
                klass=row.get("primary_class") or "",
                product=str(row.get("product_name") or "").replace("|", "\\|"),
                v3=_fmt(row.get("v3_shipped_score")),
                v4=_fmt(row.get("v4_score")),
                verdict=row.get("v4_verdict") or "",
                conf=row.get("v4_confidence") or "",
                rank=_fmt(row.get("rank_delta")),
                delta=_fmt(row.get("score_delta_vs_v3")),
                flags=", ".join(row.get("compression_flags", [])),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _iter_products(path: Path) -> Iterable[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("products", "items", "records"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        if _dsld_id(data):
            return [data]
    return []


def _dsld_id(product: Dict[str, Any]) -> str:
    for key in ("dsld_id", "id", "DSLD_ID", "label_id"):
        value = product.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any) -> str:
    number = _num(value)
    if number is None:
        return ""
    return f"{number:.1f}"


def _counts(values: Iterable[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        key = str(value or "missing")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _flag_counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        for flag in _safe_list(row.get("compression_flags")):
            key = str(flag)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canary", type=Path, default=DEFAULT_CANARY_PATH)
    parser.add_argument("--enriched-root", type=Path, default=DEFAULT_ENRICHED_ROOT)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    canaries = load_canaries(args.canary)
    enriched_index = build_enriched_index(args.enriched_root)
    scored_index = build_scored_index(args.enriched_root)
    rows = score_canaries(canaries, enriched_index, scored_index)
    summary = summarize_records(rows)
    out_dir = args.out_dir
    if out_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = DEFAULT_REPORT_ROOT / f"v4_shadow_canary_{stamp}"
    json_path, md_path = write_reports(rows, summary, out_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
