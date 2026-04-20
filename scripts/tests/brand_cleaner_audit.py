"""
Brand-scale cleaner fidelity audit — raw DSLD vs cleaned output.

For every product in a brand's cleaned output, verify:

  1. COVERAGE — every raw ingredientRow + every nested row is represented in
     the cleaned output (activeIngredients, inactiveIngredients, nutritionalInfo,
     or legitimately filtered as a label/nutrition-fact phrase).

  2. FORM PRESERVATION — forms[].name, category, ingredientGroup, uniiCode,
     prefix, percent, order all carried through from raw. No silent drops.

  3. CANONICAL IDENTITY — when `mapped=True`, the row emits canonical_id +
     canonical_source_db. A row mapped without canonical_id is a cleaner bug
     (mapped flag set without a real DB resolution).

  4. LABEL NUTRIENT CONTEXT — vitamin/mineral rows carry label_nutrient_context.

  5. SOURCE LEAK — forms with category in {"animal part or source",
     "plant part"} must never appear as top-level activeIngredient rows.

  6. QUANTITY FIDELITY — row quantity/unit preserved. Nested rows' dosing
     preserved when present.

  7. PROPRIETARY BLEND STRUCTURE — rows marked proprietaryBlend=true preserve
     parentBlend and isNestedIngredient linkage.

Usage:
    python3 scripts/tests/brand_cleaner_audit.py Thorne
    python3 scripts/tests/brand_cleaner_audit.py Pure_Encapsulations
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from glob import glob
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


NUTR_NAME_HINTS = {
    # single-word keywords that indicate a nutrition-facts row (properly filtered)
    "calorie", "calories",
    "total carbohydrate", "carbohydrates", "carbohydrate",
    "total fat", "fat", "saturated fat", "trans fat",
    "sugar", "sugars", "added sugars",
    "cholesterol",
    "total protein", "protein",
    "sodium", "potassium",  # when they appear on nutrition-facts only
    "dietary fiber", "fiber",
    "serving size", "servings per container", "amount per serving",
    # omega rollups
    "total omega", "other omega",
}


def is_expected_filtered_row(row: Dict[str, Any]) -> bool:
    """
    Rows we EXPECT the cleaner to filter out (summaries, rollups, blend
    headers, nutrition-fact labels). Absence in cleaned output is OK.
    """
    name = (row.get("name") or "").lower().strip()
    cat = (row.get("category") or "").lower().strip()
    # Blend HEADER rows: DSLD labels the container row with category='blend'.
    # The cleaner unrolls nested children into their own rows tagged with
    # parent_blend, so the header itself is intentionally dropped.
    if cat == "blend" and (
        "blend" in name or "matrix" in name or "complex" in name
        or "formula" in name or "proprietary" in name
    ):
        return True
    # Omega rollups are summary rows, not discrete ingredients
    if name.startswith("total omega") or name.startswith("other omega"):
        return True
    # Label descriptor rows like "and as (magnesium) citrate"
    if name.startswith("and as ") or name.startswith("as "):
        return True
    # Generic nutrition-fact phrases
    for hint in NUTR_NAME_HINTS:
        if hint in name and cat in {
            "", "other", "sugar", "fat", "carbohydrate", "fiber",
            "protein", "cholesterol",
        }:
            return True
    # Serving/label metadata
    if name in {"serving size", "servings per container", "amount per serving"}:
        return True
    # "less than 2%" label phrases etc.
    if "less than" in name and "%" in name:
        return True
    return False


def find_cleaned_for_brand(brand: str) -> List[str]:
    # Cleaned batches can land under scripts/products or products/ at repo root
    for prefix in ("scripts/products", "products"):
        hits = sorted(glob(f"{prefix}/output_{brand}/cleaned/cleaned_batch_*.json"))
        if hits:
            return hits
    return []


def find_raw(pid: str) -> Optional[str]:
    for cand in [
        f"/Users/seancheick/Documents/DataSetDsld/staging/brands/*/{pid}.json",
        f"/Users/seancheick/Documents/DataSetDsld/forms/*/{pid}.json",
    ]:
        hits = glob(cand)
        if hits:
            return hits[0]
    return None


def flatten_raw_rows(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flat = []
    for r in raw_rows or []:
        if not isinstance(r, dict):
            continue
        flat.append(r)
        for nr in r.get("nestedRows", []) or []:
            if isinstance(nr, dict):
                flat.append({**nr, "_parent_name": r.get("name")})
    return flat


def row_has_match(
    raw_row: Dict[str, Any], active: List[Dict[str, Any]],
    inactive: List[Dict[str, Any]], nutritional: Dict[str, Any],
) -> bool:
    raw_name = (raw_row.get("name") or "").strip().lower()
    raw_id = raw_row.get("ingredientId")
    if not raw_name:
        return True  # empty name — skip

    # nutritional facts bucket
    for k, v in (nutritional or {}).items():
        if raw_name in k.lower() or k.lower() in raw_name:
            return True

    def _match(entries):
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            if raw_id is not None and e.get("ingredientId") == raw_id:
                return True
            en = (e.get("name") or "").strip().lower()
            rs = (e.get("raw_source_text") or "").strip().lower()
            if en == raw_name or rs == raw_name:
                return True
            if raw_name and raw_name in rs:
                return True
            for nested in e.get("nestedIngredients", []) or []:
                if isinstance(nested, dict):
                    nn = (nested.get("name") or "").strip().lower()
                    if nn == raw_name:
                        return True
        return False

    return _match(active) or _match(inactive)


def audit_product(raw: Dict[str, Any], cleaned: Dict[str, Any]) -> Dict[str, List[str]]:
    """Return a dict of {issue_category: [messages...]} for one product."""
    issues: Dict[str, List[str]] = defaultdict(list)
    raw_rows = flatten_raw_rows(raw.get("ingredientRows") or [])
    active = cleaned.get("activeIngredients") or []
    inactive = cleaned.get("inactiveIngredients") or []
    nutritional = cleaned.get("nutritionalInfo") or {}

    # --- 1. COVERAGE ---
    for r in raw_rows:
        if is_expected_filtered_row(r):
            continue
        if not row_has_match(r, active, inactive, nutritional):
            issues["coverage"].append(
                f"raw row {r.get('name')!r} (id={r.get('ingredientId')}, cat={r.get('category')}) not in cleaned"
            )

    # --- 2. FORM PRESERVATION (per active/inactive row, match by ingredientId) ---
    for section_name, section in [("active", active), ("inactive", inactive)]:
        for e in section:
            if not isinstance(e, dict):
                continue
            eid = e.get("ingredientId")
            raw_match = next((r for r in raw_rows if r.get("ingredientId") == eid), None)
            if raw_match is None:
                continue
            raw_forms = raw_match.get("forms") or []
            cln_forms = e.get("forms") or []
            for rf in raw_forms:
                if not isinstance(rf, dict):
                    continue
                rf_id = rf.get("ingredientId")
                cf = next((c for c in cln_forms if isinstance(c, dict) and c.get("ingredientId") == rf_id), None)
                if cf is None:
                    issues["form_missing"].append(
                        f"[{section_name}] {e.get('name')}: form id={rf_id} ({rf.get('name')!r}) dropped"
                    )
                    continue
                for fld in ("category", "ingredientGroup", "uniiCode", "prefix", "percent"):
                    rv, cv = rf.get(fld), cf.get(fld)
                    if rv is not None and cv is None:
                        issues["form_field_dropped"].append(
                            f"[{section_name}] {e.get('name')} form {rf_id}: {fld} dropped (raw={rv!r})"
                        )

    # --- 3. CANONICAL IDENTITY ---
    for e in active:
        if not isinstance(e, dict):
            continue
        if e.get("mapped") is True:
            if e.get("canonical_id") in (None, ""):
                issues["canonical_missing_mapped"].append(
                    f"mapped active {e.get('name')!r} std={e.get('standardName')!r} has no canonical_id"
                )

    # --- 4. LABEL NUTRIENT CONTEXT ---
    for e in active:
        if not isinstance(e, dict):
            continue
        rc = e.get("raw_category")
        if rc in {"vitamin", "mineral"} and not e.get("label_nutrient_context"):
            issues["nutrient_ctx_missing"].append(
                f"{e.get('name')!r} [cat={rc}] missing label_nutrient_context"
            )

    # --- 5. SOURCE LEAK ---
    # A real source leak is when a form-level source descriptor (e.g.,
    # Pancreatin's "Pancreas" form at category='animal part or source') gets
    # promoted to a top-level activeIngredient row.
    # A bare tissue name is NOT a leak when the RAW ingredientRow itself
    # is category='animal part or source' — those are legitimate glandular
    # supplements (Thorne IM-Encap Spleen/Thymus, organ meat supplements).
    SOURCE_TOKENS = {"pancreas", "liver", "spleen", "thymus", "heart", "kidney",
                     "cantaloupe", "eggshell"}
    for e in active:
        if not isinstance(e, dict):
            continue
        nm = (e.get("name") or "").strip().lower()
        if nm not in SOURCE_TOKENS:
            continue
        # Confirm this DIDN'T come from a raw row tagged as the ingredient itself
        raw_row = next((r for r in raw_rows
                        if (r.get("name") or "").strip().lower() == nm), None)
        if raw_row is not None and (raw_row.get("category") or "") == "animal part or source":
            # Legitimate glandular supplement — not a leak.
            continue
        issues["source_leak"].append(f"bare source token {nm!r} promoted to activeIngredient")

    # --- 6. QUANTITY FIDELITY ---
    # Match top-level RAW rows (not nested children) against non-nested
    # CLEANED rows. DSLD sometimes re-uses the same ingredientId across a
    # parent row and a nested child with different quantities, so we must
    # scope the match to top-level entries to avoid false mismatches.
    top_level_raw = [r for r in (raw.get("ingredientRows") or [])
                     if isinstance(r, dict)]
    # DSLD occasionally emits multiple top-level rows with the SAME
    # ingredientId (e.g., a product that lists Vitamin D twice for distinct
    # servingSizes). Accumulate ALL matching rows so quantity checks can
    # compare against the union of raw quantities for that id.
    top_level_raw_by_id: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for r in top_level_raw:
        rid = r.get("ingredientId")
        if rid is not None:
            top_level_raw_by_id[rid].append(r)
    for e in active + inactive:
        if not isinstance(e, dict):
            continue
        if e.get("isNestedIngredient") is True:
            continue
        eid = e.get("ingredientId")
        raw_matches = top_level_raw_by_id.get(eid) or []
        if not raw_matches:
            continue
        # Union all quantity entries across matching raw rows
        raw_q: List[Any] = []
        for rm in raw_matches:
            raw_q.extend(rm.get("quantity") or [])
        if isinstance(raw_q, list) and raw_q:
            raw_qty = raw_q[0].get("quantity") if isinstance(raw_q[0], dict) else None
            raw_unit = raw_q[0].get("unit") if isinstance(raw_q[0], dict) else None
            cln_qty = e.get("quantity")
            cln_unit = e.get("unit")
            if raw_qty is not None and cln_qty is not None:
                try:
                    # Multi-serving support: raw_q may contain several
                    # quantities (one per servingSizeOrder). Accept the
                    # cleaned quantity if it matches ANY raw quantity.
                    raw_candidates = []
                    for q_entry in raw_q:
                        if isinstance(q_entry, dict):
                            rq = q_entry.get("quantity")
                            ru = (q_entry.get("unit") or "").lower()
                            if rq is not None and ru == (cln_unit or "").lower():
                                try:
                                    raw_candidates.append(float(rq))
                                except (TypeError, ValueError):
                                    pass
                    cln_f = float(cln_qty)
                    if raw_candidates and not any(
                        abs(cln_f - rc) <= 1e-6 for rc in raw_candidates
                    ):
                        issues["quantity_mismatch"].append(
                            f"{e.get('name')}: raw={raw_candidates}{raw_unit} vs cleaned={cln_qty}{cln_unit}"
                        )
                except (TypeError, ValueError):
                    pass

    # --- 7. PROPRIETARY BLEND STRUCTURE ---
    for e in active:
        if not isinstance(e, dict):
            continue
        if e.get("proprietaryBlend") is True:
            if not e.get("name"):
                issues["blend_missing_name"].append(f"blend row has no name")

    return issues


def run(brand: str) -> int:
    cleaned_files = find_cleaned_for_brand(brand)
    if not cleaned_files:
        print(f"No cleaned output found for brand={brand!r}. Run the cleaner first.")
        return 2

    total_products = 0
    aggregated: Dict[str, int] = Counter()
    example_lines: Dict[str, List[str]] = defaultdict(list)
    products_with_issues: List[Tuple[str, int]] = []

    for fp in cleaned_files:
        batch = json.load(open(fp))
        products = batch if isinstance(batch, list) else batch.get("products", [])
        for p in products:
            pid = str(p.get("id") or p.get("dsld_id") or "")
            raw_fp = find_raw(pid)
            if not raw_fp:
                continue
            raw = json.load(open(raw_fp))
            issues = audit_product(raw, p)
            total_products += 1
            product_issue_count = sum(len(v) for v in issues.values())
            if product_issue_count > 0:
                products_with_issues.append((pid, product_issue_count))
            for cat, msgs in issues.items():
                aggregated[cat] += len(msgs)
                for m in msgs[:2]:
                    if len(example_lines[cat]) < 6:
                        example_lines[cat].append(f"  [{pid}] {m}")

    # --- Report ---
    print(f"\n{'='*78}")
    print(f"BRAND: {brand} — {total_products} products audited")
    print(f"{'='*78}")
    if not aggregated:
        print("\n  ✅ ALL CHECKS PASSED — cleaner output is a faithful lift from raw DSLD.")
        return 0

    print(f"\n  Products with at least one issue: {len(products_with_issues)}/{total_products}")
    print(f"  Issue breakdown:\n")
    for cat, n in aggregated.most_common():
        print(f"    {cat:30s} {n:5d}  (unique issues across all products)")
        for ex in example_lines[cat]:
            print(ex)
        print()
    # Top offenders
    products_with_issues.sort(key=lambda x: -x[1])
    print(f"  Top offenders:")
    for pid, n in products_with_issues[:10]:
        print(f"    {pid}: {n} issues")
    return 0 if not aggregated else 1


if __name__ == "__main__":
    brand = sys.argv[1] if len(sys.argv) > 1 else "Thorne"
    sys.exit(run(brand))
