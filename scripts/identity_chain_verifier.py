#!/usr/bin/env python3
"""
Ingredient Identity Chain Verification
=======================================
Verifies that ingredient data is preserved faithfully across
the DSLD pipeline: Cleaning -> Enrichment -> Scoring.

Checks performed per product:
  a. INGREDIENT COUNT preserved (cleaned == enriched)
  b. NO SILENT DROPS (every cleaned ingredient appears in enriched)
  c. DOSAGE preserved (quantity + unit match)
  d. FORM INFO preserved (standardName survives)
  e. UNMATCHED tracked (unmatched ingredients explicitly listed)
  f. MATCH LEDGER counts (total_raw matches actual ingredient count)
"""

import json
import sys
from pathlib import Path
from collections import OrderedDict

# ── Configuration ─────────────────────────────────────────────────────────

BASE = Path(__file__).resolve().parent

CLEANED_FILES = [
    BASE / "output_Lozenges/cleaned/cleaned_batch_1.json",
    BASE / "output_Lozenges/cleaned/cleaned_batch_2.json",
]
ENRICHED_FILES = [
    BASE / "output_Lozenges_enriched/enriched/enriched_cleaned_batch_1.json",
    BASE / "output_Lozenges_enriched/enriched/enriched_cleaned_batch_2.json",
]
SCORED_FILES = [
    BASE / "output_Lozenges_scored/scored/scored_cleaned_batch_1.json",
    BASE / "output_Lozenges_scored/scored/scored_cleaned_batch_2.json",
]

TARGET_IDS = ["10042", "10997", "14382", "12821", "201241", "201871",
              "10190", "14200", "13946", "12465"]

PRODUCT_CATEGORIES = {
    "10042": "SIMPLE", "10997": "SIMPLE",
    "14382": "MEDIUM", "12821": "MEDIUM",
    "201241": "BLEND", "201871": "BLEND",
    "10190": "EDGE (banned+unmatched)", "14200": "EDGE (unmatched+allergens)",
    "13946": "EDGE (probiotic/allergen-heavy)", "12465": "EDGE (allergen-heavy)",
}


# ── Helpers ───────────────────────────────────────────────────────────────

def load_products(file_list, id_field_primary, id_field_fallback=None):
    """Load products from JSON files, index by string ID."""
    products = {}
    for fpath in file_list:
        if not fpath.exists():
            continue
        with open(fpath) as f:
            data = json.load(f)
        for p in data:
            pid = str(p.get(id_field_primary) or p.get(id_field_fallback) or "")
            if pid in TARGET_IDS:
                products[pid] = p
    return products


def extract_ingredient_key(ing):
    """Create a stable lookup key for an ingredient."""
    name = (ing.get("name") or ing.get("raw_source_text") or "").strip().lower()
    return name


def extract_ingredient_info(ing):
    """Extract the fields we care about from an ingredient dict."""
    return {
        "name": ing.get("name", ""),
        "raw_source_text": ing.get("raw_source_text", ""),
        "standardName": ing.get("standardName", ""),
        "quantity": ing.get("quantity"),
        "unit": ing.get("unit", ""),
        "mapped": ing.get("mapped"),
        "normalized_key": ing.get("normalized_key", ""),
        "ingredientGroup": ing.get("ingredientGroup", ""),
        "forms": ing.get("forms", []),
        "proprietaryBlend": ing.get("proprietaryBlend"),
        "nestedIngredients": ing.get("nestedIngredients", []),
        "source_path": ing.get("raw_source_path", ""),
    }


# ── Per-product verification ─────────────────────────────────────────────

def verify_product(pid, cleaned, enriched, scored):
    """Run all verification checks for one product across stages."""
    result = OrderedDict()
    result["dsld_id"] = pid
    result["category"] = PRODUCT_CATEGORIES.get(pid, "UNKNOWN")
    issues = []

    # ── CLEANED stage ─────────────────────────────────────────────────
    c_name = cleaned.get("fullName", "(no fullName)")
    c_active = cleaned.get("activeIngredients", [])
    c_inactive = cleaned.get("inactiveIngredients", [])
    c_active_count = len(c_active)
    c_inactive_count = len(c_inactive)
    c_total = c_active_count + c_inactive_count

    result["cleaned"] = {
        "product_name": c_name,
        "active_count": c_active_count,
        "inactive_count": c_inactive_count,
        "total_ingredients": c_total,
        "active_ingredients": [],
        "inactive_ingredients": [],
    }
    for ing in c_active:
        info = extract_ingredient_info(ing)
        result["cleaned"]["active_ingredients"].append(info)
    for ing in c_inactive:
        info = extract_ingredient_info(ing)
        result["cleaned"]["inactive_ingredients"].append(info)

    # ── ENRICHED stage ────────────────────────────────────────────────
    e_name = enriched.get("product_name", "(no name)")
    e_active = enriched.get("activeIngredients", [])
    e_inactive = enriched.get("inactiveIngredients", [])
    e_active_count = len(e_active)
    e_inactive_count = len(e_inactive)
    e_total = e_active_count + e_inactive_count

    result["enriched"] = {
        "product_name": e_name,
        "active_count": e_active_count,
        "inactive_count": e_inactive_count,
        "total_ingredients": e_total,
        "active_ingredients": [],
        "inactive_ingredients": [],
    }
    for ing in e_active:
        info = extract_ingredient_info(ing)
        result["enriched"]["active_ingredients"].append(info)
    for ing in e_inactive:
        info = extract_ingredient_info(ing)
        result["enriched"]["inactive_ingredients"].append(info)

    # Enrichment-specific fields
    iqd = enriched.get("ingredient_quality_data", {})
    iqd_ingredients = iqd.get("ingredients", [])
    unmatched_list = enriched.get("unmatched_ingredients", [])
    contaminant = enriched.get("contaminant_data", {})
    match_ledger = enriched.get("match_ledger", {})

    result["enriched"]["ingredient_quality_data_count"] = len(iqd_ingredients)
    result["enriched"]["iqd_scorable"] = iqd.get("ingredients_scorable", "N/A")
    result["enriched"]["iqd_skipped"] = iqd.get("ingredients_skipped", "N/A")
    result["enriched"]["iqd_total_active"] = iqd.get("total_active", "N/A")
    result["enriched"]["iqd_unmapped_count"] = iqd.get("unmapped_count", "N/A")
    result["enriched"]["iqd_blend_header_rows"] = iqd.get("blend_header_rows", 0)
    result["enriched"]["iqd_total_records_seen"] = iqd.get("total_records_seen", "N/A")
    result["enriched"]["iqd_promoted_from_inactive"] = iqd.get("promoted_from_inactive", 0)
    result["enriched"]["unmatched_ingredients"] = unmatched_list

    # Contaminant data
    banned = contaminant.get("banned_substances", {})
    harmful = contaminant.get("harmful_additives", {})
    allergens = contaminant.get("allergens", {})
    result["enriched"]["contaminant_data"] = {
        "banned_found": banned.get("found", False),
        "banned_substances": [s.get("substance_name", s.get("ingredient", "")) for s in banned.get("substances", [])],
        "harmful_found": harmful.get("found", False),
        "harmful_additives": [a.get("additive_name", a.get("ingredient", "")) for a in harmful.get("additives", [])],
        "allergens_found": allergens.get("found", False),
        "allergens_list": [a.get("allergen_name", a.get("allergen", "")) for a in allergens.get("allergens", [])],
    }

    # Match ledger
    ml_domains = match_ledger.get("domains", {})
    ml_ing = ml_domains.get("ingredients", {})
    ml_entries = ml_ing.get("entries", [])
    result["enriched"]["match_ledger"] = {
        "total_raw": ml_ing.get("total_raw"),
        "matched": ml_ing.get("matched"),
        "unmatched": ml_ing.get("unmatched"),
        "rejected": ml_ing.get("rejected"),
        "skipped": ml_ing.get("skipped"),
        "recognized_non_scorable": ml_ing.get("recognized_non_scorable", 0),
        "recognition_coverage_percent": ml_ing.get("recognition_coverage_percent"),
        "scorable_coverage_percent": ml_ing.get("scorable_coverage_percent"),
        "entry_count": len(ml_entries),
        "domains_present": list(ml_domains.keys()),
    }

    # ── SCORED stage ──────────────────────────────────────────────────
    if scored:
        result["scored"] = {
            "dsld_id": scored.get("dsld_id"),
            "product_name": scored.get("product_name"),
            "score_80": scored.get("score_80"),
            "score_100": scored.get("score_100_equivalent"),
            "grade": scored.get("grade"),
            "verdict": scored.get("verdict"),
            "safety_verdict": scored.get("safety_verdict"),
            "scoring_status": scored.get("scoring_status"),
            "score_basis": scored.get("score_basis"),
            "mapped_coverage": scored.get("mapped_coverage"),
            "section_scores": scored.get("section_scores", {}),
            "breakdown_sections": list(scored.get("breakdown", {}).keys()) if scored.get("breakdown") else [],
            "flags": scored.get("flags", []),
            "unmapped_actives": scored.get("unmapped_actives", []),
        }
    else:
        result["scored"] = None

    # ── VERIFICATION CHECKS ──────────────────────────────────────────

    # (a) INGREDIENT COUNT preserved
    if c_active_count != e_active_count:
        issues.append(
            f"[COUNT-ACTIVE] Cleaned active={c_active_count} vs Enriched active={e_active_count} "
            f"(delta={e_active_count - c_active_count})"
        )
    if c_inactive_count != e_inactive_count:
        issues.append(
            f"[COUNT-INACTIVE] Cleaned inactive={c_inactive_count} vs Enriched inactive={e_inactive_count} "
            f"(delta={e_inactive_count - c_inactive_count})"
        )

    # (b) NO SILENT DROPS -- every cleaned ingredient must appear in enriched
    c_all = [(extract_ingredient_key(i), "active", i) for i in c_active] + \
            [(extract_ingredient_key(i), "inactive", i) for i in c_inactive]
    e_all_keys = set()
    for i in e_active + e_inactive:
        e_all_keys.add(extract_ingredient_key(i))

    dropped = []
    for key, src, ing in c_all:
        if key and key not in e_all_keys:
            dropped.append(f"{ing.get('name','')} (from {src})")
    if dropped:
        issues.append(f"[SILENT-DROP] {len(dropped)} ingredient(s) in cleaned but missing from enriched: {dropped}")

    # (c) DOSAGE preserved -- quantity and unit must match
    c_ing_map = {}
    for ing in c_active + c_inactive:
        key = extract_ingredient_key(ing)
        if key:
            c_ing_map[key] = ing

    dosage_mismatches = []
    for ing in e_active + e_inactive:
        key = extract_ingredient_key(ing)
        if key in c_ing_map:
            c_ing = c_ing_map[key]
            c_qty = c_ing.get("quantity")
            e_qty = ing.get("quantity")
            c_unit = (c_ing.get("unit") or "").strip()
            e_unit = (ing.get("unit") or "").strip()
            if c_qty != e_qty or c_unit != e_unit:
                dosage_mismatches.append(
                    f"{ing.get('name','')}: cleaned={c_qty} {c_unit} vs enriched={e_qty} {e_unit}"
                )
    if dosage_mismatches:
        issues.append(f"[DOSAGE-MISMATCH] {len(dosage_mismatches)} ingredient(s): {dosage_mismatches}")

    # (d) FORM INFO preserved -- standardName must survive
    form_lost = []
    for ing in e_active + e_inactive:
        key = extract_ingredient_key(ing)
        if key in c_ing_map:
            c_std = (c_ing_map[key].get("standardName") or "").strip()
            e_std = (ing.get("standardName") or "").strip()
            if c_std and not e_std:
                form_lost.append(f"{ing.get('name','')}: cleaned had standardName='{c_std}', enriched has none")
            elif c_std and e_std and c_std != e_std:
                form_lost.append(
                    f"{ing.get('name','')}: standardName changed '{c_std}' -> '{e_std}'"
                )
    if form_lost:
        issues.append(f"[FORM-CHANGE] {len(form_lost)} ingredient(s): {form_lost}")

    # (e) UNMATCHED tracked -- any unmapped ingredients should appear in unmatched_ingredients list
    unmapped_in_enriched = []
    for ing in e_active + e_inactive:
        if ing.get("mapped") is False:
            unmapped_in_enriched.append(ing.get("name", ""))

    unmatched_names_in_list = set()
    for u in unmatched_list:
        if isinstance(u, dict):
            unmatched_names_in_list.add((u.get("name") or u.get("raw_source_text") or "").strip().lower())
        elif isinstance(u, str):
            unmatched_names_in_list.add(u.strip().lower())

    untracked_unmapped = []
    for name in unmapped_in_enriched:
        if name.strip().lower() not in unmatched_names_in_list:
            untracked_unmapped.append(name)

    if untracked_unmapped:
        issues.append(
            f"[UNMATCHED-UNTRACKED] {len(untracked_unmapped)} unmapped ingredient(s) not in "
            f"unmatched_ingredients list: {untracked_unmapped}"
        )

    # (f) MATCH LEDGER counts -- total_raw should match actual scorable ingredient count
    ml_total_raw = ml_ing.get("total_raw", 0)
    # total_raw counts active ingredients that are scorable (not blend headers)
    # Compare with iqd total_records_seen which is the authoritative count
    iqd_total_records = iqd.get("total_records_seen", None)
    iqd_total_active = iqd.get("total_active", None)

    # The match_ledger total_raw should equal the number of match_ledger entries
    ml_entry_count = len(ml_entries)
    if ml_total_raw != ml_entry_count:
        issues.append(
            f"[LEDGER-ENTRY-MISMATCH] match_ledger total_raw={ml_total_raw} but "
            f"actual entry count={ml_entry_count}"
        )

    # Verify matched + unmatched + rejected + skipped = total_raw
    ml_matched = ml_ing.get("matched", 0)
    ml_unmatched = ml_ing.get("unmatched", 0)
    ml_rejected = ml_ing.get("rejected", 0)
    ml_skipped = ml_ing.get("skipped", 0)
    ml_sum = ml_matched + ml_unmatched + ml_rejected + ml_skipped
    if ml_sum != ml_total_raw:
        issues.append(
            f"[LEDGER-ARITHMETIC] matched({ml_matched})+unmatched({ml_unmatched})"
            f"+rejected({ml_rejected})+skipped({ml_skipped})={ml_sum} != total_raw({ml_total_raw})"
        )

    # Cross-check: IQD total_active vs cleaned active count
    if iqd_total_active is not None and iqd_total_active != c_active_count:
        # This may be OK if blend headers are excluded or inactive promoted
        blend_headers = iqd.get("blend_header_rows", 0)
        promoted = iqd.get("promoted_from_inactive", 0)
        expected = c_active_count - blend_headers + promoted
        if iqd_total_active != expected:
            issues.append(
                f"[IQD-ACTIVE-MISMATCH] iqd.total_active={iqd_total_active} vs "
                f"cleaned active={c_active_count} (blend_headers={blend_headers}, promoted={promoted}, "
                f"expected={expected})"
            )

    result["issues"] = issues
    result["issue_count"] = len(issues)
    result["status"] = "PASS" if len(issues) == 0 else "FAIL"

    return result


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 90)
    print("  DSLD INGREDIENT IDENTITY CHAIN VERIFICATION")
    print("  Pipeline: Cleaning -> Enrichment -> Scoring")
    print("=" * 90)
    print()

    # Load all three stages
    cleaned_products = load_products(CLEANED_FILES, "id", "dsld_id")
    enriched_products = load_products(ENRICHED_FILES, "dsld_id", "id")
    scored_products = load_products(SCORED_FILES, "dsld_id", "id")

    print(f"Loaded: {len(cleaned_products)} cleaned, {len(enriched_products)} enriched, "
          f"{len(scored_products)} scored products (of {len(TARGET_IDS)} targets)")
    print()

    results = []
    total_issues = 0
    pass_count = 0
    fail_count = 0

    for pid in TARGET_IDS:
        cleaned = cleaned_products.get(pid)
        enriched = enriched_products.get(pid)
        scored = scored_products.get(pid)

        if not cleaned:
            print(f"[ERROR] Product {pid} not found in cleaned data!")
            continue
        if not enriched:
            print(f"[ERROR] Product {pid} not found in enriched data!")
            continue

        result = verify_product(pid, cleaned, enriched, scored)
        results.append(result)
        total_issues += result["issue_count"]
        if result["status"] == "PASS":
            pass_count += 1
        else:
            fail_count += 1

    # ── Print report ──────────────────────────────────────────────────
    for r in results:
        pid = r["dsld_id"]
        cat = r["category"]
        status = r["status"]
        status_marker = "PASS" if status == "PASS" else "FAIL"

        print("=" * 90)
        print(f"  [{status_marker}] Product {pid} -- {cat}")
        print(f"  Name: {r['cleaned']['product_name']}")
        print("=" * 90)

        # CLEANED
        c = r["cleaned"]
        print(f"\n  STAGE 1: CLEANED")
        print(f"    Active ingredients:   {c['active_count']}")
        print(f"    Inactive ingredients: {c['inactive_count']}")
        print(f"    Total:                {c['total_ingredients']}")
        print(f"    ---- Active Ingredients Detail ----")
        for i, ing in enumerate(c["active_ingredients"], 1):
            name = ing["name"]
            std = ing["standardName"] or "(none)"
            qty = ing["quantity"]
            unit = ing["unit"] or "(none)"
            mapped = ing["mapped"]
            blend = ing.get("proprietaryBlend")
            nested = ing.get("nestedIngredients", [])
            blend_str = f" [BLEND, {len(nested)} nested]" if blend else ""
            print(f"      {i}. {name}  |  std={std}  |  {qty} {unit}  |  mapped={mapped}{blend_str}")
        if c["inactive_ingredients"]:
            print(f"    ---- Inactive Ingredients Detail ----")
            for i, ing in enumerate(c["inactive_ingredients"], 1):
                name = ing["name"]
                std = ing["standardName"] or "(none)"
                mapped = ing["mapped"]
                print(f"      {i}. {name}  |  std={std}  |  mapped={mapped}")

        # ENRICHED
        e = r["enriched"]
        print(f"\n  STAGE 2: ENRICHED")
        print(f"    Active ingredients:   {e['active_count']}")
        print(f"    Inactive ingredients: {e['inactive_count']}")
        print(f"    Total:                {e['total_ingredients']}")
        print(f"    IQD ingredients evaluated:       {e['ingredient_quality_data_count']}")
        print(f"    IQD total_active:                {e['iqd_total_active']}")
        print(f"    IQD scorable/skipped:            {e['iqd_scorable']}/{e['iqd_skipped']}")
        print(f"    IQD unmapped_count:              {e['iqd_unmapped_count']}")
        print(f"    IQD blend_header_rows:           {e['iqd_blend_header_rows']}")
        print(f"    IQD total_records_seen:          {e['iqd_total_records_seen']}")
        print(f"    IQD promoted_from_inactive:      {e['iqd_promoted_from_inactive']}")
        print(f"    ---- Active Ingredients Detail ----")
        for i, ing in enumerate(e["active_ingredients"], 1):
            name = ing["name"]
            std = ing["standardName"] or "(none)"
            qty = ing["quantity"]
            unit = ing["unit"] or "(none)"
            mapped = ing["mapped"]
            print(f"      {i}. {name}  |  std={std}  |  {qty} {unit}  |  mapped={mapped}")

        # Unmatched
        if e["unmatched_ingredients"]:
            print(f"    ---- Unmatched Ingredients ({len(e['unmatched_ingredients'])}) ----")
            for u in e["unmatched_ingredients"]:
                if isinstance(u, dict):
                    print(f"      - {u.get('name', u.get('raw_source_text','?'))} "
                          f"(source={u.get('raw_source_path','?')}, reason={u.get('reason','?')})")
                else:
                    print(f"      - {u}")
        else:
            print(f"    ---- Unmatched Ingredients: (none) ----")

        # Contaminant data
        cd = e["contaminant_data"]
        print(f"    ---- Contaminant Data ----")
        print(f"      Banned:    found={cd['banned_found']}  {cd['banned_substances'] if cd['banned_substances'] else ''}")
        print(f"      Harmful:   found={cd['harmful_found']}  {cd['harmful_additives'] if cd['harmful_additives'] else ''}")
        print(f"      Allergens: found={cd['allergens_found']}  {cd['allergens_list'] if cd['allergens_list'] else ''}")

        # Match ledger
        ml = e["match_ledger"]
        print(f"    ---- Match Ledger (ingredients domain) ----")
        print(f"      total_raw={ml['total_raw']}  matched={ml['matched']}  "
              f"unmatched={ml['unmatched']}  rejected={ml['rejected']}  skipped={ml['skipped']}")
        print(f"      recognized_non_scorable={ml['recognized_non_scorable']}")
        print(f"      recognition_coverage={ml['recognition_coverage_percent']}%  "
              f"scorable_coverage={ml['scorable_coverage_percent']}%")
        print(f"      entry_count={ml['entry_count']}  domains_present={ml['domains_present']}")

        # SCORED
        if r["scored"]:
            s = r["scored"]
            print(f"\n  STAGE 3: SCORED")
            print(f"    dsld_id:         {s['dsld_id']}")
            print(f"    product_name:    {s['product_name']}")
            print(f"    score_80:        {s['score_80']}")
            print(f"    score_100:       {s['score_100']}")
            print(f"    grade:           {s['grade']}")
            print(f"    verdict:         {s['verdict']}")
            print(f"    safety_verdict:  {s['safety_verdict']}")
            print(f"    scoring_status:  {s['scoring_status']}")
            print(f"    score_basis:     {s['score_basis']}")
            print(f"    mapped_coverage: {s['mapped_coverage']}")
            print(f"    flags:           {s['flags']}")
            print(f"    unmapped_actives:{s['unmapped_actives']}")
            ss = s.get("section_scores", {})
            if ss:
                print(f"    ---- Section Scores ----")
                for section, scores in ss.items():
                    print(f"      {section}: {scores.get('score','?')}/{scores.get('max','?')}")
            bd = s.get("breakdown_sections", [])
            if bd:
                print(f"    ---- Breakdown Sections: {bd} ----")
        else:
            print(f"\n  STAGE 3: SCORED -- NOT AVAILABLE")

        # Issues
        print(f"\n  VERIFICATION RESULT: {status_marker}")
        if r["issues"]:
            for iss in r["issues"]:
                print(f"    >> {iss}")
        else:
            print(f"    All checks passed.")
        print()

    # ── Summary ───────────────────────────────────────────────────────
    print("=" * 90)
    print("  VERIFICATION SUMMARY")
    print("=" * 90)
    print(f"  Products verified: {len(results)}/{len(TARGET_IDS)}")
    print(f"  PASS: {pass_count}    FAIL: {fail_count}")
    print(f"  Total issues found: {total_issues}")
    print()

    # Group issues by type
    issue_types = {}
    for r in results:
        for iss in r["issues"]:
            tag = iss.split("]")[0].replace("[", "")
            issue_types.setdefault(tag, []).append(r["dsld_id"])
    if issue_types:
        print("  Issues by type:")
        for tag, pids in sorted(issue_types.items()):
            print(f"    {tag}: {len(pids)} product(s) -> {pids}")
    print()

    # Per-product summary table
    print(f"  {'ID':<10} {'Category':<30} {'C_Act':>5} {'C_Ina':>5} {'E_Act':>5} {'E_Ina':>5} "
          f"{'ML_raw':>6} {'Score':>6} {'Verdict':<10} {'Status':<6}")
    print(f"  {'-'*8:<10} {'-'*28:<30} {'-'*5:>5} {'-'*5:>5} {'-'*5:>5} {'-'*5:>5} "
          f"{'-'*6:>6} {'-'*6:>6} {'-'*8:<10} {'-'*4:<6}")
    for r in results:
        c = r["cleaned"]
        e = r["enriched"]
        ml = e["match_ledger"]
        s = r.get("scored") or {}
        score = s.get("score_80", "N/A")
        verdict = s.get("verdict", "N/A")
        print(f"  {r['dsld_id']:<10} {r['category']:<30} {c['active_count']:>5} {c['inactive_count']:>5} "
              f"{e['active_count']:>5} {e['inactive_count']:>5} "
              f"{ml['total_raw'] or 'N/A':>6} {score if score is not None else 'N/A':>6} "
              f"{verdict:<10} {r['status']:<6}")

    print()
    print("=" * 90)
    if fail_count > 0:
        print(f"  RESULT: {fail_count} product(s) have identity chain issues. See details above.")
    else:
        print(f"  RESULT: All {pass_count} products passed identity chain verification.")
    print("=" * 90)

    # Write JSON report
    report_path = BASE / "reports" / "identity_chain_verification.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  JSON report written to: {report_path}")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
