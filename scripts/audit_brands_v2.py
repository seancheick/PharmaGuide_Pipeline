#!/usr/bin/env python3
"""
Comprehensive brand audit v2 — corrected field names.
Brands: Thorne, Nordic-Naturals, Nature-Made, Lozenges, Olly
"""

import json
import os
import glob
import sys
from collections import defaultdict, Counter

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


def load_json_dir(directory):
    path = os.path.join(BASE, directory)
    files = sorted(glob.glob(os.path.join(path, "*.json")))
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


def percentile(sorted_data, p):
    if not sorted_data:
        return None
    idx = max(0, min(int(len(sorted_data) * p / 100), len(sorted_data) - 1))
    return sorted_data[idx]


def audit_brand(brand_name, paths):
    print(f"\n{'='*80}")
    print(f"BRAND: {brand_name}")
    print(f"{'='*80}")

    # ─── Load all data ────────────────────────────────────────────────────────
    clean_records  = load_json_dir(paths["clean"])
    enrich_records = load_json_dir(paths["enrich"])
    score_records  = load_json_dir(paths["score"])

    n_clean  = len(clean_records)
    n_enrich = len(enrich_records)
    n_score  = len(score_records)

    # ─── CHECK 1: Product Counts ──────────────────────────────────────────────
    print(f"\n--- CHECK 1: Product Counts ---")
    print(f"  clean={n_clean}  enrich={n_enrich}  score={n_score}")
    if n_clean == n_enrich == n_score:
        print(f"  [OK] No product drops across pipeline")
    else:
        if n_enrich != n_clean:
            diff = n_clean - n_enrich
            tag = "BUG" if diff > 0 else "WARNING"
            print(f"  [{tag}] clean({n_clean}) → enrich({n_enrich}): delta={diff}")
        if n_score != n_enrich:
            diff = n_enrich - n_score
            tag = "BUG" if diff > 0 else "WARNING"
            print(f"  [{tag}] enrich({n_enrich}) → score({n_score}): delta={diff}")

    # ─── CHECK 2: Core Invariants (enriched) ─────────────────────────────────
    print(f"\n--- CHECK 2: Core Invariants (enriched) ---")
    uneval_violations  = []
    balance_violations = []

    for prod in enrich_records:
        rid = prod.get("dsld_id") or prod.get("id") or prod.get("report_id", "?")
        iq = prod.get("ingredient_quality_data", {})

        uneval = iq.get("unevaluated_records")
        if uneval is None:
            uneval_violations.append((rid, "MISSING unevaluated_records"))
        elif uneval != 0:
            uneval_violations.append((rid, f"unevaluated_records={uneval}"))

        scorable  = iq.get("ingredients_scorable", [])
        skipped   = iq.get("ingredients_skipped", [])
        active    = prod.get("activeIngredients", [])
        promoted  = iq.get("promoted_from_inactive", [])
        lhs = len(scorable) + len(skipped)
        rhs = len(active) + len(promoted)
        if lhs != rhs:
            balance_violations.append(
                (rid, f"scorable({len(scorable)})+skipped({len(skipped)})={lhs} "
                      f"!= active({len(active)})+promoted({len(promoted)})={rhs}")
            )

    if not uneval_violations:
        print(f"  [OK] All {n_enrich} products have unevaluated_records==0")
    else:
        print(f"  [BUG] {len(uneval_violations)} unevaluated_records violations:")
        for rid, msg in uneval_violations[:10]:
            print(f"    {rid}: {msg}")
        if len(uneval_violations) > 10:
            print(f"    ... +{len(uneval_violations)-10} more")

    if not balance_violations:
        print(f"  [OK] scorable+skipped == active+promoted for all products")
    else:
        print(f"  [BUG] {len(balance_violations)} balance violations:")
        for rid, msg in balance_violations[:10]:
            print(f"    {rid}: {msg}")
        if len(balance_violations) > 10:
            print(f"    ... +{len(balance_violations)-10} more")

    # ─── CHECK 3: is_parent_total Analysis (enriched data) ───────────────────
    print(f"\n--- CHECK 3: is_parent_total Analysis ---")
    pt_products         = 0
    pt_dist             = Counter()   # n_parent_totals per product
    pt_cid_freq         = Counter()   # canonical_id frequency
    pt_no_nested_child  = []          # parent has no nested sibling
    pt_orphan_qty       = []          # parent qty>0 but all children qty==0
    pt_children_ok      = 0
    pt_children_bad     = 0

    for prod in enrich_records:
        rid = prod.get("dsld_id") or prod.get("id") or prod.get("report_id", "?")
        prod_name = prod.get("product_name") or prod.get("fullName", "?")
        iq = prod.get("ingredient_quality_data", {})
        scorable = iq.get("ingredients_scorable", [])

        cid_map = defaultdict(list)
        for ing in scorable:
            cid = ing.get("canonical_id")
            if cid:
                cid_map[cid].append(ing)

        pt_count_in_prod = 0
        for ing in scorable:
            if ing.get("is_parent_total") is True:
                pt_count_in_prod += 1
                cid = ing.get("canonical_id")
                if cid:
                    pt_cid_freq[cid] += 1

                siblings = cid_map.get(cid, [])
                has_nested = any(
                    s.get("is_nested_ingredient") is True and s is not ing
                    for s in siblings
                )
                if not has_nested:
                    pt_no_nested_child.append((rid, prod_name[:40], cid, ing.get("name")))

                children = [s for s in siblings if s is not ing]
                if children:
                    all_zero = all((s.get("quantity") or 0) == 0 for s in children)
                    if all_zero:
                        pt_children_bad += 1
                        pt_orphan_qty.append((rid, prod_name[:40], cid, ing.get("name"),
                                              ing.get("quantity")))
                    else:
                        pt_children_ok += 1

        if pt_count_in_prod > 0:
            pt_products += 1
            pt_dist[pt_count_in_prod] += 1

    print(f"  Products with >=1 is_parent_total=True: {pt_products}/{n_enrich} ({pct(pt_products, n_enrich)})")
    if pt_dist:
        print(f"  Distribution:")
        for k in sorted(pt_dist):
            print(f"    {k} parent-total{'s' if k>1 else ''}: {pt_dist[k]} products")

    print(f"  Top 10 canonical_ids flagged as parent_total:")
    if pt_cid_freq:
        for cid, cnt in pt_cid_freq.most_common(10):
            print(f"    {cid}: {cnt}")
    else:
        print(f"    (none)")

    if not pt_no_nested_child:
        print(f"  [OK] All parent_total flags have a nested child sibling")
    else:
        print(f"  [WARNING] {len(pt_no_nested_child)} parent_total without nested child:")
        for rid, pname, cid, iname in pt_no_nested_child[:10]:
            print(f"    dsld={rid} ({pname}) cid={cid} ing={iname}")
        if len(pt_no_nested_child) > 10:
            print(f"    ... +{len(pt_no_nested_child)-10} more")

    if not pt_orphan_qty:
        print(f"  [OK] No parent_total=True with all children qty=0 (fix verified)")
    else:
        print(f"  [BUG] {len(pt_orphan_qty)} parent_total where ALL children qty=0:")
        for rid, pname, cid, iname, qty in pt_orphan_qty[:10]:
            print(f"    dsld={rid} ({pname}) cid={cid} ing={iname} parent_qty={qty}")
        if len(pt_orphan_qty) > 10:
            print(f"    ... +{len(pt_orphan_qty)-10} more")

    # ─── CHECK 4: A1=0 Edge Cases ────────────────────────────────────────────
    # A1 lives at the product level in breakdown.A.A1 in scored data.
    # A1=0 on a scored product that has scorable ingredients is the issue.
    print(f"\n--- CHECK 4: A1=0 Edge Cases (product-level, scored data) ---")
    a1_zero_cases = []

    for prod in score_records:
        rid  = prod.get("dsld_id") or prod.get("id", "?")
        name = prod.get("product_name", "?")
        ss   = prod.get("scoring_status", "?")
        if ss not in ("scored",):
            continue

        breakdown = prod.get("breakdown", {})
        a1 = breakdown.get("A", {}).get("A1")
        if a1 == 0:
            # Get scorable ingredient names from match_ledger or enriched
            ml = prod.get("match_ledger", {})
            domains = ml.get("domains", {})
            ing_entries = domains.get("ingredients", {}).get("entries", [])
            scored_ings = [e.get("raw_source_text","?") for e in ing_entries
                           if e.get("decision") == "matched"]
            a1_zero_cases.append({
                "id": rid,
                "name": name[:60],
                "scored_ings": scored_ings[:5],
                "grade": prod.get("grade"),
                "score": prod.get("quality_score"),
            })

    if not a1_zero_cases:
        print(f"  [OK] No scored products with A1=0")
    else:
        print(f"  [WARNING] {len(a1_zero_cases)} scored products with A1=0:")
        # Show first 15
        for c in a1_zero_cases[:15]:
            print(f"    dsld={c['id']} score={c['score']} grade={c['grade']}")
            print(f"      name: {c['name']}")
            print(f"      matched_ings: {c['scored_ings']}")
        if len(a1_zero_cases) > 15:
            print(f"    ... +{len(a1_zero_cases)-15} more")

    # ─── CHECK 5: Scoring Status Breakdown ───────────────────────────────────
    print(f"\n--- CHECK 5: Scoring Status Breakdown ---")
    scoring_status_ctr = Counter()
    verdict_ctr        = Counter()
    grade_ctr          = Counter()

    for prod in score_records:
        scoring_status_ctr[prod.get("scoring_status", "MISSING")] += 1
        verdict_ctr[prod.get("verdict", "MISSING")] += 1
        grade_ctr[prod.get("grade", "MISSING")] += 1

    total = n_score
    print(f"  scoring_status (pipeline disposition):")
    for s in ["scored", "blocked", "not_applicable", "MISSING"]:
        cnt = scoring_status_ctr.get(s, 0)
        if cnt > 0:
            print(f"    {s:16s}: {cnt:5d}  ({pct(cnt,total)})")

    print(f"  verdict (quality verdict):")
    for v in ["SAFE", "CAUTION", "POOR", "UNSAFE", "NOT_SCORED", "MISSING"]:
        cnt = verdict_ctr.get(v, 0)
        if cnt > 0:
            flag = ""
            if brand_name == "Thorne" and v == "SAFE" and cnt < total * 0.88:
                flag = "  [WARNING] Expected ~88%+ SAFE for Thorne"
            print(f"    {v:16s}: {cnt:5d}  ({pct(cnt,total)}){flag}")

    print(f"  grade distribution:")
    for g, cnt in grade_ctr.most_common():
        if cnt > 0:
            print(f"    {str(g):16s}: {cnt:5d}  ({pct(cnt,total)})")

    # ─── CHECK 6: Score Distribution ─────────────────────────────────────────
    print(f"\n--- CHECK 6: Score Distribution (quality_score) ---")
    scores = sorted([
        float(p.get("quality_score"))
        for p in score_records
        if p.get("quality_score") is not None
    ])

    if scores:
        print(f"  n={len(scores)}")
        print(f"  min={scores[0]:.2f}  p25={percentile(scores,25):.2f}  "
              f"p50={percentile(scores,50):.2f}  p75={percentile(scores,75):.2f}  "
              f"max={scores[-1]:.2f}")
        low = [s for s in scores if s == 0]
        hi  = [s for s in scores if s > 100]
        if low:
            print(f"  [WARNING] {len(low)} products with quality_score=0")
        if hi:
            print(f"  [WARNING] {len(hi)} products with quality_score>100")
    else:
        print(f"  [WARNING] No quality_score values found")

    # ─── CHECK 7: Thorne post-fix drift check ────────────────────────────────
    if brand_name == "Thorne":
        print(f"\n--- CHECK 7: Thorne Post-Fix Drift Check ---")
        # For products that have parent_total ingredients, verify A1>0 in scored output
        # Build a set of enriched product IDs that have parent_total
        enriched_pt_ids = set()
        for prod in enrich_records:
            rid = prod.get("dsld_id") or prod.get("id") or prod.get("report_id")
            iq = prod.get("ingredient_quality_data", {})
            for ing in iq.get("ingredients_scorable", []):
                if ing.get("is_parent_total") is True:
                    enriched_pt_ids.add(rid)
                    break

        # Check scored output for those products
        pt_a1_zero = []
        pt_a1_pos  = 0
        for prod in score_records:
            rid = prod.get("dsld_id") or prod.get("id")
            if rid not in enriched_pt_ids:
                continue
            if prod.get("scoring_status") != "scored":
                continue
            a1 = prod.get("breakdown", {}).get("A", {}).get("A1", None)
            if a1 == 0:
                pt_a1_zero.append((rid, prod.get("product_name","?")[:60], a1))
            elif a1 is not None and a1 > 0:
                pt_a1_pos += 1

        print(f"  Products with parent_total in enriched: {len(enriched_pt_ids)}")
        print(f"  Of those with scoring_status=scored: A1>0={pt_a1_pos}, A1=0={len(pt_a1_zero)}")
        if not pt_a1_zero:
            print(f"  [OK] All parent_total products have A1>0 in scored output")
        else:
            print(f"  [BUG] {len(pt_a1_zero)} parent_total products got A1=0:")
            for rid, pname, a1 in pt_a1_zero[:10]:
                print(f"    dsld={rid}: {pname}, A1={a1}")
            if len(pt_a1_zero) > 10:
                print(f"    ... +{len(pt_a1_zero)-10} more")

        # Per-ingredient check using enriched data
        pt_ing_qty_bug = []
        for prod in enrich_records:
            rid = prod.get("dsld_id") or prod.get("id") or prod.get("report_id", "?")
            iq = prod.get("ingredient_quality_data", {})
            scorable = iq.get("ingredients_scorable", [])
            cid_map = defaultdict(list)
            for ing in scorable:
                cid = ing.get("canonical_id")
                if cid:
                    cid_map[cid].append(ing)
            for ing in scorable:
                if ing.get("is_parent_total") is True:
                    parent_qty = ing.get("quantity") or 0
                    cid = ing.get("canonical_id")
                    children = [s for s in cid_map.get(cid, []) if s is not ing]
                    if parent_qty > 0 and children:
                        all_zero = all((s.get("quantity") or 0) == 0 for s in children)
                        if all_zero:
                            pt_ing_qty_bug.append((
                                rid, ing.get("name"), cid, parent_qty,
                                [(s.get("name"), s.get("quantity")) for s in children]
                            ))

        if not pt_ing_qty_bug:
            print(f"  [OK] No parent_total ingredient where qty>0 and all children qty=0")
        else:
            print(f"  [BUG] {len(pt_ing_qty_bug)} ingredients: parent qty>0 but all children qty=0:")
            for rid, name, cid, qty, children in pt_ing_qty_bug[:10]:
                print(f"    dsld={rid}: {name} (cid={cid}) parent_qty={qty}")
                print(f"      children: {children[:3]}")

    # ─── CHECK 8: Form Fallbacks ──────────────────────────────────────────────
    print(f"\n--- CHECK 8: Form Fallbacks (form_unmapped_fallback in enriched) ---")
    fallback_ctr = Counter()
    fallback_forms = Counter()

    for prod in enrich_records:
        iq = prod.get("ingredient_quality_data", {})
        for ing in iq.get("ingredients_scorable", []):
            reason = ing.get("identity_decision_reason", "")
            if reason == "form_unmapped_fallback":
                ing_name = ing.get("name", "?")
                form = ing.get("matched_form") or ing.get("form_id") or "?"
                cid  = ing.get("canonical_id", "?")
                fallback_ctr[(ing_name, cid)] += 1
                fallback_forms[(ing_name, form, cid)] += 1

    total_fb = sum(fallback_ctr.values())
    print(f"  Total form_unmapped_fallback instances: {total_fb}")
    print(f"  Unique (ingredient, canonical_id) pairs: {len(fallback_ctr)}")
    if fallback_ctr:
        print(f"  Top 10 by (ingredient_name, canonical_id):")
        for (ing, cid), cnt in fallback_ctr.most_common(10):
            # Flag suspicious: non-unspecified fallback form
            forms_for_ing = [(f, c) for (n,f,c2), c in fallback_forms.most_common()
                             if n == ing]
            print(f"    {ing!r} → cid={cid}: {cnt} occurrences")

        print(f"\n  Top 10 by (ingredient_name, form, canonical_id):")
        for (ing, form, cid), cnt in fallback_forms.most_common(10):
            flag = ""
            if form and "unspecified" not in form.lower():
                flag = "  ← non-unspecified form"
            print(f"    {ing!r} form={form!r} cid={cid}: {cnt}{flag}")
    else:
        print(f"  [OK] No form_unmapped_fallback instances")

    # ─── CHECK 9: Unmapped Ingredients ───────────────────────────────────────
    print(f"\n--- CHECK 9: Unmapped Actives (mapped=False in ingredients_scorable) ---")
    unmapped_ctr = Counter()
    unmapped_reasons = Counter()

    for prod in enrich_records:
        iq = prod.get("ingredient_quality_data", {})
        for ing in iq.get("ingredients_scorable", []):
            if ing.get("mapped") is False:
                ing_name = ing.get("name", "?")
                reason   = ing.get("identity_decision_reason", "?")
                unmapped_ctr[ing_name] += 1
                unmapped_reasons[reason] += 1

    total_unmapped = sum(unmapped_ctr.values())
    print(f"  Total unmapped instances: {total_unmapped}")
    print(f"  Unique unmapped names: {len(unmapped_ctr)}")
    if unmapped_ctr:
        print(f"  Top 10 by frequency:")
        for name, cnt in unmapped_ctr.most_common(10):
            print(f"    {name!r}: {cnt}")
        print(f"  Reasons breakdown:")
        for reason, cnt in unmapped_reasons.most_common():
            print(f"    {reason!r}: {cnt}")
    else:
        print(f"  [OK] No unmapped actives")

    return {
        "brand": brand_name,
        "n_clean": n_clean, "n_enrich": n_enrich, "n_score": n_score,
        "verdict_ctr": dict(verdict_ctr),
        "scoring_status_ctr": dict(scoring_status_ctr),
        "scores": scores,
        "pt_products": pt_products,
        "a1_zero_count": len(a1_zero_cases),
        "fallback_total": total_fb,
        "unmapped_total": total_unmapped,
    }


def main():
    results = []
    for brand_name, paths in BRANDS.items():
        try:
            r = audit_brand(brand_name, paths)
            results.append(r)
        except Exception as e:
            import traceback
            print(f"\n[ERROR] Audit failed for {brand_name}: {e}")
            traceback.print_exc()

    # ─── Cross-brand summary ──────────────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print(f"CROSS-BRAND SUMMARY")
    print(f"{'='*80}")
    header = (f"{'Brand':<20} {'Clean':>6} {'Enrich':>7} {'Score':>6} "
              f"{'Counts':>8} {'SAFE%':>7} {'UNSAFE%':>8} "
              f"{'p50':>7} {'A1=0':>6} {'PT_prods':>9} {'FB':>6} {'Unmapped':>9}")
    print(header)
    print("-" * len(header))
    for r in results:
        total   = r["n_score"]
        safe    = r["verdict_ctr"].get("SAFE", 0)
        unsafe  = r["verdict_ctr"].get("UNSAFE", 0)
        safe_p  = f"{100*safe/total:.1f}%" if total else "N/A"
        unsafe_p= f"{100*unsafe/total:.1f}%" if total else "N/A"
        p50     = f"{percentile(r['scores'],50):.1f}" if r["scores"] else "N/A"
        counts_ok = "OK" if r["n_clean"]==r["n_enrich"]==r["n_score"] else "MISMATCH"
        print(f"  {r['brand']:<18} {r['n_clean']:>6} {r['n_enrich']:>7} {r['n_score']:>6} "
              f"  {counts_ok:>8} {safe_p:>7} {unsafe_p:>8} "
              f"{p50:>7} {r['a1_zero_count']:>6} {r['pt_products']:>9} "
              f"{r['fallback_total']:>6} {r['unmapped_total']:>9}")

    print(f"\nAudit complete.")


if __name__ == "__main__":
    main()
