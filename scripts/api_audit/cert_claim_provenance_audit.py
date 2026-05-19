#!/usr/bin/env python3
"""P0.1c — cert claim provenance audit (AUDIT-ONLY, no scoring change).

Goal: for every cert program the catalog has labeled, separate the
evidence by provenance:

  - `label_certifications`     — regex/rules-db hits in product-level text
                                  (statements, qualityFeatures, labelText)
  - `manufacturer_evidence`    — brand/manufacturer-level injection from
                                  `top_manufacturers_data.json`
  - `verified_cert_programs`   — current resolver output (sku / product_line /
                                  brand_only / needs_review / claimed_only)

Why: P0.1b made unsupported programs (USP/IFOS/Informed/Non-GMO/etc.)
resolve to `claimed_only=0` because no registry is loaded. That avoids
overcredit but may undercredit legitimate product-level label claims.
This audit quantifies the gap so we can decide whether a provisional
`label_asserted_product` tier (proposed 2/1/0, cap 3) is warranted —
**without changing scoring yet**.

Output: a JSON + Markdown report per program, with raw counts and
representative samples.

Usage:
  python scripts/api_audit/cert_claim_provenance_audit.py [--out-dir reports/]
  python scripts/api_audit/cert_claim_provenance_audit.py --sample 10

NO SCORING CHANGES. NO BLOB MUTATIONS. Audit-only.
"""

from __future__ import annotations

import argparse
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

CORE_DB = SCRIPTS_ROOT / "final_db_output" / "pharmaguide_core.db"
BLOBS_DIR = SCRIPTS_ROOT / "final_db_output" / "detail_blobs"
REPORT_DIR = SCRIPTS_ROOT / "api_audit" / "reports"


# Programs we expect to see + Codex's interim handling guidance.
# This is the routing decision matrix the audit informs.
INTERIM_PROGRAM_ROUTING = {
    "USP Verified": {
        "handling": "provisional_b4a_if_product_label_evidence",
        "scraper_priority": 1,
        "category": "testing_purity",
    },
    "Informed Sport": {
        "handling": "provisional_b4a_if_product_label_evidence",
        "scraper_priority": 2,
        "category": "testing_purity_sport",
    },
    "Informed Choice": {
        "handling": "provisional_b4a_if_product_label_evidence",
        "scraper_priority": 2,
        "category": "testing_purity_sport",
    },
    "BSCG": {
        "handling": "provisional_b4a_if_product_label_evidence",
        "scraper_priority": 4,
        "category": "testing_purity_sport",
    },
    "IFOS": {
        "handling": "provisional_omega_only",
        "scraper_priority": 3,
        "category": "omega_purity",
    },
    "Friend of the Sea": {
        "handling": "omega_marine_source_quality_only",
        "scraper_priority": 5,
        "category": "marine_sustainability",
    },
    "MSC Certified": {
        "handling": "omega_marine_source_quality_only",
        "scraper_priority": 5,
        "category": "marine_sustainability",
    },
    "MSC": {
        "handling": "omega_marine_source_quality_only",
        "scraper_priority": 5,
        "category": "marine_sustainability",
    },
    "GOED": {
        "handling": "omega_source_quality_only",
        "scraper_priority": 5,
        "category": "omega_source",
    },
    "GOED Certified": {
        "handling": "omega_source_quality_only",
        "scraper_priority": 5,
        "category": "omega_source",
    },
    "Non-GMO Project": {
        "handling": "formulation_a5_not_b4a_purity",
        "scraper_priority": 4,
        "category": "formulation_claim",
    },
    "USDA Organic": {
        "handling": "formulation_a5_not_b4a_purity",
        "scraper_priority": None,
        "category": "formulation_claim",
    },
    "GFCO": {
        "handling": "b3_claim_compliance_not_b4a",
        "scraper_priority": None,
        "category": "b3_claim",
    },
    "ConsumerLab": {
        "handling": "manual_review_only_paid_license",
        "scraper_priority": None,
        "category": "paid_subscription",
    },
    "Labdoor Tested": {
        "handling": "manual_review_only",
        "scraper_priority": None,
        "category": "third_party_review",
    },
    "Health Canada NPN": {
        "handling": "regulatory_filing_not_purity",
        "scraper_priority": None,
        "category": "regulatory",
    },
}


# Bucket programs we already cover via live registry (post-P0.1a)
COVERED_BY_LIVE_REGISTRY = {"NSF Sport", "NSF Certified"}


def load_audit_rows() -> list[dict]:
    """Pull all live-catalog products with their cert_programs (claimed)
    + we'll join blob detail in a second pass for provenance."""
    if not CORE_DB.exists():
        raise SystemExit(f"core DB missing at {CORE_DB}")
    con = sqlite3.connect(CORE_DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT dsld_id, brand_name, product_name, score_100_equivalent,
               cert_programs, primary_category, supplement_type, product_status
        FROM products_core
        """
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def load_blob(dsld_id: str) -> dict | None:
    """Load the detail blob for a product. Returns None if missing."""
    path = BLOBS_DIR / f"{dsld_id}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def extract_provenance(blob: dict) -> dict[str, list[str]]:
    """From a v3-shipped blob, separate program names by provenance.

    Returns a dict with three keys:
      - label_certifications: list of programs detected from product label text
      - manufacturer_evidence: list of programs injected from manufacturer data
      - either_or_unknown: programs whose provenance can't be determined
        from the blob (e.g., older blob shape).
    """
    cert = blob.get("certification_data") or blob.get("certification_detail") or {}
    tp = cert.get("third_party_programs") or {}
    programs = tp.get("programs") or []

    label_progs: list[str] = []
    mfg_progs: list[str] = []
    unknown_progs: list[str] = []

    for p in programs:
        if not isinstance(p, dict):
            unknown_progs.append(str(p))
            continue
        name = p.get("name") or ""
        if not name:
            continue
        source = (p.get("source") or "").lower()
        if source == "manufacturer_evidence":
            mfg_progs.append(name)
        elif source in ("rules_db", "label", "label_text", ""):
            # Empty / rules_db / label-style = product-level label evidence
            label_progs.append(name)
        else:
            unknown_progs.append(name)

    return {
        "label_certifications": label_progs,
        "manufacturer_evidence": mfg_progs,
        "either_or_unknown": unknown_progs,
    }


def summarize(audit_records: list[dict], sample_size: int = 5) -> dict:
    """Aggregate per-program provenance counts + capture samples."""
    by_program: dict[str, dict] = defaultdict(
        lambda: {
            "label_count": 0,
            "manufacturer_count": 0,
            "unknown_count": 0,
            "total_products": 0,
            "sample_products_label": [],
            "sample_products_manufacturer": [],
        }
    )

    products_with_any_unsupported_program = 0
    total_products_with_cert_provenance = 0

    for rec in audit_records:
        if not rec.get("provenance"):
            continue
        total_products_with_cert_provenance += 1
        prov = rec["provenance"]
        all_programs_for_product = (
            set(prov["label_certifications"])
            | set(prov["manufacturer_evidence"])
            | set(prov["either_or_unknown"])
        )

        product_has_unsupported = False
        for prog in all_programs_for_product:
            slot = by_program[prog]
            slot["total_products"] += 1

            if prog in prov["label_certifications"]:
                slot["label_count"] += 1
                if len(slot["sample_products_label"]) < sample_size:
                    slot["sample_products_label"].append(
                        {
                            "dsld_id": rec["dsld_id"],
                            "brand": rec["brand_name"],
                            "product": rec["product_name"],
                        }
                    )

            if prog in prov["manufacturer_evidence"]:
                slot["manufacturer_count"] += 1
                if len(slot["sample_products_manufacturer"]) < sample_size:
                    slot["sample_products_manufacturer"].append(
                        {
                            "dsld_id": rec["dsld_id"],
                            "brand": rec["brand_name"],
                            "product": rec["product_name"],
                        }
                    )

            if prog in prov["either_or_unknown"]:
                slot["unknown_count"] += 1

            if prog not in COVERED_BY_LIVE_REGISTRY:
                product_has_unsupported = True

        if product_has_unsupported:
            products_with_any_unsupported_program += 1

    # Sort by total_products descending
    summary = sorted(
        [
            {
                "program": prog,
                "covered_by_live_registry": prog in COVERED_BY_LIVE_REGISTRY,
                "interim_routing": INTERIM_PROGRAM_ROUTING.get(prog, {}).get("handling", "not_classified"),
                "scraper_priority": INTERIM_PROGRAM_ROUTING.get(prog, {}).get("scraper_priority"),
                **vals,
            }
            for prog, vals in by_program.items()
        ],
        key=lambda x: -x["total_products"],
    )

    return {
        "total_products_with_cert_provenance": total_products_with_cert_provenance,
        "products_with_any_unsupported_program": products_with_any_unsupported_program,
        "by_program": summary,
    }


def render_markdown(summary: dict, timestamp: str) -> str:
    out: list[str] = []
    out.append(f"# Cert claim provenance audit (P0.1c) — {timestamp}")
    out.append("")
    out.append("**AUDIT-ONLY. No scoring change.** Scans the full live catalog and,")
    out.append("for products that carry any cert provenance, separates label-text")
    out.append("evidence from manufacturer-injected evidence.")
    out.append("")
    out.append("## Summary")
    out.append(
        f"- Catalog products scanned: **{summary.get('total_catalog_products_scanned', '?')}** "
        f"(only those with cert provenance are aggregated below)"
    )
    out.append(
        f"- Products with at least one cert claim (label OR manufacturer): "
        f"**{summary['total_products_with_cert_provenance']}**"
    )
    out.append(
        f"- Of those, products with at least one program OUTSIDE our live registry: "
        f"**{summary['products_with_any_unsupported_program']}**"
    )
    out.append("")
    out.append("## Per-program counts (sorted by total products claiming this program)")
    out.append("")
    out.append("| Program | Covered? | Label hits | Mfg hits | Unknown | Total | Interim handling | Scraper priority |")
    out.append("|---|---|---:|---:|---:|---:|---|---:|")
    for row in summary["by_program"]:
        cov = "✓" if row["covered_by_live_registry"] else "—"
        pri = row["scraper_priority"]
        pri_str = str(pri) if pri is not None else "—"
        out.append(
            f"| `{row['program']}` | {cov} | "
            f"{row['label_count']} | {row['manufacturer_count']} | "
            f"{row['unknown_count']} | {row['total_products']} | "
            f"`{row['interim_routing']}` | {pri_str} |"
        )
    out.append("")
    out.append("## Reading the table")
    out.append("- **Label hits**: product's own label text (or rules-db detection) names this program.")
    out.append("  These are the strongest candidates for a provisional `label_asserted_product` tier")
    out.append("  (proposed 2/1/0 capped at 3 in v4 §10 follow-on).")
    out.append("- **Mfg hits**: brand-level injection from `top_manufacturers_data.json`. These should")
    out.append("  remain display-only / manufacturer trust signals — they do NOT prove SKU-level cert.")
    out.append("- **Unknown**: provenance unclear from the v3 blob (legacy shape). Ignore for now.")
    out.append("- **Covered**: program is loaded into `cert_registry.json` and a resolver can")
    out.append("  verify it at SKU level. Currently only NSF Sport + NSF/ANSI 173.")
    out.append("")
    out.append("## Samples (first 3 of each provenance per program)")
    for row in summary["by_program"][:30]:  # top 30 programs only
        if row["total_products"] == 0:
            continue
        out.append("")
        out.append(f"### {row['program']}")
        if row["sample_products_label"]:
            out.append(f"**Label hits** (n={row['label_count']}):")
            for s in row["sample_products_label"][:3]:
                out.append(f"- `{s['dsld_id']}` — {s['brand']} — {s['product']}")
        if row["sample_products_manufacturer"]:
            out.append(f"**Manufacturer-injected** (n={row['manufacturer_count']}):")
            for s in row["sample_products_manufacturer"][:3]:
                out.append(f"- `{s['dsld_id']}` — {s['brand']} — {s['product']}")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="P0.1c cert claim provenance audit")
    parser.add_argument("--out-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--sample", type=int, default=5, help="Per-program sample size (default 5)")
    parser.add_argument("--limit", type=int, default=0, help="Limit products audited (0 = all)")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading catalog rows...", file=sys.stderr)
    rows = load_audit_rows()
    print(f"  {len(rows)} products in products_core", file=sys.stderr)

    if args.limit:
        rows = rows[: args.limit]

    print("Walking detail blobs for provenance...", file=sys.stderr)
    audit_records: list[dict] = []
    missing = 0
    for i, r in enumerate(rows, 1):
        if i % 1000 == 0:
            print(f"  [{i}/{len(rows)}]", file=sys.stderr)
        blob = load_blob(r["dsld_id"])
        if not blob:
            missing += 1
            continue
        prov = extract_provenance(blob)
        if not (prov["label_certifications"] or prov["manufacturer_evidence"] or prov["either_or_unknown"]):
            continue
        audit_records.append({**r, "provenance": prov})

    print(f"  audited {len(audit_records)} products; {missing} missing blobs", file=sys.stderr)

    summary = summarize(audit_records, sample_size=args.sample)
    # Wire catalog-scan counts into summary so the report can distinguish
    # "scanned" from "had cert provenance" — Codex feedback on report wording.
    summary["total_catalog_products_scanned"] = len(rows)
    summary["catalog_products_missing_blob"] = missing

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"cert_claim_provenance_audit_{ts}"
    json_path = args.out_dir / f"{stem}.json"
    md_path = args.out_dir / f"{stem}.md"

    payload = {
        "_metadata": {
            "schema_version": "1.1.0",
            "generated_at": ts,
            "audit_kind": "p0_1c_cert_claim_provenance",
            "covered_by_live_registry": sorted(COVERED_BY_LIVE_REGISTRY),
            "total_catalog_products_scanned": summary["total_catalog_products_scanned"],
            "total_products_with_cert_provenance": summary["total_products_with_cert_provenance"],
        },
        "summary": summary,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(summary, ts), encoding="utf-8")

    print(f"Wrote:\n  {json_path}\n  {md_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
