#!/usr/bin/env python3
"""Cert claim-vs-registry audit.

For every product in the shipped catalog that has a recorded cert claim in
the current blob, run the resolver against cert_registry.json and report
what the production rerun will award.  Tells us — before kicking off a
2-3 hour pipeline run — how many products will:

  * `sku` / `product_line` → real verification, B4a credit awarded
  * `brand_only`           → brand is in registry but THIS product isn't
                              (B4a 0; routes to manufacturer trust later)
  * `claimed_only`         → no registry hit at all; often a
                              claim-text false positive (USP-grade
                              ingredient claim, NSF GMP facility wording,
                              Informed-tested-facility marketing, etc.)
  * `needs_review`         → borderline match, reviewer decides

This is the diagnostic that surfaces patterns like Doctor's Best CoQ10
(USP text can refer to USP-grade ingredient, not Verified Mark Program —
resolver correctly returns claimed_only). Run this BEFORE the
non-production rerun so the score-delta report has expected ranges.

Usage:
  python3 scripts/api_audit/cert_label_registry_audit.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cert_resolver import CertRegistry, normalize_program, resolve  # noqa: E402

CORE_DB = SCRIPTS_ROOT / "final_db_output" / "pharmaguide_core.db"
BLOBS_DIR = SCRIPTS_ROOT / "final_db_output" / "detail_blobs"
REPORT_DIR = SCRIPTS_ROOT / "api_audit" / "reports"

def _walk_label_programs(blob: dict) -> list[str]:
    """Return the list of cert program names the SHIPPED blob recorded.

    Shipped blobs predate P0.1b's three-tier split, so third_party_programs
    contains BOTH label-detected and manufacturer-injected entries. The
    registry audit treats both as "claimed" — what matters for the rerun
    is whether the resolver finds the SKU, not which path put the claim
    in the blob.

    Falls back to top-level `named_cert_programs` if third_party is missing.
    """
    # Shipped blob schema uses `certification_detail`; intermediate / canary
    # outputs use `certification_data`. Accept either.
    cert_data = (
        blob.get("certification_detail")
        or blob.get("certification_data")
        or {}
    )
    tp = (cert_data.get("third_party_programs") or {}).get("programs") or []
    names: list[str] = []
    for entry in tp:
        if isinstance(entry, dict):
            n = entry.get("name") or entry.get("program")
        else:
            n = entry
        if isinstance(n, str) and n:
            names.append(n)
    if not names:
        for n in blob.get("named_cert_programs") or []:
            if isinstance(n, str) and n:
                names.append(n)
    # Dedupe preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def load_catalog() -> list[dict]:
    if not CORE_DB.exists():
        raise SystemExit(f"core DB missing at {CORE_DB}")
    con = sqlite3.connect(CORE_DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT dsld_id, brand_name, product_name, primary_category, "
        "supplement_type, verdict, score_100_equivalent FROM products_core"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def load_blob(dsld_id: str) -> Optional[dict]:
    p = BLOBS_DIR / f"{dsld_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _registry_covered_programs(registry: CertRegistry) -> set[str]:
    """Return normalized programs backed by the loaded registry snapshot."""
    from_sources = {
        normalize_program(src.get("program", ""))
        for src in (registry.metadata.get("registry_sources") or [])
        if src.get("program")
    }
    from_records = {p for p in registry.records_by_program.keys() if p}
    return {p for p in (from_sources | from_records) if p}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cert claim-vs-registry audit")
    parser.add_argument(
        "--out-dir", type=Path, default=REPORT_DIR,
        help="Where to write JSON + Markdown reports."
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Cap catalog walk for debugging (0 = all).",
    )
    parser.add_argument(
        "--samples", type=int, default=5,
        help="Per-scope sample count in the Markdown report (default 5).",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading registry...", file=sys.stderr)
    registry = CertRegistry.load()
    covered_programs = _registry_covered_programs(registry)
    print(f"  registry loaded: {sum(len(v) for v in registry.records_by_program.values())} records across {len(covered_programs)} programs", file=sys.stderr)

    print("Loading catalog...", file=sys.stderr)
    rows = load_catalog()
    if args.limit:
        rows = rows[: args.limit]
    print(f"  {len(rows)} products in products_core", file=sys.stderr)

    # Per-program: count of each scope.
    by_program: dict[str, Counter] = defaultdict(Counter)
    # Per-program-and-scope sample records (dsld_id, brand, product).
    samples: dict[tuple[str, str], list[dict]] = defaultdict(list)
    total_with_any_claim = 0
    total_covered_claims = 0
    missing_blobs = 0

    for i, r in enumerate(rows, 1):
        if i % 1000 == 0:
            print(f"  [{i}/{len(rows)}]", file=sys.stderr)
        blob = load_blob(r["dsld_id"])
        if blob is None:
            missing_blobs += 1
            continue
        label_programs = _walk_label_programs(blob)
        if not label_programs:
            continue
        total_with_any_claim += 1

        # Only audit programs we have live registries for. Other programs
        # are out of scope for this audit (handled by P0.1c routing).
        covered_claims = [
            p for p in label_programs
            if normalize_program(p) in covered_programs
        ]
        if not covered_claims:
            continue
        total_covered_claims += 1

        resolutions = resolve(
            brand=r["brand_name"] or "",
            product=r["product_name"] or "",
            claimed_programs=covered_claims,
            registry=registry,
            dsld_id=r["dsld_id"],
        )
        for res in resolutions:
            d = res.to_dict()
            prog = normalize_program(d.get("program") or "")
            if not prog:
                continue
            scope = d.get("scope") or "claimed_only"
            # When the resolver writes scoring_blocked_reason, treat it as
            # a separate bucket for visibility (this should be empty given
            # fresh snapshots).
            if d.get("scoring_blocked_reason"):
                scope = "scoring_blocked"
            by_program[prog][scope] += 1
            if len(samples[(prog, scope)]) < args.samples:
                samples[(prog, scope)].append(
                    {
                        "dsld_id": r["dsld_id"],
                        "brand": r["brand_name"],
                        "product": r["product_name"],
                        "match_confidence": d.get("match_confidence"),
                        "matched_record_brand": d.get("matched_brand"),
                        "matched_record_product": d.get("matched_product"),
                    }
                )

    # Build summary
    program_summary: list[dict] = []
    for prog in sorted(by_program.keys()):
        counts = by_program[prog]
        total = sum(counts.values())
        sku = counts.get("sku", 0) + counts.get("product_line", 0)
        zero = counts.get("brand_only", 0) + counts.get("claimed_only", 0)
        program_summary.append(
            {
                "program": prog,
                "total_claims_in_catalog": total,
                "scope_counts": dict(counts),
                "sku_or_product_line_pct": round(100.0 * sku / total, 1) if total else 0.0,
                "non_scoring_pct": round(100.0 * zero / total, 1) if total else 0.0,
                # Backward-compatible key for older report consumers. The
                # markdown now uses "non-scoring" because brand_only is not
                # necessarily a false positive; it is often a real brand cert
                # that does not prove this SKU.
                "false_positive_pct": round(100.0 * zero / total, 1) if total else 0.0,
                "samples": {
                    scope: samples.get((prog, scope), [])[: args.samples]
                    for scope in counts.keys()
                },
            }
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"cert_label_registry_audit_{ts}"
    payload = {
        "_metadata": {
            "schema_version": "1.0.0",
            "generated_at": ts,
            "audit_kind": "p01_cert_claim_vs_registry",
            "covered_programs": sorted(covered_programs),
            "total_catalog_products_scanned": len(rows),
            "total_products_with_any_cert_claim": total_with_any_claim,
            "total_products_with_covered_program_claim": total_covered_claims,
            "missing_blobs": missing_blobs,
            "registry_record_count": sum(len(v) for v in registry.records_by_program.values()),
        },
        "summary": {"by_program": program_summary},
    }

    json_path = args.out_dir / f"{stem}.json"
    md_path = args.out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Markdown
    out: list[str] = []
    out.append(f"# Cert claim-vs-registry audit — {ts}")
    out.append("")
    out.append("**Purpose:** for every shipped product with a recorded cert claim in its current blob,")
    out.append("predict what the cert resolver will award when the next pipeline rerun runs.")
    out.append("Surfaces claim-text false positives (USP-grade ingredient ≠ USP Verified Mark, etc.)")
    out.append("before the rerun, so the score-delta report has expected counts.")
    out.append("")
    out.append("## Summary")
    out.append(f"- Catalog products scanned: **{len(rows)}**")
    out.append(f"- With at least one cert claim in the current blob: **{total_with_any_claim}**")
    out.append(f"- With at least one claim for a live-registry-covered program: **{total_covered_claims}**")
    out.append(f"- Programs covered by live registry: {', '.join(sorted(covered_programs))}")
    out.append("")
    out.append("## Per-program breakdown")
    out.append("")
    out.append("| Program | Total claims | sku | product_line | needs_review | brand_only | claimed_only | scoring_blocked | % real verify | % non-scoring |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in program_summary:
        c = row["scope_counts"]
        out.append(
            f"| `{row['program']}` | {row['total_claims_in_catalog']} | "
            f"{c.get('sku',0)} | {c.get('product_line',0)} | {c.get('needs_review',0)} | "
            f"{c.get('brand_only',0)} | {c.get('claimed_only',0)} | {c.get('scoring_blocked',0)} | "
            f"{row['sku_or_product_line_pct']}% | {row['false_positive_pct']}% |"
        )
    out.append("")
    out.append("## Reading the table")
    out.append("- **sku / product_line**: real verification — the resolver matched the brand + product.")
    out.append("- **needs_review**: borderline confidence (0.80-0.91) OR dose/form variant conflict.")
    out.append("- **brand_only**: brand IS in the registry but THIS product isn't (e.g., Thorne brand in NSF Sport, but Thorne Basic Prenatal not on the cert list).")
    out.append("- **claimed_only**: no scoring product match. Common causes: explicit reviewer reject, USP-grade ingredient wording, NSF GMP-facility wording, old manufacturer-injected claim, or unverified marketing — NOT actual cert participation.")
    out.append("- **scoring_blocked**: resolver flagged the snapshot as too stale to score.")
    out.append("")
    out.append("## Per-program sample records")
    for row in program_summary:
        out.append("")
        out.append(f"### `{row['program']}`")
        for scope in ("sku", "product_line", "needs_review", "brand_only", "claimed_only"):
            sams = row["samples"].get(scope, [])
            if not sams:
                continue
            out.append(f"**{scope}** (n={row['scope_counts'].get(scope,0)}):")
            for s in sams:
                line = f"- `{s['dsld_id']}` — {s['brand']} — {s['product']}"
                if s.get("matched_record_product"):
                    line += f"  → matched `{s['matched_record_brand']} / {s['matched_record_product']}` (conf={s.get('match_confidence')})"
                out.append(line)
    md_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"\nWrote:\n  {json_path}\n  {md_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
