#!/usr/bin/env python3
"""P0.1a cert audit report — runs the resolver against the canary set + top 200
products with claimed certs, produces a JSON + CSV comparison report.

NO SCORING CHANGES. This is audit-only. The report tells us:
  - How many claimed certs resolve to each scope (sku / product_line / brand_only / needs_review / claimed_only)
  - For each product: current B4a (from products_core), proposed B4a (under v4 scope-aware rules), delta
  - Per-product details with matched_brand / matched_product / match_confidence

Usage:
  python scripts/api_audit/cert_audit_report.py [--top 200] [--out path]

Reads:
  - scripts/final_db_output/pharmaguide_core.db (products_core + detail blob shas)
  - scripts/final_db_output/detail_blobs/<dsld_id>.json (per-product blob)
  - scripts/data/cert_registry.json (via cert_resolver)
  - scripts/data/curated_overrides/cert_verification_overrides.json (via cert_resolver)

Writes:
  - scripts/api_audit/reports/cert_audit_v4_p01a_<timestamp>.json
  - scripts/api_audit/reports/cert_audit_v4_p01a_<timestamp>.csv
  - scripts/api_audit/reports/cert_audit_v4_p01a_<timestamp>_summary.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cert_resolver import CertRegistry, CertResolution, resolve  # noqa: E402

CORE_DB = SCRIPTS_ROOT / "final_db_output" / "pharmaguide_core.db"
BLOBS_DIR = SCRIPTS_ROOT / "final_db_output" / "detail_blobs"
REPORT_DIR = SCRIPTS_ROOT / "api_audit" / "reports"


# v4 scoring proposal: scope -> diminishing-returns points (see §10 + §16 P0.1a)
SCOPE_POINTS = {
    "sku": [8, 4, 2],
    "product_line": [6, 3, 1],
    "label_asserted_product": [2, 1, 0],
    "needs_review": [0, 0, 0],  # held until reviewer triages
    "brand_only": [0, 0, 0],  # routes to manufacturer trust D, not B4a in v4
    "claimed_only": [0, 0, 0],
}
B4A_HARD_CAP = 12  # mirrors score_supplements.py P0.1b/P0.1d contract
SCOPE_STRENGTH = {"sku": 3, "product_line": 2, "label_asserted_product": 1}


# --- Canary set (DSLD IDs from §12 of v4 spec) -------------------------------
# Only DSLD-resolvable IDs included; others tested via brand/product fallback.
CANARY = [
    {"id": 1, "name": "Thorne Magnesium Bisglycinate"},
    {"id": 10, "name": "Thorne Basic Prenatal"},
    {"id": 15, "dsld_id": "274081", "name": "Garden of Life Once Daily Prenatal Probiotic"},
    {"id": 22, "dsld_id": "305203", "name": "Transparent Labs KSM-66 Ashwagandha"},
    {"id": 1, "dsld_id": "298074", "name": "Thorne Magnesium Bisglycinate (alt id)"},
    # Many more canaries from §12, but only DSLD-mapped ones can flow through
    # the SQLite extractor. Others get smoke-tested via direct (brand,product)
    # input in the canary smoke test.
]


def _load_claimed_certs(blob: dict) -> list[str]:
    """Pull claimed_cert_programs from a v3 detail blob.

    v3 stores this under certification_detail / third_party_programs in
    different blob versions. Tries multiple shapes."""
    out: list[str] = []
    cd = blob.get("certification_detail") or {}
    tp = cd.get("third_party_programs") or {}
    programs = tp.get("programs") if isinstance(tp, dict) else None
    if isinstance(programs, list):
        for p in programs:
            if isinstance(p, dict):
                name = p.get("name") or p.get("program")
            else:
                name = p
            if name:
                out.append(str(name))
    # Some v3 blobs project directly
    direct = blob.get("named_cert_programs") or []
    if isinstance(direct, list):
        for p in direct:
            if p:
                out.append(str(p))
    # Dedup preserving order
    seen: set[str] = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _current_b4a(row: dict) -> float:
    """v3 currently emits the B4 sum into score_brand_trust? Actually B4 lives
    inside score_safety_purity. We don't have a per-B4a column — surface the
    aggregate B and let the report record context."""
    # We don't get per-B4a from products_core in v3. The audit shows:
    #   - claimed program count (proxy for current B4a contribution)
    #   - cert_programs list (raw claimed)
    # Real per-B4a comparison would require running the v3 scorer on the blob,
    # which we can do as a follow-up. For now, report the v3 raw claimed_count.
    cert_programs = row.get("cert_programs") or "[]"
    try:
        progs = json.loads(cert_programs) if isinstance(cert_programs, str) else cert_programs
    except json.JSONDecodeError:
        progs = []
    return 5.0 * min(len(progs), 3)  # v3 B4a: 5 per program, capped at 15


def _propose_b4a(resolutions: list[CertResolution]) -> float:
    """v4 B4a under scope-aware diminishing returns.

    Recency-gated: resolutions with scoring_blocked_reason (stale snapshot)
    are reported in the audit but contribute ZERO points. Production scorers
    obey the same rule via CertResolution.scores_points().
    """
    # Keep only the strongest scoring scope per normalized program. This mirrors
    # the production scorer's duplicate-proofing so the audit cannot overstate
    # v4 credit when the same program appears from multiple sources.
    best_scope_by_program: dict[str, str] = {}
    for r in resolutions:
        if not r.scores_points():
            continue
        if r.scope not in SCOPE_STRENGTH:
            continue
        program_key = (r.program or "").strip().lower()
        current = best_scope_by_program.get(program_key)
        if current is None or SCOPE_STRENGTH[r.scope] > SCOPE_STRENGTH[current]:
            best_scope_by_program[program_key] = r.scope

    scope_counts: dict[str, int] = defaultdict(int)
    for scope in best_scope_by_program.values():
        scope_counts[scope] += 1

    total = 0.0
    # Apply diminishing returns per scope: sku first, then product_line, then
    # low-credit label_asserted_product when present in audit fixtures.
    for scope in ("sku", "product_line", "label_asserted_product"):
        if scope_counts[scope] == 0:
            continue
        rung_points = SCOPE_POINTS[scope]
        for i in range(min(scope_counts[scope], len(rung_points))):
            total += rung_points[i]

    return min(total, B4A_HARD_CAP)


def fetch_audit_rows(top_n: int, canary_dsld_ids: set[str]) -> list[dict]:
    """Pull canary products + top-N by (claimed-cert count, score) from the DB."""
    con = sqlite3.connect(CORE_DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = []

    # 1. Canary products (explicit DSLD IDs)
    if canary_dsld_ids:
        placeholders = ",".join("?" for _ in canary_dsld_ids)
        cur.execute(
            f"""
            SELECT dsld_id, brand_name, product_name, score_100_equivalent,
                   cert_programs, primary_category, supplement_type
            FROM products_core
            WHERE dsld_id IN ({placeholders})
            """,
            tuple(canary_dsld_ids),
        )
        for r in cur.fetchall():
            d = dict(r)
            d["_audit_bucket"] = "canary"
            rows.append(d)

    # 2. Top-N by claimed cert count (LENGTH of cert_programs JSON as proxy) and score
    #    cert_programs is a JSON array like ["NSF Sport","NSF Certified","USP Verified"].
    cur.execute(
        """
        SELECT dsld_id, brand_name, product_name, score_100_equivalent,
               cert_programs, primary_category, supplement_type
        FROM products_core
        WHERE cert_programs IS NOT NULL
          AND cert_programs != '[]'
          AND product_status = 'active'
        ORDER BY (LENGTH(cert_programs) - LENGTH(REPLACE(cert_programs, '"', '')))/2 DESC,
                 score_100_equivalent DESC
        LIMIT ?
        """,
        (top_n,),
    )
    existing_ids = {r["dsld_id"] for r in rows}
    for r in cur.fetchall():
        d = dict(r)
        if d["dsld_id"] in existing_ids:
            continue
        d["_audit_bucket"] = "top_claimed"
        rows.append(d)

    con.close()
    return rows


def audit_row(row: dict, registry: CertRegistry) -> dict:
    """Run the resolver against one product. Returns the full audit record."""
    brand = row["brand_name"] or ""
    product = row["product_name"] or ""
    cert_programs_raw = row.get("cert_programs") or "[]"
    try:
        claimed = json.loads(cert_programs_raw) if isinstance(cert_programs_raw, str) else cert_programs_raw
    except json.JSONDecodeError:
        claimed = []

    resolutions = resolve(brand, product, claimed, registry)
    current_b4a = _current_b4a(row)
    proposed_b4a = _propose_b4a(resolutions)

    scope_counts = Counter(r.scope for r in resolutions)
    recency_counts = Counter(r.recency_status or "unknown" for r in resolutions)

    has_scoring_blocked = any(r.scoring_blocked_reason for r in resolutions)
    has_needs_review = any(r.scope == "needs_review" for r in resolutions)
    has_brand_only = any(r.scope == "brand_only" for r in resolutions)

    return {
        "dsld_id": row["dsld_id"],
        "brand": brand,
        "product": product,
        "audit_bucket": row.get("_audit_bucket"),
        "primary_category": row.get("primary_category"),
        "supplement_type": row.get("supplement_type"),
        "current_score_100": row.get("score_100_equivalent"),
        "claimed_programs": claimed,
        "claimed_count": len(claimed),
        "resolutions": [r.to_dict() for r in resolutions],
        "scope_counts": dict(scope_counts),
        "recency_counts": dict(recency_counts),
        "current_b4a_v3": current_b4a,
        "proposed_b4a_v4": proposed_b4a,
        "delta_b4a": round(proposed_b4a - current_b4a, 2),
        "has_needs_review": has_needs_review,
        "has_brand_only_demotion": has_brand_only,
        "has_scoring_blocked": has_scoring_blocked,
    }


def _build_needs_review_queue(audit_records: list[dict]) -> list[dict]:
    """Flatten the per-product `needs_review` resolutions into a top-level
    queue. Reviewers triage this directly without scanning all 200+ records."""
    queue: list[dict] = []
    for rec in audit_records:
        for res in rec["resolutions"]:
            if res.get("scope") != "needs_review":
                continue
            queue.append(
                {
                    "dsld_id": rec["dsld_id"],
                    "brand": rec["brand"],
                    "product": rec["product"],
                    "program": res.get("program"),
                    "match_confidence": res.get("match_confidence"),
                    "matched_brand_in_registry": res.get("matched_brand"),
                    "matched_product_in_registry": res.get("matched_product"),
                    "record_id": res.get("record_id"),
                    "snapshot_date": res.get("snapshot_date"),
                    "recency_status": res.get("recency_status"),
                    "review_action_required": (
                        "Confirm SKU match, downgrade to claimed_only (rejected), or escalate."
                    ),
                    "override_template": {
                        "brand": rec["brand"],
                        "product": rec["product"],
                        "program": res.get("program"),
                        "status": "verified | rejected | pending_review",
                        "scope": "sku | product_line",
                        "record_id": res.get("record_id"),
                        "verified_at": "YYYY-MM-DD",
                        "source_url": "https://...",
                        "reason": "reviewer notes",
                    },
                }
            )
    return queue


def _build_scoring_blocked_queue(audit_records: list[dict]) -> list[dict]:
    """Top-level list of resolutions that matched but cannot score due to
    recency. Engineering sees this and prioritizes a registry refresh."""
    blocked: list[dict] = []
    for rec in audit_records:
        for res in rec["resolutions"]:
            if not res.get("scoring_blocked_reason"):
                continue
            blocked.append(
                {
                    "dsld_id": rec["dsld_id"],
                    "brand": rec["brand"],
                    "product": rec["product"],
                    "program": res.get("program"),
                    "scope": res.get("scope"),
                    "snapshot_date": res.get("snapshot_date"),
                    "snapshot_age_days": res.get("snapshot_age_days"),
                    "recency_status": res.get("recency_status"),
                    "scoring_blocked_reason": res.get("scoring_blocked_reason"),
                }
            )
    return blocked


def write_outputs(audit_records: list[dict], out_dir: Path, timestamp: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"cert_audit_v4_p01a_{timestamp}"

    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"
    md_path = out_dir / f"{stem}_summary.md"

    # JSON
    summary = _summarize(audit_records)
    needs_review_queue = _build_needs_review_queue(audit_records)
    scoring_blocked_queue = _build_scoring_blocked_queue(audit_records)
    payload = {
        "_metadata": {
            "schema_version": "1.1.0",
            "generated_at": timestamp,
            "audit_kind": "v4_cert_p01a",
            "products_audited": len(audit_records),
            "registry_sources": _registry_sources(),
            "needs_review_count": len(needs_review_queue),
            "scoring_blocked_count": len(scoring_blocked_queue),
        },
        "summary": summary,
        # Top-level review queues — workflow-ready. Reviewers pull from here;
        # they don't have to scan 200+ records.
        "needs_review_queue": needs_review_queue,
        "scoring_blocked_queue": scoring_blocked_queue,
        "records": audit_records,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # CSV
    csv_cols = [
        "dsld_id",
        "audit_bucket",
        "brand",
        "product",
        "primary_category",
        "supplement_type",
        "current_score_100",
        "claimed_count",
        "claimed_programs",
        "scope_counts",
        "current_b4a_v3",
        "proposed_b4a_v4",
        "delta_b4a",
        "has_needs_review",
        "has_brand_only_demotion",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_cols)
        for r in audit_records:
            writer.writerow(
                [
                    r["dsld_id"],
                    r["audit_bucket"],
                    r["brand"],
                    r["product"],
                    r.get("primary_category"),
                    r.get("supplement_type"),
                    r.get("current_score_100"),
                    r["claimed_count"],
                    "|".join(r["claimed_programs"]),
                    json.dumps(r["scope_counts"], separators=(",", ":")),
                    r["current_b4a_v3"],
                    r["proposed_b4a_v4"],
                    r["delta_b4a"],
                    r["has_needs_review"],
                    r["has_brand_only_demotion"],
                ]
            )

    # Markdown summary
    md_path.write_text(_render_summary_md(summary, audit_records, timestamp), encoding="utf-8")

    return {"json": json_path, "csv": csv_path, "md": md_path}


def _registry_sources() -> list[dict]:
    reg_path = SCRIPTS_ROOT / "data" / "cert_registry.json"
    if not reg_path.exists():
        return []
    with open(reg_path) as f:
        return json.load(f).get("_metadata", {}).get("registry_sources", [])


def _summarize(records: list[dict]) -> dict:
    total = len(records)
    if total == 0:
        return {"total_audited": 0}

    scope_totals: Counter = Counter()
    delta_totals = []
    bucket_counts: Counter = Counter()
    fp_candidates = 0  # products where claimed had a cert but resolver dropped to brand_only / claimed_only
    fn_candidates = 0  # products with no claimed certs but registry has a match (rare)
    needs_review = 0
    sku_verified = 0
    products_with_demotion = 0  # claimed but routed below sku/product_line

    for r in records:
        bucket_counts[r["audit_bucket"]] += 1
        delta_totals.append(r["delta_b4a"])
        for scope, c in r["scope_counts"].items():
            scope_totals[scope] += c
        if r["has_needs_review"]:
            needs_review += 1
        if r["claimed_count"] > 0 and r["scope_counts"].get("sku", 0) > 0:
            sku_verified += 1
        if r["claimed_count"] > 0 and not r["scope_counts"].get("sku") and not r["scope_counts"].get("product_line"):
            products_with_demotion += 1
        # FP heuristic: claimed cert exists but no sku/product_line match
        if r["claimed_count"] > 0 and (r["scope_counts"].get("brand_only", 0) + r["scope_counts"].get("claimed_only", 0)) == r["claimed_count"]:
            fp_candidates += 1

    delta_totals.sort()
    n = len(delta_totals)
    def pct(arr: list[float], p: float) -> float:
        if not arr:
            return 0.0
        i = max(0, min(n - 1, int(round((n - 1) * p))))
        return arr[i]

    return {
        "total_audited": total,
        "by_bucket": dict(bucket_counts),
        "scope_distribution": dict(scope_totals),
        "products_with_sku_verified": sku_verified,
        "products_with_demotion_only": products_with_demotion,
        "products_needing_review": needs_review,
        "products_fp_candidates": fp_candidates,
        "delta_b4a": {
            "min": delta_totals[0] if delta_totals else 0,
            "p25": pct(delta_totals, 0.25),
            "median": pct(delta_totals, 0.5),
            "p75": pct(delta_totals, 0.75),
            "max": delta_totals[-1] if delta_totals else 0,
            "mean": round(sum(delta_totals) / n, 2) if n else 0,
        },
    }


def _render_summary_md(summary: dict, records: list[dict], timestamp: str) -> str:
    lines: list[str] = []
    lines.append(f"# Cert audit v4 P0.1a — {timestamp}")
    lines.append("")
    lines.append("**No scoring changes applied.** This report compares v3's current "
                 "B4a treatment against the v4 proposed scope-aware B4a logic.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total products audited: **{summary['total_audited']}**")
    lines.append(f"- By bucket: `{json.dumps(summary.get('by_bucket', {}))}`")
    lines.append(f"- Products with at least one SKU-verified cert: **{summary['products_with_sku_verified']}**")
    lines.append(f"- Products where all claimed certs resolve below sku/product_line "
                 f"(demotion candidates — v3 overcredits these): **{summary['products_with_demotion_only']}**")
    lines.append(f"- Products with at least one needs_review entry: **{summary['products_needing_review']}**")
    lines.append("")
    lines.append("### Scope distribution (across all resolutions)")
    for scope, c in sorted(summary["scope_distribution"].items()):
        lines.append(f"- `{scope}`: {c}")
    lines.append("")
    lines.append("### Delta B4a (proposed v4 − current v3)")
    d = summary["delta_b4a"]
    lines.append(f"- min: {d['min']:.2f}, p25: {d['p25']:.2f}, median: {d['median']:.2f}, "
                 f"p75: {d['p75']:.2f}, max: {d['max']:.2f}, mean: {d['mean']:.2f}")
    lines.append("")
    lines.append("## Top 10 negative movers (products that LOSE B4a points under v4)")
    sorted_neg = sorted(records, key=lambda r: r["delta_b4a"])[:10]
    for r in sorted_neg:
        lines.append(
            f"- `{r['dsld_id']}` **{r['brand']}** — {r['product']}: "
            f"v3 B4a {r['current_b4a_v3']} → v4 {r['proposed_b4a_v4']} "
            f"(Δ {r['delta_b4a']:+.1f}) "
            f"claimed={r['claimed_count']} scopes={json.dumps(r['scope_counts'])}"
        )
    lines.append("")
    lines.append("## Top 10 positive movers (products that GAIN B4a points under v4)")
    sorted_pos = sorted(records, key=lambda r: -r["delta_b4a"])[:10]
    for r in sorted_pos:
        lines.append(
            f"- `{r['dsld_id']}` **{r['brand']}** — {r['product']}: "
            f"v3 B4a {r['current_b4a_v3']} → v4 {r['proposed_b4a_v4']} "
            f"(Δ {r['delta_b4a']:+.1f}) "
            f"claimed={r['claimed_count']} scopes={json.dumps(r['scope_counts'])}"
        )
    lines.append("")
    lines.append("## Canary detail")
    canaries = [r for r in records if r["audit_bucket"] == "canary"]
    for r in canaries:
        lines.append("")
        lines.append(f"### {r['brand']} — {r['product']} (DSLD `{r['dsld_id']}`)")
        lines.append(f"- Current score: {r['current_score_100']}")
        lines.append(f"- Claimed: {r['claimed_programs']}")
        lines.append(f"- Resolutions:")
        for res in r["resolutions"]:
            lines.append(
                f"  - `{res.get('program')}` → **{res.get('scope')}** "
                f"(confidence={res.get('match_confidence')}, "
                f"matched=`{res.get('matched_product') or '-'}`)"
            )
        lines.append(f"- v3 B4a: {r['current_b4a_v3']}, v4 proposed: {r['proposed_b4a_v4']}, Δ {r['delta_b4a']:+.1f}")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="P0.1a cert audit report")
    parser.add_argument("--top", type=int, default=200, help="Top N products with claimed certs to audit (default 200)")
    parser.add_argument("--out-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args()

    canary_dsld_ids = {c["dsld_id"] for c in CANARY if "dsld_id" in c}
    print(f"Canary DSLD IDs: {sorted(canary_dsld_ids)}", file=sys.stderr)

    rows = fetch_audit_rows(args.top, canary_dsld_ids)
    print(f"Fetched {len(rows)} products from DB", file=sys.stderr)

    registry = CertRegistry.load()
    print(f"Registry: {sum(len(v) for v in registry.records_by_program.values())} verified records across "
          f"{len(registry.records_by_program)} programs", file=sys.stderr)

    audit_records = [audit_row(r, registry) for r in rows]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    paths = write_outputs(audit_records, args.out_dir, timestamp)
    print(f"Wrote:", file=sys.stderr)
    for kind, p in paths.items():
        print(f"  {kind}: {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
