"""v4 class router — decides which module scores a product.

Priority order (intentionally identical to score_supplements._b5_class_for_product
where the two overlap, but a separate decision surface — v4 routes among
the SCORING modules `probiotic / multi_or_prenatal / omega / generic`,
while B5 routes among the OPACITY classes `probiotic / multi_or_prenatal /
sports_active / generic`; sports_active doesn't get its own v4 module
because sports stacks fall through generic with class-specific opacity
already handled at B5):

  1. supp_type == "probiotic"      → probiotic       (strongest signal)
  2. supp_type == "multivitamin"   → multi_or_prenatal
  3. product name contains prenatal/pregnancy/etc. → multi_or_prenatal
     (Prenatal DHA / Prenatal Probiotic style products)
  4. primary_category == "multivitamin"           → multi_or_prenatal
     (specialty/targeted enricher classification + multivit category)
  5. omega class detected (P1.6) → omega
     - primary_category in {omega-3, omega_3, fish_oil, omega3}
     - OR product name has omega keyword (fish oil, omega-3, krill,
       algae, cod liver, EPA+DHA)
     - OR product/brand/bundle name has standalone EPA/DHA word-boundary
       match
  6. fall through                                  → generic

Omega routing was previously deferred to `generic` per the §9 P1.5
decision gate. The gate fired against canary rows 5–9: generic
under-credited EPA/DHA dose, IFOS scope, and TG/rTG/EE form by 4–11
cal points (logged in P1.5 omega-debt note). P1.6 graduates omega
to its own module.
"""

from __future__ import annotations

import re
from typing import Any, Dict

VALID_CLASSES = ("generic", "probiotic", "multi_or_prenatal", "omega")

_PRENATAL_KEYWORDS = re.compile(
    r"\b(prenatal|pregnancy|pre-natal|expecting|maternal|gestation)\b",
    re.IGNORECASE,
)

# Per scripts/data/omega_rubric.json router.name_keywords. Lowercased
# substring matches against the joined product/brand/bundle name text.
# These are unambiguous multi-character tokens that don't false-positive
# on unrelated products. Short standalone tokens (EPA / DHA) need
# word-boundary regex below to avoid matching inside DHEA / similar.
_OMEGA_NAME_KEYWORDS = (
    "fish oil",
    "omega-3",
    "omega 3",
    "omega3",
    "krill",
    "algae oil",
    "algal oil",
    "cod liver",
    "epa+dha",
    "epa dha",
    "epa/dha",
)

# Standalone EPA / DHA word-boundary detection. CRITICAL: must use \b so
# DHEA (dehydroepiandrosterone) does not match — DHEA is one word, and
# `\bDHA\b` requires DHA to be surrounded by non-word characters. Same
# guard for `\bEPA\b` against any future EPA-prefix false-positives.
# Case-insensitive so labels like "Pure epa" still route.
_OMEGA_STANDALONE_RE = re.compile(r"\b(EPA|DHA)\b", re.IGNORECASE)

# Per scripts/data/omega_rubric.json router.primary_category_match. The
# enricher emits these as primary_category values for fish-oil-class rows.
_OMEGA_PRIMARY_CATEGORIES = {"omega-3", "omega_3", "omega3", "fish_oil"}

# Per scripts/data/omega_rubric.json router.ingredient_panel_canonicals.
# Strongest routing signal — operates on the enricher's canonicalized
# identity rather than label text. A product whose ingredient panel has
# any EPA/DHA canonical with positive quantity is omega regardless of
# what the name says.
_OMEGA_INGREDIENT_CANONICALS = {"epa", "dha", "epa_dha"}


def _has_omega_ingredient(product: Dict[str, Any]) -> bool:
    """Return True when ingredient_quality_data contains any EPA/DHA
    canonical with a positive quantity. Strongest router signal."""
    iqd = (product or {}).get("ingredient_quality_data")
    if not isinstance(iqd, dict):
        return False
    candidates = (
        iqd.get("ingredients_scorable")
        or iqd.get("ingredients")
        or []
    )
    if not isinstance(candidates, list):
        return False
    for ing in candidates:
        if not isinstance(ing, dict):
            continue
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if canonical not in _OMEGA_INGREDIENT_CANONICALS:
            continue
        for key in ("quantity", "amount", "dose", "dosage"):
            value = ing.get(key)
            try:
                if value is not None and float(value) > 0:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def _is_omega_class(product: Dict[str, Any], name_text: str) -> bool:
    """Detect omega-class routing signals.

    Independent triggers — any one routes to omega (most-specific first):
      1. ingredient_quality_data has canonical_id ∈ {epa, dha, epa_dha}
         with positive quantity (strongest signal — enricher already
         canonicalized the identity)
      2. primary_category in _OMEGA_PRIMARY_CATEGORIES
      3. product name contains an unambiguous omega keyword
      4. product name has standalone EPA or DHA (word-boundary regex,
         excludes DHEA and other false positives)

    The function takes the raw mixed-case name_text so the standalone
    EPA/DHA regex can use IGNORECASE without losing word boundaries.

    HISTORICAL — a 5th trigger (category_breakdown.fatty_acid plurality)
    was removed 2026-05-20 after a real-catalog audit caught ~250 false
    positives: CLA / Borage Oil (GLA) / Flax Seed Oil (ALA-only) / MCT /
    Liposomal Glutathione (lecithin) all count as fatty_acid in the
    enricher's category_breakdown but NONE are EPA/DHA-bearing. The
    plurality check was redundant — every legitimate omega product
    (Sports Research, Nordic Naturals Ultimate Omega, Garden of Life
    Advanced Omega, etc.) is already caught by _has_omega_ingredient
    because the enricher canonicalizes EPA/DHA from the ingredient panel.
    Per the dev's 2026-05-20 feedback: ALA is alpha-linolenic acid,
    a different molecule from EPA/DHA; ALA-only products route to
    generic (where ALA gets the IOM AI when the rda_optimal_uls fix
    lands), not omega.
    """
    # 1. Strongest signal: enricher canonicalized an EPA/DHA ingredient.
    if _has_omega_ingredient(product):
        return True

    primary_category = str((product or {}).get("primary_category") or "").strip().lower()
    if primary_category in _OMEGA_PRIMARY_CATEGORIES:
        return True

    name_text_lower = name_text.lower()
    if any(kw in name_text_lower for kw in _OMEGA_NAME_KEYWORDS):
        return True

    # Standalone EPA / DHA — word boundary regex, excludes DHEA.
    if _OMEGA_STANDALONE_RE.search(name_text):
        return True

    return False


def class_for_product(product: Dict[str, Any]) -> str:
    """Return one of VALID_CLASSES given an enriched product blob.

    Conservative defaults: missing supp_type / unknown supp_type → generic.
    Never returns None or a value outside VALID_CLASSES.
    """
    st_payload = (product or {}).get("supplement_type")
    if isinstance(st_payload, dict):
        supp_type = st_payload.get("type") or ""
    elif isinstance(st_payload, str):
        supp_type = st_payload  # legacy shape (rare)
    else:
        supp_type = ""
    supp_type = str(supp_type).strip().lower()

    # Priority 1: probiotic supp_type wins absolutely (enricher inspected
    # the strain panel — trust it over name keywords).
    if supp_type == "probiotic":
        return "probiotic"

    # Priority 2: multivitamin supp_type.
    if supp_type == "multivitamin":
        return "multi_or_prenatal"

    # Priority 3: prenatal name keyword on a non-multivit product.
    # Covers single-active prenatal DHA, prenatal probiotic, etc.
    # NOTE: Prenatal DHA gets multi_or_prenatal NOT omega — the prenatal
    # use case has stricter dose/safety expectations that the multi
    # module is designed to handle.
    name_text = " ".join(
        str((product or {}).get(k) or "")
        for k in ("product_name", "fullName", "brand_name", "bundleName")
    )
    if _PRENATAL_KEYWORDS.search(name_text):
        return "multi_or_prenatal"

    # Priority 4: primary_category=multivitamin fallback.
    # Catches GoL MyKind Men's/Women's Multi where supp_type=specialty
    # but the category classifier got it right.
    primary_category = str((product or {}).get("primary_category") or "").strip().lower()
    if primary_category == "multivitamin":
        return "multi_or_prenatal"

    # Priority 5: omega-class detection (P1.6). Routes fish-oil / krill /
    # algae / cod liver / EPA-DHA products to the dedicated omega module.
    # See _is_omega_class for the trigger conditions (ingredient panel,
    # primary_category, name keyword, standalone EPA/DHA).
    if _is_omega_class(product, name_text):
        return "omega"

    # Priority 6: generic (v3 single-nutrient / specialty / targeted /
    # herbal / sports — generic handles all until later phases peel them off).
    return "generic"
