#!/usr/bin/env python3
"""P1.7.1 — cert needs_review cluster report.

Read-only audit tool. Scans enriched product blobs for
`verified_cert_programs` entries with `scope=needs_review`, clusters
them by the registry row they're matching against (program +
record_id), and emits a JSON + markdown triage report.

Per Codex's 2026-05-20 catalog audit, ~458 entries / 456 products
sit in `needs_review` — a mixed bag of real product-line variants
(GNC AMP Wheybolic flavors, Sports Research Omega-3 flavor variants,
GoL Sport flavor variants) and real false positives (Nature Made
dose/form mismatches, Nordic-vs-Naturalis brand collisions, Thorne
wrong-product matches).

The report clusters those entries so a reviewer can decide as a
group whether each registry row is legit. Cluster decisions then
become entries in
`scripts/data/curated_overrides/cert_verification_overrides.json`
with `status: verified` (good match, scope: product_line) or
`status: rejected` (false positive, scope: claimed_only).

This script does NOT modify the override file. It writes a triage
artifact under `scripts/api_audit/reports/`. The override file edits
are intentionally manual — same discipline as the existing 32
overrides shipped with the resolver.

Usage:
    python3 scripts/api_audit/cert_needs_review_cluster.py \\
        [--products-root scripts/products] \\
        [--out-dir scripts/api_audit/reports]

Outputs:
    cert_needs_review_clusters.json
    cert_needs_review_clusters.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_OUT_DIR = SCRIPTS_ROOT / "api_audit" / "reports"


# --- IO -----------------------------------------------------------------


def load_enriched_products(
    products_root: Path,
    *,
    limit: int | None = None,
) -> Iterable[Dict[str, Any]]:
    """Yield enriched product dicts from `output_*_enriched` subdirs.

    `limit` caps the number yielded (useful for tests + smoke runs).
    """
    yielded = 0
    for path in products_root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        items = data if isinstance(data, list) else (
            data.get("products", data.get("items", []))
        )
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            yield item
            yielded += 1
            if limit is not None and yielded >= limit:
                return


# --- Clustering ---------------------------------------------------------


def build_clusters(products: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return clusters of `needs_review` cert entries grouped by
    (program, record_id). Returns a sorted list for stable output."""
    raw_groups: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {
            "program": "",
            "record_id": "",
            "matched_brand": "",
            "matched_product": "",
            "members": [],
        }
    )

    for product in products:
        if not isinstance(product, dict):
            continue
        verified = product.get("verified_cert_programs") or []
        if not isinstance(verified, list):
            continue
        for entry in verified:
            if not isinstance(entry, dict):
                continue
            if entry.get("scope") != "needs_review":
                continue
            program = str(entry.get("program") or "").strip()
            record_id = str(entry.get("record_id") or "").strip()
            if not program and not record_id:
                continue
            key = (program.lower(), record_id)
            group = raw_groups[key]
            group["program"] = program or group["program"]
            group["record_id"] = record_id or group["record_id"]
            # Use the first observed matched_brand/matched_product; they
            # should be identical across members of the same record_id
            # cluster (the resolver matched them all to the same row).
            if not group["matched_brand"] and entry.get("matched_brand"):
                group["matched_brand"] = str(entry.get("matched_brand"))
            if not group["matched_product"] and entry.get("matched_product"):
                group["matched_product"] = str(entry.get("matched_product"))
            # Enriched blobs use camelCase (brandName, fullName) at the
            # top level; v3-scored blobs use snake_case (brand_name,
            # product_name). Accept both shapes so the cluster report
            # works regardless of which artifact stage we read.
            brand_name = (
                product.get("brand_name")
                or product.get("brandName")
                or ""
            )
            product_name = (
                product.get("product_name")
                or product.get("fullName")
                or product.get("name")
                or ""
            )
            member = {
                "dsld_id": str(product.get("dsld_id") or product.get("id") or ""),
                "brand_name": str(brand_name),
                "product_name": str(product_name),
                "matched_brand": str(entry.get("matched_brand") or ""),
                "matched_product": str(entry.get("matched_product") or ""),
                "evidence_source": entry.get("evidence_source"),
                "match_confidence": entry.get("match_confidence"),
            }
            member["triage_hint"] = classify_member(member)
            group["members"].append(member)

    clusters = list(raw_groups.values())
    # Sort clusters: largest member count first, then alphabetically by program.
    clusters.sort(key=lambda c: (-len(c["members"]), c["program"].lower(), c["record_id"]))
    # Sort each cluster's members by dsld_id for stable output.
    for c in clusters:
        c["members"].sort(key=lambda m: m["dsld_id"])
        c["member_count"] = len(c["members"])
        c["suggested_action"] = _aggregate_cluster_action(c["members"])
    return clusters


def _aggregate_cluster_action(members: List[Dict[str, Any]]) -> str:
    """Aggregate per-member triage hints into a cluster-level suggestion.

    - If ALL members hint REJECT → "reject"
    - If ALL members hint VERIFY → "verify_product_line"
    - Else "review" — mixed signals warrant a human look
    """
    actions = {m["triage_hint"]["likely_action"] for m in members if m.get("triage_hint")}
    if not actions:
        return "review"
    if actions == {"reject"}:
        return "reject"
    if actions == {"verify_product_line"}:
        return "verify_product_line"
    return "review"


# --- Triage heuristics --------------------------------------------------


# Dose-bearing tokens we look for in product names (e.g. "1000 mg", "200 IU").
_DOSE_TOKEN_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|ug|µg|iu|g|billion|b|cfu|ml)\b",
    re.IGNORECASE,
)
# Common flavor / variant tokens. Presence in product_name but not
# matched_product strongly suggests a product-line variant.
_FLAVOR_TOKENS = (
    "vanilla", "chocolate", "strawberry", "lemon", "berry", "mixed",
    "coconut", "cookies and cream", "fruit punch", "blue raspberry",
    "tropical", "cinnamon", "mocha", "caramel", "peanut", "matcha",
    "natural flavor", "unflavored", "raspberry", "cherry", "orange",
    "salted", "double", "triple", "extra", "extra strength",
)


def classify_member(member: Dict[str, Any]) -> Dict[str, Any]:
    """Apply triage heuristics to a single cluster member.

    Returns a dict with:
        likely_action: "reject" | "verify_product_line" | "review"
        reasons: list of reason codes

    Conservative: only emits "reject" when there's a strong false-positive
    signal (dose mismatch or brand-name collision). Only emits
    "verify_product_line" when the product name is the registry product
    plus a flavor/variant suffix. Everything else gets "review" so a
    human triages it.
    """
    reasons: List[str] = []
    likely_action = "review"

    product_name = str(member.get("product_name") or "").strip()
    matched_product = str(member.get("matched_product") or "").strip()
    brand_name = str(member.get("brand_name") or "").strip()
    matched_brand = str(member.get("matched_brand") or "").strip()

    # 1. Dose / form mismatch — e.g. "Vitamin E 200 IU" vs "Vitamin E 1000 IU"
    if product_name and matched_product:
        product_doses = _extract_dose_tokens(product_name)
        matched_doses = _extract_dose_tokens(matched_product)
        if product_doses and matched_doses and product_doses != matched_doses:
            # Different dose values on the same form → mismatch.
            reasons.append("dose_mismatch")
            likely_action = "reject"

    # 2. Brand-name collision — brand and matched_brand are not the same brand.
    if brand_name and matched_brand:
        if not _brands_likely_same(brand_name, matched_brand):
            reasons.append("brand_mismatch")
            # Brand mismatch is a strong false-positive signal — reject
            # even if a dose match would otherwise suggest verify.
            likely_action = "reject"

    if likely_action == "reject":
        return {"likely_action": likely_action, "reasons": reasons}

    # 3. Flavor / variant — product name extends matched_product with a
    # flavor/variant token. Cautious: only when the matched_product is a
    # prefix or contained within product_name AND a flavor token is present.
    if product_name and matched_product:
        normalized_product = _normalize_text(product_name)
        normalized_matched = _normalize_text(matched_product)
        if normalized_matched and normalized_matched in normalized_product:
            extra = normalized_product.replace(normalized_matched, "", 1).strip()
            if any(tok in extra for tok in _FLAVOR_TOKENS):
                reasons.append("flavor_variant")
                likely_action = "verify_product_line"
            elif extra and len(extra.split()) <= 3:
                # Short trailing differentiator (e.g. "Pure Isolate Mass XXX
                # Vanilla" vs "Pure Isolate") — likely line variant but
                # require human eyes.
                reasons.append("short_suffix_variant")

    if not reasons:
        reasons.append("no_strong_signal")
    return {"likely_action": likely_action, "reasons": reasons}


# --- Helpers ------------------------------------------------------------


def _extract_dose_tokens(text: str) -> set:
    """Extract (value, unit) dose tokens, normalized for comparison."""
    tokens = set()
    for match in _DOSE_TOKEN_RE.finditer(text):
        value_str, unit = match.groups()
        try:
            value = float(value_str)
        except ValueError:
            continue
        tokens.add((value, unit.lower().replace("ug", "mcg").replace("µg", "mcg")))
    return tokens


def _normalize_text(text: str) -> str:
    """Lowercase + collapse whitespace + strip dose tokens for comparison."""
    text = text.lower()
    # Strip dose tokens so we compare the substantive product name.
    text = _DOSE_TOKEN_RE.sub(" ", text)
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _brands_likely_same(brand_a: str, brand_b: str) -> bool:
    """Conservative brand-equality check: lowercased substring overlap.

    Examples:
      "Nordic Naturals" vs "Nordic Naturals, Inc" → same
      "GNC" vs "GNC Holdings" → same
      "Nordic Naturals" vs "Naturalis Inc" → different ('naturals' != 'naturalis')

    Uses normalized brand-token overlap rather than full string equality
    because brand strings vary (LLC / Inc suffixes, trailing comma).
    """
    a = _brand_tokens(brand_a)
    b = _brand_tokens(brand_b)
    if not a or not b:
        return False
    # Require at least one shared brand-core token AND that the shorter
    # set is a subset modulo legal suffixes.
    legal_suffixes = {"inc", "llc", "co", "corp", "ltd", "company", "holdings"}
    a_core = a - legal_suffixes
    b_core = b - legal_suffixes
    if not a_core or not b_core:
        return False
    return bool(a_core & b_core) and (a_core <= b_core or b_core <= a_core)


def _brand_tokens(brand: str) -> set:
    """Lowercase set of brand-name tokens (alphanumeric splits)."""
    text = brand.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return {tok for tok in text.split() if tok}


# --- Summary + reports --------------------------------------------------


def summarize(clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Top-level summary fields for the report header."""
    member_count = sum(c["member_count"] for c in clusters)
    distinct_brands = set()
    distinct_programs = set()
    suggested_action_counts: Dict[str, int] = defaultdict(int)
    for c in clusters:
        distinct_programs.add(c["program"])
        for m in c["members"]:
            if m.get("brand_name"):
                distinct_brands.add(m["brand_name"])
        suggested_action_counts[c["suggested_action"]] += 1
    return {
        "cluster_count": len(clusters),
        "member_count": member_count,
        "distinct_programs": len(distinct_programs),
        "distinct_brands": len(distinct_brands),
        "suggested_action_counts": dict(suggested_action_counts),
    }


def write_reports(
    clusters: List[Dict[str, Any]],
    out_dir: Path,
) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(clusters)
    payload = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase": "P1.7.1_cert_needs_review_cluster",
            "source": "verified_cert_programs[scope=needs_review]",
        },
        "summary": summary,
        "clusters": clusters,
    }
    json_path = out_dir / "cert_needs_review_clusters.json"
    md_path = out_dir / "cert_needs_review_clusters.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    md_path.write_text(_render_markdown(summary, clusters))
    return json_path, md_path


def _render_markdown(summary: Dict[str, Any], clusters: List[Dict[str, Any]]) -> str:
    lines = [
        "# Cert `needs_review` cluster triage report",
        "",
        f"_Generated: {datetime.now(timezone.utc).isoformat()}_",
        "",
        "## Summary",
        "",
        f"- **Clusters:** {summary['cluster_count']}",
        f"- **Members (products):** {summary['member_count']}",
        f"- **Distinct programs:** {summary['distinct_programs']}",
        f"- **Distinct brands:** {summary['distinct_brands']}",
        "- **Suggested actions:**",
    ]
    for action, count in sorted(summary["suggested_action_counts"].items()):
        lines.append(f"  - `{action}`: {count}")
    lines.append("")
    lines.append("## Clusters")
    lines.append("")
    for cluster in clusters:
        lines.append(
            f"### {cluster['program']} — {cluster.get('matched_product', '')} "
            f"(record_id `{cluster['record_id']}`)"
        )
        lines.append("")
        lines.append(
            f"- **Suggested action:** `{cluster['suggested_action']}`"
        )
        lines.append(f"- **Member count:** {cluster['member_count']}")
        lines.append(
            f"- **Registry match brand:** {cluster.get('matched_brand', '?')}"
        )
        lines.append("")
        lines.append("| DSLD | Brand | Product | Hint | Reasons |")
        lines.append("|------|-------|---------|------|---------|")
        for member in cluster["members"]:
            hint = member.get("triage_hint", {})
            reasons = ", ".join(hint.get("reasons", []))
            lines.append(
                f"| {member['dsld_id']} | {member['brand_name']} | "
                f"{member['product_name']} | `{hint.get('likely_action', '?')}` | "
                f"{reasons} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


# --- CLI ----------------------------------------------------------------


def _parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--products-root", type=Path, default=DEFAULT_PRODUCTS_ROOT,
        help="Path to scripts/products containing output_*_enriched subdirs.",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT_DIR,
        help="Directory to write JSON + markdown reports.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap number of products read (useful for testing).",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv)
    products = list(load_enriched_products(args.products_root, limit=args.limit))
    clusters = build_clusters(products)
    json_path, md_path = write_reports(clusters, args.out_dir)
    summary = summarize(clusters)
    print(f"Inspected {len(products)} products → {summary['cluster_count']} clusters")
    print(f"  json: {json_path}")
    print(f"  md:   {md_path}")
    print(f"  suggested actions: {summary['suggested_action_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
