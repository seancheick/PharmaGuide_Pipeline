"""v4 class router — decides which module scores a product.

Priority order (post-taxonomy refactor, 2026-05-20):

  1. probiotic              → probiotic
     - taxonomy primary_type == "probiotic"
     - OR legacy supp_type == "probiotic" (backward compat)
  2. prenatal name keyword  → multi_or_prenatal
     - overrides multi / omega routing for products like Prenatal DHA,
       Prenatal Gummies. Does NOT override probiotic — prenatal-probiotic
       blends still go to probiotic.
  3. multivitamin / b-complex → multi_or_prenatal
     - taxonomy primary_type in {multivitamin, b_complex}
  4. omega_3                → omega
     - taxonomy primary_type == "omega_3"
     - OR EPA/DHA canonical in ingredient panel (positive quantity)
     - OR omega name keyword (fish oil, omega-3, krill, cod liver, etc.)
     - OR standalone EPA/DHA word-boundary match (excludes DHEA)
  5. legacy multivitamin fallback → multi_or_prenatal
     - only when taxonomy is absent (old enriched batches pre-2026-05-20):
       legacy supp_type == "multivitamin" or primary_category == "multivitamin"
  6. fall through           → generic

The taxonomy primary_type field comes from scripts/supplement_taxonomy.py
(introduced 2026-05-20) and uses canonical-ID-based panel composition
analysis. It replaces the legacy supp_type heuristic which over-classified
single-issue targeted products (Collagen Love, Mighty Night sleep aid,
Vitafusion Omega-3 EPA/DHA, etc.) as multivitamin. The router prefers
taxonomy when present and falls back to legacy signals only for old
enriched batches that haven't been re-run through the new pipeline.

§13 architecture lock — this router does not import from score_supplements.py.

Omega routing was previously deferred to `generic` per the §9 P1.5
decision gate. P1.6 graduated omega to its own module. P3 added
multi_or_prenatal. This file is the only place where module dispatch
is decided.
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
_OMEGA_369_RE = re.compile(r"\bomega[\s-]*3[\s-]*[-/]?[\s-]*6[\s-]*[-/]?[\s-]*9\b", re.IGNORECASE)

# Per scripts/data/omega_rubric.json router.primary_category_match. The
# enricher emits these as primary_category values for fish-oil-class rows.
_OMEGA_PRIMARY_CATEGORIES = {"omega-3", "omega_3", "omega3", "fish_oil"}

# Per scripts/data/omega_rubric.json router.ingredient_panel_canonicals.
# Strongest routing signal — operates on the enricher's canonicalized
# identity rather than label text. A product whose ingredient panel has
# any EPA/DHA canonical with positive quantity is omega regardless of
# what the name says.
_OMEGA_INGREDIENT_CANONICALS = {"epa", "dha", "epa_dha"}
_NON_EPA_DHA_FATTY_ACID_CANONICALS = {
    "ala", "alpha_linolenic_acid", "alpha_linolenic_acid_ala",
    "omega_3_fatty_acids", "gla", "gamma_linolenic_acid",
    "cla", "conjugated_linoleic_acid", "oleic_acid",
}


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


def _has_non_epa_dha_fatty_acid_panel(product: Dict[str, Any]) -> bool:
    """Return True for ALA / GLA / CLA / 3-6-9 style panels with no EPA/DHA.

    These are fatty-acid supplements, but not EPA/DHA omega-module products.
    They must not route via name-only "omega" marketing.
    """
    if _has_omega_ingredient(product):
        return False
    iqd = (product or {}).get("ingredient_quality_data")
    if not isinstance(iqd, dict):
        return False
    candidates = iqd.get("ingredients_scorable") or iqd.get("ingredients") or []
    if not isinstance(candidates, list):
        return False
    for ing in candidates:
        if not isinstance(ing, dict):
            continue
        canonical = str(ing.get("canonical_id") or "").strip().lower()
        if canonical in _NON_EPA_DHA_FATTY_ACID_CANONICALS:
            return True
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

    # ALA / GLA / CLA / 3-6-9 products may use omega marketing language,
    # but they do not belong in the EPA/DHA omega module unless EPA/DHA is
    # actually disclosed in the panel.
    if _OMEGA_369_RE.search(name_text) or _has_non_epa_dha_fatty_acid_panel(product):
        return False

    name_text_lower = name_text.lower()
    if any(kw in name_text_lower for kw in _OMEGA_NAME_KEYWORDS):
        return True

    # Standalone EPA / DHA — word boundary regex, excludes DHEA.
    if _OMEGA_STANDALONE_RE.search(name_text):
        return True

    return False


# Taxonomy primary_type → v4 module mapping. The taxonomy emits 20 types
# (see scripts/data/product_type_vocab.json); v4 has 4 scoring modules.
# Most product classes route to `generic` because their scoring rubric is
# adequately handled by the generic dimensions; only probiotic / multi /
# omega have dedicated modules with class-specific dose / form / evidence
# rubrics.
_TAXONOMY_TO_MODULE = {
    "probiotic": "probiotic",
    "multivitamin": "multi_or_prenatal",
    "b_complex": "multi_or_prenatal",  # B-complex is a multi-vitamin variant
    "omega_3": "omega",
    # Everything else routes to generic — listed explicitly so future
    # taxonomy types are caught by the unknown-key fallthrough below:
    "single_vitamin": "generic",
    "single_mineral": "generic",
    "vitamin_mineral_combo": "generic",
    "herbal_botanical": "generic",
    "protein_powder": "generic",
    "collagen": "generic",
    "greens_powder": "generic",
    "electrolyte": "generic",
    "pre_workout": "generic",
    "amino_acid": "generic",
    "fiber_digestive": "generic",
    "sleep_support": "generic",
    "immune_support": "generic",
    "joint_support": "generic",
    "beauty_hair_skin_nails": "generic",
    "general_supplement": "generic",
}


def _read_primary_type(product: Dict[str, Any]) -> str:
    """Return the taxonomy `primary_type` if present, else empty string.

    Pipeline writes the field at two paths (set by enrich_supplements_v3
    and preserved by score_supplements):
      product["primary_type"]
      product["supplement_taxonomy"]["primary_type"]
    Both are read for resilience.
    """
    direct = (product or {}).get("primary_type")
    if isinstance(direct, str) and direct.strip():
        return direct.strip().lower()
    taxonomy = (product or {}).get("supplement_taxonomy") or {}
    if isinstance(taxonomy, dict):
        nested = taxonomy.get("primary_type")
        if isinstance(nested, str) and nested.strip():
            return nested.strip().lower()
    return ""


def _read_legacy_supp_type(product: Dict[str, Any]) -> str:
    """Return the legacy supplement_type.type heuristic (pre-taxonomy enrichers)."""
    st_payload = (product or {}).get("supplement_type")
    if isinstance(st_payload, dict):
        value = st_payload.get("type") or ""
    elif isinstance(st_payload, str):
        value = st_payload  # legacy shape (rare)
    else:
        value = ""
    return str(value).strip().lower()


def class_for_product(product: Dict[str, Any]) -> str:
    """Return one of VALID_CLASSES given an enriched product blob.

    Reads `primary_type` from the new supplement taxonomy as the canonical
    signal. Falls back to legacy `supplement_type.type` / `primary_category`
    only when taxonomy is absent (old enriched batches pre-2026-05-20).

    Never raises on malformed input. Never returns None or a value outside
    VALID_CLASSES. Missing or unknown signals fall through to `generic`.
    """
    primary_type = _read_primary_type(product)
    legacy_supp_type = _read_legacy_supp_type(product)
    name_text = " ".join(
        str((product or {}).get(k) or "")
        for k in ("product_name", "fullName", "brand_name", "bundleName")
    )

    # Priority 1: probiotic. Wins absolutely — strain panel inspection is
    # the strongest signal. Either taxonomy or legacy supp_type routes here.
    if primary_type == "probiotic" or legacy_supp_type == "probiotic":
        return "probiotic"

    # Priority 2: prenatal name keyword. Overrides multi / omega routing
    # for products like Prenatal DHA, Prenatal Gummies, Pregnancy Vitamins.
    # NOTE: prenatal-DHA gets multi_or_prenatal NOT omega — the prenatal
    # use case has stricter dose/safety expectations (folate, iron, iodine
    # critical-nutrient floors) that the multi module is designed to handle.
    # Prenatal-probiotic was already handled by Priority 1 above.
    if _PRENATAL_KEYWORDS.search(name_text):
        return "multi_or_prenatal"

    # Priority 3: taxonomy primary_type — canonical signal when present.
    # Maps the 20 taxonomy types to the 4 v4 modules. Unknown taxonomy
    # values (new types added later that aren't in _TAXONOMY_TO_MODULE)
    # fall through to the omega / generic logic below rather than crashing.
    if primary_type:
        module = _TAXONOMY_TO_MODULE.get(primary_type)
        if module == "multi_or_prenatal":
            return "multi_or_prenatal"
        if module == "omega":
            return "omega"
        if module == "generic":
            # Taxonomy is authoritative for generic classes, but the
            # physical panel fact of disclosed EPA/DHA still wins. Do not let
            # name-only omega marketing override taxonomy here — ALA / 3-6-9 /
            # fatty-acid blends are intentionally generic unless EPA/DHA is
            # actually disclosed.
            return "omega" if _has_omega_ingredient(product) else "generic"
        # Unknown taxonomy type: fall through to legacy omega / multi fallback
        # rather than crashing.

    # Priority 4: omega panel-canonical / name-keyword detection.
    # The panel-canonical (canonical_id ∈ {epa,dha,epa_dha} with positive
    # quantity) is the strongest omega signal — it operates on the
    # enricher's canonicalized identity. Name-keyword and standalone
    # EPA/DHA fallbacks catch labels where canonicalization didn't run.
    if _is_omega_class(product, name_text):
        return "omega"

    # Priority 5: legacy multivitamin fallback. Only fires when the
    # taxonomy didn't classify the product (old enriched batch) — we
    # explicitly do NOT trust legacy supp_type=multivitamin when the
    # taxonomy is present, because that signal over-classified targeted
    # products (Collagen Love, Mighty Night, Vitafusion Omega-3 EPA/DHA)
    # as multivitamin (Bug C, 2026-05-20).
    if not primary_type:
        if legacy_supp_type == "multivitamin":
            return "multi_or_prenatal"
        primary_category = str((product or {}).get("primary_category") or "").strip().lower()
        if primary_category == "multivitamin":
            return "multi_or_prenatal"

    # Priority 6: generic catch-all.
    return "generic"
