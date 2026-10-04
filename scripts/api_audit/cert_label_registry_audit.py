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
  python3 scripts/api_audit/cert_label_registry_audit.py --products-root scripts/products

The --products-root census reruns production discovery for every enriched or
clean-only label, regardless of claim or publication eligibility. Input failures
are reported and return a nonzero exit; --limit is explicitly incomplete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cert_resolver import CertRegistry, OVERRIDES_PATH, REGISTRY_PATH, discover_verified_programs, _reviewed_override_identity_conflict, _sku_variant_conflict, _with_label_form_context, normalize_program, resolve  # noqa: E402

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


def audit_overrides(registry: CertRegistry) -> list[dict]:
    """Check reviewed references against the candidate, without awarding credit."""
    issues = []
    for key, entries in registry.overrides_by_brand_product.items():
        for entry in entries:
            if entry.get("status") != "verified":
                continue
            record = registry.record_by_id(entry.get("record_id"))
            cause = None
            if not record:
                cause = "missing_registry_record"
            elif normalize_program(record.get("program", "")) != normalize_program(entry.get("program", "")):
                cause = "program_conflict"
            elif _reviewed_override_identity_conflict(entry, record):
                cause = "reviewed_identity_conflict"
            elif record.get("current_certification") is False:
                cause = "withdrawn_registry_record"
            elif record.get("_recency_status") in {"unknown", "scoring_blocked"}:
                cause = "outdated_registry_record"
            if cause:
                issues.append({"brand": key[0], "product": key[1], "dsld_id": entry.get("dsld_id"),
                               "record_id": entry.get("record_id"), "cause": cause})
        for index, first in enumerate(entries):
            for second in entries[index + 1:]:
                if normalize_program(first.get("program", "")) != normalize_program(second.get("program", "")):
                    continue
                if first.get("dsld_id") and second.get("dsld_id") and str(first["dsld_id"]) != str(second["dsld_id"]):
                    continue
                # Disjoint strength/form reviews are legitimate. A broad name
                # can overlap a narrower review when either owner comparison allows it.
                if _sku_variant_conflict(first.get("product", ""), second.get("product", "")) and _sku_variant_conflict(second.get("product", ""), first.get("product", "")):
                    continue
                statuses = {first.get("status", "verified"), second.get("status", "verified")}
                if statuses == {"verified", "rejected"}:
                    rejected = first if first.get("status") == "rejected" else second
                    verified = second if rejected is first else first
                    # A rejected competing record and an accepted record are
                    # normal review outcomes, not contradictory decisions.
                    conflict = not rejected.get("record_id") or rejected.get("record_id") == verified.get("record_id")
                elif statuses == {"verified"} and first.get("record_id") != second.get("record_id"):
                    other_record = registry.record_by_id(second.get("record_id"))
                    conflict = bool(other_record and _reviewed_override_identity_conflict(first, other_record))
                else:
                    conflict = False
                if conflict:
                    issues.append({"brand": key[0], "product": key[1], "cause": "conflicting_reviewed_overrides",
                                   "record_ids": [first.get("record_id"), second.get("record_id")]})
    return issues


def _census_resolution(product: dict, registry: CertRegistry) -> dict:
    """Ask production discovery; diagnostic candidates never become certification."""
    brand, title = product["brandName"], product["fullName"]
    identifier = str(product.get("dsld_id") or product.get("id"))
    context = {key: product.get(key) for key in ("form_factor_canonical", "form_factor", "netContents")}
    claims = _walk_label_programs(product)
    # Resolve all registry programs for non-awarding explanations, including no-claim misses.
    programs = sorted(_registry_covered_programs(registry) | {normalize_program(p) for p in claims})
    diagnostic = resolve(brand, title, programs, registry, dsld_id=identifier, label_context=context)
    # Discovery can only emit sku/product_line resolutions. Restrict a shallow
    # view to those programs after the identical owner query, avoiding a second
    # all-program search while preserving discovery's additional identity guard.
    eligible_programs = {row.program for row in diagnostic if row.scope in {"sku", "product_line"}}
    discovery_registry = replace(registry, records_by_program={
        program: records for program, records in registry.records_by_program.items() if program in eligible_programs
    })
    discovered = discover_verified_programs(brand, title, discovery_registry, dsld_id=identifier, label_context=context)
    matched = [resolution.to_dict() for resolution in discovered]
    diagnostics = [resolution.to_dict() for resolution in diagnostic]
    if any(resolution.scores_points() for resolution in discovered):
        cause = "verified_match"
    elif any(row.get("scoring_blocked_reason") for row in matched + diagnostics):
        cause = "outdated_or_withdrawn_record"
    elif any("ambiguous registry product variants" in row.get("notes", "") for row in diagnostics):
        cause = "ambiguous_registry_variants"
    elif any(row.get("scope") == "needs_review" and row.get("matched_product") and _sku_variant_conflict(
            _with_label_form_context(title, context), row["matched_product"],
            brand_a=brand, brand_b=row.get("matched_brand", "")) for row in diagnostics):
        cause = "material_identity_conflict"
    elif any(row.get("scope") == "needs_review" for row in diagnostics):
        cause = "title_identity_review"
    elif any(row.get("scope") in {"brand_only", "sku", "product_line"} for row in diagnostics):
        cause = "product_identity_not_established"
    elif any(normalize_program(p) not in _registry_covered_programs(registry) for p in claims):
        cause = "source_not_covered"
    else:
        cause = "registry_brand_absent"
    return {"dsld_id": identifier, "brand": brand, "product": title, "has_claim": bool(claims),
            "claims": claims, "quality_score_status": product.get("quality_score_status"),
            "cause": cause, "discovered": matched, "diagnostics": diagnostics}


def census(products_root: Path, registry: CertRegistry, *, limit: int = 0) -> dict:
    """Walk enriched plus clean-only inputs, including held and unclaimed labels.

    Every malformed row/file is recorded. Clean copies of an enriched label are
    counted as stage duplicates, not scored again. No export eligibility filter.
    """
    products, errors, seen = [], [], {}
    duplicates = 0
    paths = sorted(products_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"))
    paths += sorted(products_root.glob("output_*/cleaned/cleaned_batch_*.json"))
    clean_count = 0
    file_count = 0
    input_fingerprints = {}
    for path in paths:
        file_count += 1
        try:
            raw = path.read_bytes()
            input_fingerprints[str(path)] = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw)
            del raw
            items = payload if isinstance(payload, list) else payload.get("products", payload.get("items")) if isinstance(payload, dict) else None
            if not isinstance(items, list):
                raise ValueError("product batch must contain a list")
        except (OSError, ValueError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
            continue
        for index, product in enumerate(items):
            identifier = str(product.get("dsld_id") or product.get("id") or "") if isinstance(product, dict) else ""
            if identifier and identifier in seen:
                identity = (product.get("brandName"), product.get("fullName"))
                if identity != seen[identifier]:
                    errors.append({"path": str(path), "row": index, "dsld_id": identifier,
                                   "error": "duplicate label ID has conflicting identity"})
                duplicates += 1
                continue
            if identifier:
                seen[identifier] = (product.get("brandName"), product.get("fullName"))
            if not isinstance(product, dict) or not identifier or not product.get("brandName") or not product.get("fullName"):
                error = {"path": str(path), "row": index, "dsld_id": identifier, "error": "missing product identity"}
                errors.append(error)
                products.append({**error, "cause": "input_error"})
            else:
                try:
                    row = _census_resolution(product, registry)
                except Exception as exc:
                    error = {"path": str(path), "row": index, "dsld_id": identifier, "error": str(exc)}
                    errors.append(error)
                    row = {**error, "cause": "input_error"}
                row["input_path"] = str(path)
                products.append(row)
                if path.parent.name == "cleaned":
                    clean_count += 1
            if len(products) % 1000 == 0:
                print(f"  census: {len(products)} products", file=sys.stderr)
            if limit and len(products) >= limit:
                break
        if limit and len(products) >= limit:
            break
    if not paths:
        errors.append({"path": str(products_root), "error": "no product batches found"})
    clusters = defaultdict(list)
    for product in products:
        for row in product.get("diagnostics", []):
            if row.get("scope") == "needs_review":
                clusters[(row.get("program"), row.get("record_id"), row.get("notes"))].append(product["dsld_id"])
    return {"_metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
                           "audit_kind": "catalog_wide_certification_census", "total_products_scanned": len(products),
                           "input_file_count": file_count, "input_error_count": len(errors),
                           "stage_duplicates": duplicates, "clean_only_products": clean_count,
                           "complete": not errors and not limit,
                           "input_sha256": input_fingerprints},
            "summary": {"by_cause": dict(Counter(p["cause"] for p in products)),
                        "products_without_claim": sum(not p.get("has_claim") for p in products if p["cause"] != "input_error")},
            "products": products, "input_errors": errors, "override_issues": audit_overrides(registry),
            "review_clusters": [{"program": key[0], "record_id": key[1], "notes": key[2], "dsld_ids": ids}
                                for key, ids in sorted(clusters.items(), key=lambda item: -len(item[1]))]}


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
    parser.add_argument("--products-root", type=Path, help="Census all enriched and clean-only labels instead of exported claims.")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH, help="Candidate registry snapshot; production registry remains untouched.")
    parser.add_argument("--overrides", type=Path, default=OVERRIDES_PATH, help="Reviewed mappings used for this comparison.")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading registry...", file=sys.stderr)
    if args.products_root and (not args.registry.is_file() or not args.overrides.is_file()):
        parser.error("census requires existing registry and reviewed override inputs")
    source_paths = (args.registry, args.overrides, Path(__file__), SCRIPTS_ROOT / "cert_resolver.py")
    source_fingerprints = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths} if args.products_root else {}
    registry = CertRegistry.load(registry_path=args.registry, overrides_path=args.overrides)
    covered_programs = _registry_covered_programs(registry)
    print(f"  registry loaded: {sum(len(v) for v in registry.records_by_program.values())} records across {len(covered_programs)} programs", file=sys.stderr)

    if args.products_root:
        payload = census(args.products_root, registry, limit=args.limit)
        payload["_metadata"]["source_sha256"] = source_fingerprints
        current_fingerprints = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
        payload["_metadata"]["source_unchanged"] = source_fingerprints == current_fingerprints
        if source_fingerprints != current_fingerprints:
            payload["input_errors"].append({"error": "source or registry changed during census"})
            payload["_metadata"]["input_error_count"] = len(payload["input_errors"])
            payload["_metadata"]["complete"] = False
        json_path = args.out_dir / "certification_census.json"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        md_path = args.out_dir / "certification_census.md"
        md_path.write_text("# Catalog-wide certification census\n\n" + json.dumps(payload["_metadata"], indent=2) +
                           "\n\n" + json.dumps(payload["summary"], indent=2) +
                           "\n\nMatching outcomes are diagnostics, not new certification or clinical claims. "
                           "See JSON product rows, review clusters, override issues and explicit input errors.\n", encoding="utf-8")
        print(f"Wrote {json_path}", file=sys.stderr)
        if payload["input_errors"]:
            raise SystemExit(1)
        return

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
