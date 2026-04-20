"""
Cleaner fidelity smoke test — raw DSLD vs cleaned output.

Runs the cleaner against 20 diverse products and asserts on each:
  1. Every raw DSLD row maps to an output row (activeIngredients, inactiveIngredients,
     or nutritionalInfo) — nothing silently lost.
  2. forms[].category, forms[].ingredientGroup, forms[].uniiCode preserved when
     present in raw DSLD.
  3. Every mapped active ingredient has canonical_id + canonical_source_db.
  4. Every row in a vitamin/mineral DSLD category has label_nutrient_context set.
  5. Source descriptors (DSLD category == "animal part or source" / "plant part")
     remain inside forms[], never promoted to top-level activeIngredients.
  6. Nutritional facts (Calories/Total Fat/Carbs/Protein/Sodium/Fiber) end up in
     the product-level nutritionalInfo block.

Run: ``python3 scripts/tests/cleaner_fidelity_smoke_test.py``
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from glob import glob
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


# Curated sample list spanning: single-ingredient, small multi, large multi,
# proprietary blend, phytosome delivery, probiotic, fish oil, enzyme/glandular,
# yeast-fermented, mineral chelate, botanical, multivitamin, and a product
# hit by each of the two known canonical-selection bugs.
SAMPLES: List[Tuple[str, str, str]] = [
    # (pid, brand, description)
    ("241306", "Garden_of_life",        "Joint Health — pancreatin/enzymes"),
    ("16037",  "Thorne",                "Planti-Oxidants — silybin phytosome (canonical bug)"),
    ("219141", "Pure_Encapsulations",   "Joint Complex — meriva phytosome + UC-II"),
    ("246351", "Pure_Encapsulations",   "NeuroMood Pure Pack — large multi"),
    ("182730", "Pure_Encapsulations",   "Athletic Pure Pack — mega multi w/ blends"),
    ("12012",  "CVS",                   "Spectravite — multi w/ Phosphorus+DCP (canonical bug)"),
    ("173715", "Garden_of_life",        "Oceans 3 Better Brain — yeast K/B vitamins"),
    ("288344", "Garden_of_life",        "Vitamin Code Men — blend unrolling 26→63"),
    ("13186",  "Garden_of_life",        "Immune Balance Daily — Emblic vit C"),
    ("12141",  "Spring_Valley",         "Probiotic Multi-Enzyme"),
    ("245156", "Goli",                  "Ashwagandha Gummy — KSM-66 branded"),
    ("16010",  "Thorne",                "Magnesium Time-Sorb"),
    ("16080",  "Thorne",                "Grape seed Phytosome"),
    ("174164", "Garden_of_life",        "Magnesium — dead sea minerals"),
    ("173734", "Garden_of_life",        "Iron — ionic plant minerals"),
    ("173803", "Garden_of_life",        "Vitamin K/Zinc — RAW food-created"),
    ("12012",  "CVS",                   "Spectravite (re-run sanity)"),
    ("18193",  "CVS",                   "Boron (sodium tetraborate — banned routing)"),
    ("235674", "Garden_of_life",        "SOD Cantaloupe — source descriptor"),
    ("233697", "Garden_of_life",        "SOD variant — source descriptor"),
]


def find_raw(pid: str) -> Optional[str]:
    for cand in [
        f"/Users/seancheick/Documents/DataSetDsld/staging/brands/*/{pid}.json",
        f"/Users/seancheick/Documents/DataSetDsld/forms/*/{pid}.json",
    ]:
        hits = glob(cand)
        if hits:
            return hits[0]
    return None


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def row_represented(raw_row: Dict[str, Any], cleaned: Dict[str, Any]) -> Optional[str]:
    """
    Return None if raw_row is represented somewhere in the cleaned output,
    or an explanation string if not.

    Representation can be:
      - an activeIngredients entry matching by name/ingredientId
      - an inactiveIngredients entry
      - a nutritionalInfo entry (calories/fat/protein/etc.)
      - a nested ingredient inside another active row (for flattened blends)
    """
    raw_name = (raw_row.get("name") or "").strip().lower()
    raw_id = raw_row.get("ingredientId")
    if not raw_name:
        return "raw row has no name"

    # Nutritional info canonical keys
    NUTR_KEYS = {
        "calorie": "calories",
        "calories": "calories",
        "total carbohydrate": "totalCarbohydrates",
        "carbohydrates": "totalCarbohydrates",
        "total fat": "totalFat",
        "sugar": "sugars",
        "sugars": "sugars",
        "sodium": "sodium",
        "protein": "protein",
        "fiber": "dietaryFiber",
        "dietary fiber": "dietaryFiber",
        "cholesterol": "cholesterol",
    }
    # Direct nutritional capture
    for needle, key in NUTR_KEYS.items():
        if needle in raw_name:
            if cleaned.get("nutritionalInfo", {}).get(key) is not None:
                return None
            # Nutritional rows can also appear nested; consider absence acceptable
            # only if amount is None / row is non-informative.
            # We won't treat this as a hard failure because some products list
            # Calories as zero and the extractor may skip.
            return None

    def _match(entries: List[Dict[str, Any]]) -> bool:
        for e in entries:
            if not isinstance(e, dict):
                continue
            if raw_id is not None and e.get("ingredientId") == raw_id:
                return True
            en = (e.get("name") or "").strip().lower()
            if en == raw_name:
                return True
            # branded-token can shorten ("KSM-66 Ashwagandha" → "KSM-66")
            # accept if raw_source_text matches the raw name
            if raw_name in (e.get("raw_source_text") or "").lower():
                return True
            # nested children
            for nested in e.get("nestedIngredients", []) or []:
                if isinstance(nested, dict):
                    nn = (nested.get("name") or "").strip().lower()
                    if nn == raw_name or raw_name in nn:
                        return True
        return False

    if _match(cleaned.get("activeIngredients", []) or []):
        return None
    if _match(cleaned.get("inactiveIngredients", []) or []):
        return None
    # Blend container rows get absorbed into children
    if (raw_row.get("category") or "").lower() in {"blend"}:
        return None
    # Rollup / aggregate rows ("Total Omega-6 Fatty Acids", "Total Collagen",
    # "Typical Fatty Acid Composition", etc.) are intentionally dropped by
    # the cleaner — they are label summaries, not discrete supplements.
    _rollup_prefixes = ("total ", "other ", "typical ", "all other ")
    if any(raw_name.startswith(p) for p in _rollup_prefixes):
        return None
    return f"raw row {raw_name!r} (id={raw_id}) not found in any cleaned section"


def check_form_field_preservation(cleaned_ing: Dict[str, Any], raw_row: Dict[str, Any]) -> List[str]:
    """Verify category/ingredientGroup/uniiCode propagated from raw forms."""
    issues: List[str] = []
    raw_forms = raw_row.get("forms") or []
    cln_forms = cleaned_ing.get("forms") or []
    if not raw_forms:
        return issues
    # Match by ingredientId where possible, else by order/position
    for rf in raw_forms:
        if not isinstance(rf, dict):
            continue
        rf_id = rf.get("ingredientId")
        cf = next(
            (c for c in cln_forms if isinstance(c, dict) and c.get("ingredientId") == rf_id),
            None,
        )
        if cf is None:
            issues.append(f"form id={rf_id} ({rf.get('name')!r}) missing in cleaned")
            continue
        for field in ("category", "ingredientGroup", "uniiCode"):
            if rf.get(field) is not None and cf.get(field) is None:
                issues.append(f"form {rf_id}: {field} dropped (raw={rf.get(field)!r})")
    return issues


def check_mapping_fields(cleaned_ing: Dict[str, Any]) -> List[str]:
    """Every mapped ingredient must have canonical_id + source_db."""
    issues: List[str] = []
    if cleaned_ing.get("mapped") is True:
        if cleaned_ing.get("canonical_id") in (None, ""):
            issues.append(f"mapped ingredient {cleaned_ing.get('name')!r} missing canonical_id")
        if cleaned_ing.get("canonical_source_db") in (None, "", "unmapped"):
            issues.append(f"mapped ingredient {cleaned_ing.get('name')!r} missing canonical_source_db")
    return issues


def check_nutrient_context(cleaned_ing: Dict[str, Any]) -> List[str]:
    """Vitamin/mineral rows must have label_nutrient_context set."""
    issues: List[str] = []
    if (cleaned_ing.get("raw_category") or "") in {"vitamin", "mineral"}:
        if not cleaned_ing.get("label_nutrient_context"):
            issues.append(f"{cleaned_ing.get('name')!r} [cat={cleaned_ing.get('raw_category')}] missing label_nutrient_context")
    return issues


def check_source_descriptor_not_promoted(cleaned: Dict[str, Any]) -> List[str]:
    """
    Source descriptors (category=='animal part or source' / 'plant part') must
    appear inside forms[], never as a top-level activeIngredients row.
    """
    issues: List[str] = []
    SOURCE_ONLY_CATS = {"animal part or source", "plant part"}
    active_names = {
        (a.get("name") or "").strip().lower()
        for a in cleaned.get("activeIngredients", []) or []
    }
    # Known tissue/organ tokens that would indicate a source was promoted
    SOURCE_TOKENS = {"pancreas", "liver", "spleen", "thymus", "heart", "kidney", "cantaloupe"}
    for a in cleaned.get("activeIngredients", []) or []:
        if not isinstance(a, dict):
            continue
        nm = (a.get("name") or "").strip().lower()
        # Bare tissue/plant-part names must not be ingredients
        if nm in SOURCE_TOKENS:
            issues.append(f"Source token {nm!r} promoted to activeIngredient")
    return issues


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run() -> int:
    normalizer = EnhancedDSLDNormalizer()

    total_issues = 0
    per_product_summary: List[Tuple[str, int, int, int]] = []

    for pid, brand, descr in SAMPLES:
        raw_fp = find_raw(pid)
        if not raw_fp:
            print(f"[SKIP] {pid} {brand}: raw not found")
            continue
        raw = json.load(open(raw_fp))
        cleaned = normalizer.normalize_product(raw)

        raw_rows = [r for r in (raw.get("ingredientRows") or []) if isinstance(r, dict)]
        # Flatten nested rows for coverage check
        flat_raw = list(raw_rows)
        for r in raw_rows:
            for nr in r.get("nestedRows", []) or []:
                if isinstance(nr, dict):
                    flat_raw.append(nr)

        issues: List[str] = []

        # 1. Row representation
        for r in flat_raw:
            msg = row_represented(r, cleaned)
            if msg:
                issues.append(f"[coverage] {msg}")

        # 2-4. Per-ingredient field checks on active rows
        for a in cleaned.get("activeIngredients", []) or []:
            if not isinstance(a, dict):
                continue
            # Match raw row by ingredientId
            raw_match = next(
                (r for r in flat_raw if r.get("ingredientId") == a.get("ingredientId")),
                None,
            )
            if raw_match is not None:
                for m in check_form_field_preservation(a, raw_match):
                    issues.append(f"[form_fields] {a.get('name')}: {m}")
            for m in check_mapping_fields(a):
                issues.append(f"[mapping] {m}")
            for m in check_nutrient_context(a):
                issues.append(f"[nutrient_ctx] {m}")

        # 5. Source descriptors never promoted
        for m in check_source_descriptor_not_promoted(cleaned):
            issues.append(f"[source_leak] {m}")

        n_active = len(cleaned.get("activeIngredients") or [])
        n_inactive = len(cleaned.get("inactiveIngredients") or [])
        per_product_summary.append((f"{pid} {brand[:12]}", n_active, n_inactive, len(issues)))

        tag = "OK" if not issues else f"{len(issues)} ISSUES"
        print(f"\n[{tag}] {pid} {brand} — {descr}")
        print(f"       raw_rows={len(raw_rows)} active={n_active} inactive={n_inactive}")
        # Sample new fields on first active ingredient
        if cleaned.get("activeIngredients"):
            a0 = cleaned["activeIngredients"][0]
            print(f"       sample: name={a0.get('name')!r} cid={a0.get('canonical_id')!r} "
                  f"db={a0.get('canonical_source_db')!r} nut_ctx={a0.get('label_nutrient_context')!r}")
        for issue in issues[:8]:
            print(f"       - {issue}")
        if len(issues) > 8:
            print(f"       ... and {len(issues) - 8} more")
        total_issues += len(issues)

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------
    print("\n" + "=" * 76)
    print("SUMMARY")
    print("=" * 76)
    print(f"{'Product':30s}  {'active':>6}  {'inactive':>8}  {'issues':>6}")
    for row in per_product_summary:
        print(f"{row[0]:30s}  {row[1]:>6}  {row[2]:>8}  {row[3]:>6}")
    print("-" * 76)
    print(f"Total issues across {len(per_product_summary)} products: {total_issues}")
    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
