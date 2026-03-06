#!/usr/bin/env python3
"""
Comprehensive brand audit: Thorne, Nordic-Naturals, Nature-Made, Lozenges, Olly
Checks: counts, invariants, parent_total, A1=0, scoring status, score distribution,
        form fallbacks, unmapped ingredients.
"""

import json
import os
import glob
import sys
from collections import defaultdict, Counter
from statistics import median, quantiles

BASE = "/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts"

BRANDS = {
    "Thorne": {
        "clean":   "output_Thorne-2-17-26/cleaned",
        "enrich":  "output_Thorne-2-17-26_enriched/enriched",
        "score":   "output_Thorne-2-17-26_scored/scored",
    },
    "Nordic-Naturals": {
        "clean":   "output_Nordic-Naturals-2-17-26-L511/cleaned",
        "enrich":  "output_Nordic-Naturals-2-17-26-L511_enriched/enriched",
        "score":   "output_Nordic-Naturals-2-17-26-L511_scored/scored",
    },
    "Nature-Made": {
        "clean":   "output_Nature-Made-2-17-26-L827/cleaned",
        "enrich":  "output_Nature-Made-2-17-26-L827_enriched/enriched",
        "score":   "output_Nature-Made-2-17-26-L827_scored/scored",
    },
    "Lozenges": {
        "clean":   "output_Lozenges-978labels-11-11-25/cleaned",
        "enrich":  "output_Lozenges-978labels-11-11-25_enriched/enriched",
        "score":   "output_Lozenges-978labels-11-11-25_scored/scored",
    },
    "Olly": {
        "clean":   "output_Olly-2-17-26-L187/cleaned",
        "enrich":  "output_Olly-2-17-26-L187_enriched/enriched",
        "score":   "output_Olly-2-17-26-L187_scored/scored",
    },
}


def load_json_files(directory, pattern="*.json"):
    """Load all JSON files from a directory, return list of records."""
    path = os.path.join(BASE, directory)
    files = sorted(glob.glob(os.path.join(path, pattern)))
    records = []
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
            if isinstance(data, list):
                records.extend(data)
            else:
                records.append(data)
    return records


def pct(n, total):
    if total == 0:
        return "N/A"
    return f"{100*n/total:.1f}%"


def percentile(data, p):
    """Simple percentile calculation."""
    if not data:
        return None
    sorted_d = sorted(data)
    idx = int(len(sorted_d) * p / 100)
    idx = min(idx, len(sorted_d) - 1)
    return sorted_d[idx]


def audit_brand(brand_name, paths):
    print(f"\n{'='*80}")
    print(f"BRAND: {brand_name}")
    print(f"{'='*80}")

    # ── CHECK 1: Product Counts ───────────────────────────────────────────────
    print(f"\n--- CHECK 1: Product Counts ---")
    clean_records = load_json_files(paths["clean"])
    enrich_records = load_json_files(paths["enrich"])
    score_records  = load_json_files(paths["score"])

    n_clean  = len(clean_records)
    n_enrich = len(enrich_records)
    n_score  = len(score_records)

    # Also count raw input — try to find source DSLD files or just note it's pre-pipeline
    print(f"  Clean:   {n_clean}")
    print(f"  Enrich:  {n_enrich}")
    print(f"  Score:   {n_score}")

    count_ok = (n_clean == n_enrich == n_score)
    if count_ok:
        print(f"  [OK] No product drops across pipeline")
    else:
        drop_enrich = n_clean - n_enrich
        drop_score  = n_enrich - n_score
        if drop_enrich != 0:
            print(f"  [BUG] DROP: clean→enrich: {drop_enrich}")
        if drop_score != 0:
            print(f"  [BUG] DROP: enrich→score: {drop_score}")
        if n_enrich > n_clean:
            print(f"  [WARNING] Enrich has MORE records than clean ({n_enrich} > {n_clean})")
        if n_score > n_enrich:
            print(f"  [WARNING] Score has MORE records than enrich ({n_score} > {n_enrich})")

    # ── CHECK 2: Core Invariants (enriched) ──────────────────────────────────
    print(f"\n--- CHECK 2: Core Invariants (enriched) ---")
    inv_violations = []
    unevaluated_violations = []

    for prod in enrich_records:
        rid = prod.get("report_id") or prod.get("dsld_id") or prod.get("id", "?")
        iq = prod.get("ingredient_quality_data", {})

        # unevaluated_records == 0
        uneval = iq.get("unevaluated_records", None)
        if uneval is None:
            unevaluated_violations.append((rid, "unevaluated_records field MISSING"))
        elif uneval != 0:
            unevaluated_violations.append((rid, f"unevaluated_records={uneval}"))

        # len(scorable) + len(skipped) == len(active) + len(promoted)
        scorable   = iq.get("ingredients_scorable", [])
        skipped    = iq.get("ingredients_skipped", [])
        active     = prod.get("activeIngredients", [])
        promoted   = iq.get("promoted_from_inactive", [])

        lhs = len(scorable) + len(skipped)
        rhs = len(active) + len(promoted)
        if lhs != rhs:
            inv_violations.append((rid, f"scorable({len(scorable)})+skipped({len(skipped)})={lhs} != active({len(active)})+promoted({len(promoted)})={rhs}"))

    if not unevaluated_violations:
        print(f"  [OK] All {n_enrich} products have unevaluated_records==0")
    else:
        print(f"  [BUG] {len(unevaluated_violations)} products with unevaluated_records != 0:")
        for rid, msg in unevaluated_violations[:10]:
            print(f"        {rid}: {msg}")
        if len(unevaluated_violations) > 10:
            print(f"        ... and {len(unevaluated_violations)-10} more")

    if not inv_violations:
        print(f"  [OK] scorable+skipped == active+promoted for all products")
    else:
        print(f"  [BUG] {len(inv_violations)} invariant violations:")
        for rid, msg in inv_violations[:10]:
            print(f"        {rid}: {msg}")
        if len(inv_violations) > 10:
            print(f"        ... and {len(inv_violations)-10} more")

    # ── CHECK 3: is_parent_total analysis ─────────────────────────────────────
    print(f"\n--- CHECK 3: is_parent_total Analysis ---")
    pt_product_count   = 0  # products with at least one is_parent_total=True
    pt_distribution    = Counter()  # n_parent_totals per product
    pt_canonical_ids   = Counter()  # canonical_id frequency when is_parent_total=True
    pt_no_nested_child = []  # parent_total with no nested sibling
    pt_orphan_qty      = []  # parent_total=True AND all children have qty=0

    for prod in enrich_records:
        rid = prod.get("report_id") or prod.get("dsld_id") or prod.get("id", "?")
        iq = prod.get("ingredient_quality_data", {})
        scorable = iq.get("ingredients_scorable", [])

        # Build a map of canonical_id → list of ingredients
        cid_map = defaultdict(list)
        for ing in scorable:
            cid = ing.get("canonical_id")
            if cid:
                cid_map[cid].append(ing)

        pt_in_product = 0
        for ing in scorable:
            if ing.get("is_parent_total") is True:
                pt_in_product += 1
                cid = ing.get("canonical_id")
                if cid:
                    pt_canonical_ids[cid] += 1

                # Verify: at least one sibling has is_nested_ingredient=True and same cid
                siblings = cid_map.get(cid, [])
                has_nested_child = any(
                    s.get("is_nested_ingredient") is True and s is not ing
                    for s in siblings
                )
                if not has_nested_child:
                    pt_no_nested_child.append((rid, cid, ing.get("ingredient_name")))

                # Check: are all siblings (children, not the parent itself) qty=0?
                children = [s for s in siblings if s is not ing]
                if children:
                    all_children_zero = all(
                        (s.get("quantity") or 0) == 0 for s in children
                    )
                    if all_children_zero:
                        pt_orphan_qty.append((rid, cid, ing.get("ingredient_name")))

        if pt_in_product > 0:
            pt_product_count += 1
            pt_distribution[pt_in_product] += 1

    print(f"  Products with >=1 is_parent_total=True: {pt_product_count} / {n_enrich} ({pct(pt_product_count, n_enrich)})")
    if pt_distribution:
        print(f"  Distribution (n_parent_totals per product):")
        for k in sorted(pt_distribution.keys()):
            label = f"    {k} parent-total{'s' if k>1 else ''}"
            print(f"  {label}: {pt_distribution[k]} products")

    print(f"  Top 10 canonical_ids as parent_total:")
    for cid, cnt in pt_canonical_ids.most_common(10):
        print(f"    {cid}: {cnt}")

    if not pt_no_nested_child:
        print(f"  [OK] All parent_total flags have at least one nested child sibling")
    else:
        print(f"  [WARNING] {len(pt_no_nested_child)} parent_total without nested child sibling:")
        for rid, cid, name in pt_no_nested_child[:10]:
            print(f"    Product {rid}: canonical_id={cid}, name={name}")

    if not pt_orphan_qty:
        print(f"  [OK] No parent_total=True with all children qty=0 (bug was fixed)")
    else:
        print(f"  [BUG] {len(pt_orphan_qty)} parent_total where ALL children have qty=0:")
        for rid, cid, name in pt_orphan_qty[:10]:
            print(f"    Product {rid}: canonical_id={cid}, name={name}")

    # ── CHECK 4: A1=0 edge cases ──────────────────────────────────────────────
    print(f"\n--- CHECK 4: A1=0 Edge Cases (scorable but A1=0) ---")
    a1_zero_cases = []

    for prod in score_records:
        rid = prod.get("report_id") or prod.get("dsld_id") or prod.get("id", "?")
        product_name = prod.get("productName") or prod.get("product_name", "?")
        scored_ings = prod.get("scored_ingredients", [])

        for ing in scored_ings:
            breakdown = ing.get("scoring_breakdown", {})
            a1 = breakdown.get("A1_bioavailability_form")
            if a1 == 0:
                a1_zero_cases.append({
                    "product_id": rid,
                    "product_name": product_name,
                    "ingredient": ing.get("ingredient_name", "?"),
                    "form": ing.get("form_matched") or ing.get("form", "?"),
                    "canonical_id": ing.get("canonical_id", "?"),
                    "is_parent_total": ing.get("is_parent_total", False),
                })

    if not a1_zero_cases:
        print(f"  [OK] No scored ingredients with A1=0")
    else:
        print(f"  [WARNING] {len(a1_zero_cases)} scored ingredients with A1=0:")
        shown = set()
        for c in a1_zero_cases[:20]:
            key = (c["product_id"], c["canonical_id"])
            if key not in shown:
                shown.add(key)
                print(f"    [{c['product_id']}] {c['product_name'][:50]}")
                print(f"      ingredient={c['ingredient']}, form={c['form']}, cid={c['canonical_id']}, is_parent_total={c['is_parent_total']}")
        if len(a1_zero_cases) > 20:
            print(f"    ... and {len(a1_zero_cases)-20} more")

    # ── CHECK 5: Scoring Status Breakdown ─────────────────────────────────────
    print(f"\n--- CHECK 5: Scoring Status Breakdown ---")
    status_counter = Counter()
    for prod in score_records:
        status = prod.get("scoring_status") or prod.get("status", "UNKNOWN")
        status_counter[status] += 1

    total_scored = len(score_records)
    for status in ["SAFE", "CAUTION", "POOR", "NOT_SCORED", "BLOCKED", "UNSAFE", "UNKNOWN"]:
        cnt = status_counter.get(status, 0)
        if cnt > 0 or status in ["SAFE", "CAUTION", "POOR"]:
            flag = ""
            if status == "SAFE" and brand_name == "Thorne" and cnt < total_scored * 0.90:
                flag = "  [WARNING] Expected ~90%+ SAFE for Thorne"
            print(f"  {status:12s}: {cnt:5d}  ({pct(cnt, total_scored)}){flag}")

    # ── CHECK 6: Score Distribution ───────────────────────────────────────────
    print(f"\n--- CHECK 6: Score Distribution ---")
    scores = []
    for prod in score_records:
        s = prod.get("final_score")
        if s is not None:
            try:
                scores.append(float(s))
            except (ValueError, TypeError):
                pass

    if scores:
        scores_sorted = sorted(scores)
        print(f"  n={len(scores)}")
        print(f"  min={scores_sorted[0]:.2f}")
        print(f"  p25={percentile(scores, 25):.2f}")
        print(f"  p50={percentile(scores, 50):.2f}")
        print(f"  p75={percentile(scores, 75):.2f}")
        print(f"  max={scores_sorted[-1]:.2f}")

        # Flag outliers: anything below 20 or above 100 is suspicious
        very_low = [s for s in scores if s < 20]
        very_high = [s for s in scores if s > 100]
        if very_low:
            print(f"  [WARNING] {len(very_low)} products with score < 20")
        if very_high:
            print(f"  [WARNING] {len(very_high)} products with score > 100 (unusual)")
    else:
        print(f"  [WARNING] No final_score values found")

    # ── CHECK 7: Thorne-specific post-fix drift ───────────────────────────────
    if brand_name == "Thorne":
        print(f"\n--- CHECK 7: Thorne Post-Fix Drift Check ---")
        pt_a1_zero = []
        pt_qty_bug  = []

        # Use scored data for A1 check
        # Build scored ingredient index by product
        for prod in score_records:
            rid = prod.get("report_id") or prod.get("dsld_id") or prod.get("id", "?")
            scored_ings = prod.get("scored_ingredients", [])

            cid_map_scored = defaultdict(list)
            for ing in scored_ings:
                cid = ing.get("canonical_id")
                if cid:
                    cid_map_scored[cid].append(ing)

            for ing in scored_ings:
                if ing.get("is_parent_total") is True:
                    breakdown = ing.get("scoring_breakdown", {})
                    a1 = breakdown.get("A1_bioavailability_form", None)
                    if a1 == 0:
                        pt_a1_zero.append((rid, ing.get("ingredient_name"), a1))

                    # Check qty bug: parent qty > 0 but all children qty = 0
                    cid = ing.get("canonical_id")
                    parent_qty = ing.get("quantity") or 0
                    children = [s for s in cid_map_scored.get(cid, []) if s is not ing]
                    if parent_qty > 0 and children:
                        all_children_zero = all((s.get("quantity") or 0) == 0 for s in children)
                        if all_children_zero:
                            pt_qty_bug.append((rid, ing.get("ingredient_name"), parent_qty))

        if not pt_a1_zero:
            print(f"  [OK] No parent_total ingredients with A1=0 in scored data")
        else:
            print(f"  [BUG] {len(pt_a1_zero)} parent_total ingredients got A1=0:")
            for rid, name, a1 in pt_a1_zero[:10]:
                print(f"    Product {rid}: {name}, A1={a1}")

        if not pt_qty_bug:
            print(f"  [OK] No parent_total with qty>0 and all children qty=0")
        else:
            print(f"  [BUG] {len(pt_qty_bug)} parent_total where qty>0 but all children qty=0:")
            for rid, name, qty in pt_qty_bug[:10]:
                print(f"    Product {rid}: {name}, parent_qty={qty}")

    # ── CHECK 8: Form Fallbacks ───────────────────────────────────────────────
    print(f"\n--- CHECK 8: Form Fallbacks (form_unmapped_fallback) ---")
    fallback_counter = Counter()  # (ingredient_name, fallback_form) → count

    for prod in enrich_records:
        iq = prod.get("ingredient_quality_data", {})
        scorable = iq.get("ingredients_scorable", [])
        for ing in scorable:
            reason = ing.get("identity_decision_reason", "")
            if "form_unmapped_fallback" in str(reason):
                ing_name = ing.get("ingredient_name", "?")
                form     = ing.get("form_matched") or ing.get("form", "?")
                fallback_counter[(ing_name, form)] += 1

    total_fallbacks = sum(fallback_counter.values())
    print(f"  Total fallback usages: {total_fallbacks}")
    if fallback_counter:
        print(f"  Top 10 (ingredient, form) by count:")
        for (ing, form), cnt in fallback_counter.most_common(10):
            flag = ""
            if "unspecified" not in str(form).lower() and cnt > 5:
                flag = "  [WARNING] non-unspecified fallback form"
            print(f"    ({ing!r}, {form!r}): {cnt}{flag}")
    else:
        print(f"  [OK] No form_unmapped_fallback instances")

    # ── CHECK 9: Unmapped Ingredients ─────────────────────────────────────────
    print(f"\n--- CHECK 9: Unmapped Actives ---")
    unmapped_counter = Counter()

    for prod in enrich_records:
        iq = prod.get("ingredient_quality_data", {})
        scorable = iq.get("ingredients_scorable", [])
        for ing in scorable:
            if ing.get("mapped") is False:
                ing_name = ing.get("ingredient_name", "?")
                unmapped_counter[ing_name] += 1

    total_unmapped_instances = sum(unmapped_counter.values())
    print(f"  Total unmapped ingredient instances: {total_unmapped_instances}")
    print(f"  Unique unmapped ingredient names: {len(unmapped_counter)}")
    if unmapped_counter:
        print(f"  Top 10 by frequency:")
        for name, cnt in unmapped_counter.most_common(10):
            print(f"    {name!r}: {cnt}")
    else:
        print(f"  [OK] No unmapped actives found")

    return {
        "brand": brand_name,
        "n_clean": n_clean,
        "n_enrich": n_enrich,
        "n_score": n_score,
        "status_counter": dict(status_counter),
        "scores": scores,
        "pt_product_count": pt_product_count,
    }


def main():
    results = []
    for brand_name, paths in BRANDS.items():
        try:
            r = audit_brand(brand_name, paths)
            results.append(r)
        except Exception as e:
            print(f"\n[ERROR] Failed to audit {brand_name}: {e}")
            import traceback
            traceback.print_exc()

    # ── Cross-brand summary ───────────────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print(f"CROSS-BRAND SUMMARY")
    print(f"{'='*80}")
    print(f"\n{'Brand':<20} {'Clean':>7} {'Enrich':>7} {'Score':>7} {'SAFE%':>7} {'p50':>7} {'PT_prods':>10}")
    print("-" * 70)
    for r in results:
        total = r["n_score"]
        safe = r["status_counter"].get("SAFE", 0)
        safe_pct = f"{100*safe/total:.1f}%" if total > 0 else "N/A"
        p50 = f"{percentile(r['scores'], 50):.1f}" if r["scores"] else "N/A"
        pt = r.get("pt_product_count", 0)
        count_ok = "OK" if (r["n_clean"] == r["n_enrich"] == r["n_score"]) else "MISMATCH"
        print(f"  {r['brand']:<18} {r['n_clean']:>7} {r['n_enrich']:>7} {r['n_score']:>7} {safe_pct:>7} {p50:>7} {pt:>10}  [{count_ok}]")

    print(f"\nAudit complete.")


if __name__ == "__main__":
    main()
