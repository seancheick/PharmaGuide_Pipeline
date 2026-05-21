"""
Supplement Taxonomy Classification Engine
==========================================

Canonical taxonomy for PharmaGuide supplement classification.

Produces structured classification with:
  - primary_type: broad product category (20 types)
  - secondary_type: specific compound/focus (e.g. zinc, vitamin_d, ashwagandha)
  - percentile_category: peer-comparison cohort key
  - classification_confidence: 0.0–1.0
  - classification_reasons: list of signals that drove the decision

Design principles:
  - NP/zero-potency ingredients are excluded from type inference
  - Classification is deterministic and auditable
  - primary_type drives scoring behavior; percentile_category drives peer comparison
  - general_supplement is a true residual, not a missing-taxonomy catchall
"""

from __future__ import annotations

import os
import re
from math import ceil
from typing import Any

from supplement_type_utils import (
    PROBIOTIC_TERMS,
    NON_SCORABLE_CATEGORIES,
    canonical_category,
    _normalize_text,
    _safe_list,
    _ingredient_name,
)

# ============================================================================
# PRIMARY TYPE DEFINITIONS — derived from product_type_vocab.json
# ============================================================================

def _load_primary_types() -> list[str]:
    """Load PRIMARY_TYPES from the canonical vocab file.

    This ensures the classifier and the vocab file (which ships to Flutter)
    can never drift. If the vocab file is missing, falls back to a hardcoded
    list and logs a warning.
    """
    import json
    import logging
    vocab_path = os.path.join(
        os.path.dirname(__file__), "data", "product_type_vocab.json"
    )
    try:
        with open(vocab_path, encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("product_types", [])
        ids = [e["id"] for e in entries if isinstance(e, dict) and e.get("id")]
        if ids:
            return ids
    except (OSError, json.JSONDecodeError, KeyError):
        logging.getLogger(__name__).warning(
            "product_type_vocab.json not found or invalid; using hardcoded PRIMARY_TYPES"
        )
    return [
        "single_vitamin", "single_mineral", "vitamin_mineral_combo",
        "multivitamin", "b_complex", "omega_3", "probiotic",
        "herbal_botanical", "protein_powder", "collagen", "greens_powder",
        "electrolyte", "pre_workout", "amino_acid", "fiber_digestive",
        "sleep_support", "immune_support", "joint_support",
        "beauty_hair_skin_nails", "general_supplement",
    ]


PRIMARY_TYPES = _load_primary_types()

# ============================================================================
# INGREDIENT CLASSIFICATION HELPERS
# ============================================================================

_VITAMIN_CANONICAL_IDS = frozenset({
    "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_d3", "vitamin_d2",
    "vitamin_e", "vitamin_k", "vitamin_k1", "vitamin_k2",
    "vitamin_b1", "vitamin_b2", "vitamin_b3", "vitamin_b5",
    "vitamin_b6", "vitamin_b7", "vitamin_b12",
    "folate", "folic_acid", "methylfolate", "niacin", "niacinamide",
    "thiamine", "riboflavin", "pyridoxine", "cobalamin",
    "pantothenic_acid", "biotin", "choline", "inositol",
})

_MINERAL_CANONICAL_IDS = frozenset({
    "zinc", "magnesium", "calcium", "iron", "selenium", "chromium",
    "copper", "manganese", "potassium", "iodine", "molybdenum",
    "boron", "phosphorus", "silica", "vanadium", "lithium",
})

_B_VITAMIN_IDS = frozenset({
    "vitamin_b1", "vitamin_b2", "vitamin_b3", "vitamin_b5",
    "vitamin_b6", "vitamin_b7", "vitamin_b12",
    "folate", "folic_acid", "methylfolate", "niacin", "niacinamide",
    "thiamine", "riboflavin", "pyridoxine", "cobalamin",
    "pantothenic_acid", "biotin", "choline", "inositol",
})

_OMEGA_CANONICAL_IDS = frozenset({
    "omega_3", "epa", "dha", "fish_oil", "algae_oil", "krill_oil",
    "cod_liver_oil", "ala", "omega_3_fatty_acids",
})

_AMINO_ACID_IDS = frozenset({
    "l_theanine", "l_glutamine", "l_arginine", "l_carnitine",
    "l_tyrosine", "l_lysine", "l_tryptophan", "l_citrulline",
    "bcaa", "beta_alanine", "creatine", "taurine", "glycine",
    "n_acetyl_cysteine", "nac", "glutathione", "acetyl_l_carnitine",
    "gaba", "5_htp", "sam_e",
})

_COLLAGEN_IDS = frozenset({
    "collagen", "collagen_peptides", "hydrolyzed_collagen",
    "type_ii_collagen", "bovine_collagen", "marine_collagen",
    "type_i_collagen", "type_iii_collagen",
})

# Name-based signals for functional categories
_SLEEP_NAME_TOKENS = {"sleep", "melatonin", "nighttime", "night time", "pm", "rest", "calm sleep"}
_IMMUNE_NAME_TOKENS = {"immune", "immunity", "defense", "elderberry", "echinacea"}
_JOINT_NAME_TOKENS = {"joint", "glucosamine", "chondroitin", "msm", "flexibility", "cartilage"}
_BEAUTY_NAME_TOKENS = {"hair", "skin", "nail", "nails", "beauty", "glow", "radiance", "keratin"}
_FIBER_NAME_TOKENS = {"fiber", "fibre", "digestive", "prebiotic", "psyllium", "inulin"}

# Secondary type detection: compound → secondary_type
_SECONDARY_TYPE_MAP = {
    "zinc": "zinc",
    "magnesium": "magnesium",
    "vitamin_d": "vitamin_d", "vitamin_d3": "vitamin_d", "vitamin_d2": "vitamin_d",
    "vitamin_c": "vitamin_c",
    "biotin": "biotin", "vitamin_b7": "biotin",
    "ashwagandha": "ashwagandha",
    "turmeric": "turmeric_curcumin", "curcumin": "turmeric_curcumin",
    "berberine": "berberine",
    "epa": "fish_oil_epa_dha", "dha": "fish_oil_epa_dha",
    "fish_oil": "fish_oil_epa_dha", "krill_oil": "fish_oil_epa_dha",
    "omega_3": "fish_oil_epa_dha",
    "iron": "iron",
    "calcium": "calcium",
    "selenium": "selenium",
    "potassium": "potassium",
    "iodine": "iodine",
    "melatonin": "melatonin",
    "elderberry": "elderberry",
    "echinacea": "echinacea",
    "valerian": "valerian",
    "st_johns_wort": "st_johns_wort",
    "saw_palmetto": "saw_palmetto",
    "milk_thistle": "milk_thistle",
    "collagen": "collagen", "collagen_peptides": "collagen",
    "glucosamine": "glucosamine",
    "l_theanine": "l_theanine",
    "quercetin": "quercetin",
    "coq10": "coq10", "ubiquinol": "coq10",
    "resveratrol": "resveratrol",
    "maca": "maca",
    "rhodiola": "rhodiola",
    "lion_s_mane": "lions_mane", "lions_mane": "lions_mane",
    "cordyceps": "cordyceps",
    "reishi": "reishi",
    "folic_acid": "folate", "folate": "folate", "methylfolate": "folate",
    "creatine": "creatine",
    "5_htp": "5_htp",
    "gaba": "gaba",
}


# ============================================================================
# NP / ZERO-POTENCY FILTER
# ============================================================================

_NP_UNITS = frozenset({
    "np", "", "not provided", "unknown", "n/a", "na", "none",
    "not applicable", "proprietary",
})


def _is_non_quantified(row: dict[str, Any]) -> bool:
    """Check if an ingredient row is non-quantified (zero potency / NP unit).

    These ingredients should NOT influence type classification but are
    preserved as supporting/base ingredients for transparency.
    """
    qty = row.get("quantity", row.get("amount", row.get("qty")))
    unit = _normalize_text(row.get("quantityUnit", row.get("unit", "")))

    # Zero quantity
    if qty is not None:
        try:
            if float(qty) == 0:
                return True
        except (ValueError, TypeError):
            pass

    # NP / empty / unknown units
    if unit in _NP_UNITS:
        return True

    # No quantity AND no unit
    if qty is None and not unit:
        return True

    return False


_ALL_FUNCTIONAL_TOKENS = (
    _SLEEP_NAME_TOKENS | _IMMUNE_NAME_TOKENS | _JOINT_NAME_TOKENS
    | _BEAUTY_NAME_TOKENS | _FIBER_NAME_TOKENS
)


def _has_functional_name_signal(product_name: str) -> bool:
    """Quick check: does the product name contain any functional category token?"""
    return any(t in product_name for t in _ALL_FUNCTIONAL_TOKENS)


def _detect_functional_name(product_name: str) -> tuple[str, float, str]:
    """Detect functional category from product name. Returns (type, confidence, reason)."""
    if any(t in product_name for t in _BEAUTY_NAME_TOKENS):
        return "beauty_hair_skin_nails", 0.85, f"beauty name signal in '{product_name}'"
    if any(t in product_name for t in _SLEEP_NAME_TOKENS):
        return "sleep_support", 0.85, f"sleep name signal in '{product_name}'"
    if any(t in product_name for t in _IMMUNE_NAME_TOKENS):
        return "immune_support", 0.85, f"immune name signal in '{product_name}'"
    if any(t in product_name for t in _JOINT_NAME_TOKENS):
        return "joint_support", 0.85, f"joint name signal in '{product_name}'"
    if any(t in product_name for t in _FIBER_NAME_TOKENS):
        return "fiber_digestive", 0.8, f"fiber/digestive name signal in '{product_name}'"
    return "general_supplement", 0.3, "no functional match"


def _has_omega_name_signal(product_name: str) -> bool:
    """Check if product name contains omega-related tokens with word boundaries.

    Short tokens like 'dha' and 'epa' need word-boundary checks to avoid
    false positives (e.g. 'ashwagandha' contains 'dha').
    """
    # Long tokens — simple substring is safe
    if any(t in product_name for t in ("omega", "fish oil", "krill", "cod liver")):
        return True
    # Short tokens — require word boundary
    if re.search(r'\bdha\b', product_name):
        return True
    if re.search(r'\bepa\b', product_name):
        return True
    return False


# ============================================================================
# CORE CLASSIFICATION ENGINE
# ============================================================================

def classify_supplement(product: dict[str, Any]) -> dict[str, Any]:
    """Classify a supplement product into the canonical taxonomy.

    Returns dict with:
      - primary_type: str
      - secondary_type: str | None
      - percentile_category: str
      - classification_confidence: float (0.0-1.0)
      - classification_reasons: list[str]
      - quantified_active_count: int
      - non_quantified_base_count: int
      - category_breakdown: dict
    """
    rows, source = _iter_classification_rows_v2(product)
    reasons: list[str] = []

    # DSLD productType signal (if available from raw data or preserved by enricher)
    dsld_product_type = ""
    pt = product.get("productType") or product.get("dsld_product_type_raw") or {}
    if isinstance(pt, dict):
        dsld_product_type = _normalize_text(pt.get("langualCodeDescription", ""))

    # Partition into quantified (therapeutic) vs non-quantified (base/NP)
    quantified_rows: list[dict[str, Any]] = []
    non_quantified_rows: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    canonical_ids: list[str] = []
    probiotic_count = 0

    for row in rows:
        category = canonical_category(row.get("category"))
        role = _normalize_text(row.get("role_classification"))

        # Skip truly non-scorable
        if category in NON_SCORABLE_CATEGORIES:
            continue
        if role in {"recognized_non_scorable", "inactive_non_scorable"}:
            continue
        if bool(row.get("is_blend_header")) or bool(row.get("blend_total_weight_only")):
            continue

        name = _ingredient_name(row)
        if not name and not category:
            continue

        # Check NP/zero-potency — these go to base, not actives.
        # Exception: probiotic strains with qty=0/NP in a confirmed probiotic
        # product — their CFU counts live in probiotic_data.total_cfu, not the
        # standard quantity field.  Without the is_probiotic_product gate,
        # Paradise-style products that embed 5 NP probiotic strains in a
        # whole-food base would misclassify Zinc/Quercetin as "probiotic".
        if _is_non_quantified(row):
            is_probiotic_strain = category in {"probiotic", "bacteria"} or (
                name and any(term in name for term in PROBIOTIC_TERMS)
            )
            # Only exempt NP probiotic strains when the product is a confirmed
            # probiotic WITH actual CFU data. Paradise-style products flag
            # is_probiotic_product=True because they embed NP probiotic strains
            # in every product's whole-food base — but total_cfu=0 reveals
            # these are decorative, not therapeutic.
            probiotic_data = product.get("probiotic_data", {})
            has_real_cfu = bool(probiotic_data.get("total_cfu"))
            is_probiotic_product = bool(probiotic_data.get("is_probiotic_product"))
            if is_probiotic_strain and is_probiotic_product and has_real_cfu:
                pass  # let it through — real probiotic product with CFU data
            else:
                non_quantified_rows.append(row)
                continue

        quantified_rows.append(row)
        counted_category = category or "uncategorized"
        category_counts[counted_category] = category_counts.get(counted_category, 0) + 1

        # Track canonical IDs for secondary type and category detection
        cid = _normalize_text(row.get("canonical_id") or row.get("iqm_parent_key") or "")
        if cid:
            canonical_ids.append(cid)

        # Probiotic counting
        if category in {"probiotic", "bacteria"}:
            probiotic_count += 1
        elif any(term in name for term in PROBIOTIC_TERMS):
            probiotic_count += 1

    active_count = len(quantified_rows)
    nq_count = len(non_quantified_rows)

    if nq_count > 0:
        reasons.append(f"excluded {nq_count} non-quantified base ingredients from classification")

    # Product name analysis
    product_name = _normalize_text(
        " ".join(str(product.get(k) or "") for k in ("product_name", "fullName", "bundleName"))
    )

    # Canonical ID sets
    cid_set = frozenset(canonical_ids)
    vitamin_ids = cid_set & _VITAMIN_CANONICAL_IDS
    mineral_ids = cid_set & _MINERAL_CANONICAL_IDS
    b_vitamin_ids = cid_set & _B_VITAMIN_IDS
    omega_ids = cid_set & _OMEGA_CANONICAL_IDS
    amino_ids = cid_set & _AMINO_ACID_IDS
    collagen_ids = cid_set & _COLLAGEN_IDS

    herb_count = category_counts.get("botanical", 0) + category_counts.get("herb", 0)
    vitamin_count = category_counts.get("vitamin", 0)
    mineral_count = category_counts.get("mineral", 0)

    # =========================================================================
    # CLASSIFICATION DECISION TREE
    # =========================================================================

    primary_type = "general_supplement"
    secondary_type = None
    confidence = 0.0

    # --- Probiotic ---
    probiotic_name_signal = any(term in product_name for term in PROBIOTIC_TERMS)
    probiotic_data = product.get("probiotic_data", {})
    # Require real CFU data — Paradise-style products set is_probiotic_product=True
    # even for Zinc/Quercetin because NP probiotic strains exist in the base.
    probiotic_flag = (
        bool(probiotic_data.get("is_probiotic_product"))
        and bool(probiotic_data.get("total_cfu"))
    )
    if (probiotic_flag or probiotic_count > 0 or probiotic_name_signal) and active_count > 0:
        probiotic_majority = probiotic_count >= max(1, ceil(active_count * 0.5))
        if active_count == 1 or probiotic_majority or (
            (probiotic_name_signal or probiotic_flag)
            and probiotic_count >= max(1, ceil(active_count * 0.25))
        ):
            primary_type = "probiotic"
            confidence = 0.9 if probiotic_majority else 0.7
            reasons.append(f"probiotic: {probiotic_count}/{active_count} strains")

    # --- Omega-3 / Fish Oil ---
    # Word-boundary check for short tokens (dha, epa) to avoid "ashwagan-dha" false positives
    elif omega_ids or _has_omega_name_signal(product_name):
        omega_signal = len(omega_ids)
        name_signal = any(t in product_name for t in ("omega", "fish oil", "krill", "cod liver"))
        if omega_signal > 0 or name_signal:
            primary_type = "omega_3"
            confidence = 0.95 if (omega_signal and name_signal) else 0.8
            reasons.append(f"omega-3: ids={list(omega_ids)}, name_match={name_signal}")

    # --- Functional name-based categories (sleep, immune, beauty, joint, fiber) ---
    # Checked early because name intent overrides composition-based inference.
    # E.g. "Hair Skin & Nails with Biotin" is beauty, not vitamin_mineral_combo.
    elif active_count >= 2 and _has_functional_name_signal(product_name):
        primary_type, confidence, reason = _detect_functional_name(product_name)
        reasons.append(reason)

    # --- Single nutrient (active_count == 1) ---
    elif active_count == 1:
        cid = canonical_ids[0] if canonical_ids else ""
        cat = list(category_counts.keys())[0] if category_counts else ""
        if cid in _VITAMIN_CANONICAL_IDS or cat == "vitamin":
            primary_type = "single_vitamin"
            confidence = 0.95
            reasons.append(f"single vitamin: {cid or cat}")
        elif cid in _MINERAL_CANONICAL_IDS or cat == "mineral":
            primary_type = "single_mineral"
            confidence = 0.95
            reasons.append(f"single mineral: {cid or cat}")
        elif cid in _AMINO_ACID_IDS or cat == "amino_acid":
            primary_type = "amino_acid"
            confidence = 0.9
            reasons.append(f"single amino acid: {cid or cat}")
        elif cat in ("herb", "botanical", "antioxidant"):
            primary_type = "herbal_botanical"
            confidence = 0.9
            reasons.append(f"single herbal/botanical: {cid or cat}")
        elif cid in _COLLAGEN_IDS:
            primary_type = "collagen"
            confidence = 0.9
            reasons.append(f"collagen: {cid}")
        else:
            primary_type = "general_supplement"
            confidence = 0.5
            reasons.append(f"single ingredient, uncategorized: {cid or cat}")

    # --- B-Complex ---
    elif (b_vitamin_ids and len(b_vitamin_ids) >= 3) or "b-complex" in product_name or "b complex" in product_name:
        # Must be primarily B-vitamins, not a full multivitamin
        non_b_vitamins = vitamin_ids - _B_VITAMIN_IDS
        non_b_minerals = mineral_ids
        if len(non_b_vitamins) <= 1 and len(non_b_minerals) <= 2:
            primary_type = "b_complex"
            confidence = 0.9 if "complex" in product_name else 0.75
            reasons.append(f"b-complex: {len(b_vitamin_ids)} B-vitamins, {len(non_b_vitamins)} non-B vitamins")
        else:
            primary_type = "multivitamin"
            confidence = 0.7
            reasons.append(f"multivitamin (b-complex + extras): {len(vitamin_ids)} vitamins + {len(mineral_ids)} minerals")

    # --- Multivitamin ---
    elif active_count >= 6 and len(vitamin_ids) + len(mineral_ids) >= 4 and (
        len(set(category_counts.keys()) - {"uncategorized"}) >= 3
        or (len(vitamin_ids) >= 3 and len(mineral_ids) >= 3)
        or any(t in product_name for t in ("multi", "daily vitamin", "one daily", "complete"))
    ):
        name_signal = any(t in product_name for t in ("multi", "daily vitamin", "one daily", "complete"))
        primary_type = "multivitamin"
        confidence = 0.95 if name_signal else 0.75
        reasons.append(f"multivitamin: {len(vitamin_ids)} vitamins, {len(mineral_ids)} minerals, {active_count} actives")

    # --- Vitamin + Mineral Combo (2-5 actives, mixed vitamins/minerals) ---
    elif 2 <= active_count <= 5 and (vitamin_ids or mineral_ids):
        vm_count = len(vitamin_ids) + len(mineral_ids)
        if vm_count >= active_count * 0.7:
            if mineral_ids and not vitamin_ids:
                primary_type = "single_mineral"
                confidence = 0.8
                reasons.append(f"mineral combo: {list(mineral_ids)}")
            elif vitamin_ids and not mineral_ids:
                primary_type = "single_vitamin"
                confidence = 0.8
                reasons.append(f"vitamin combo: {list(vitamin_ids)}")
            else:
                primary_type = "vitamin_mineral_combo"
                confidence = 0.8
                reasons.append(f"vitamin+mineral combo: {list(vitamin_ids | mineral_ids)}")
        elif herb_count > vm_count:
            primary_type = "herbal_botanical"
            confidence = 0.7
            reasons.append(f"herbal dominant: {herb_count} herbs vs {vm_count} vitamins/minerals")
        else:
            primary_type = "general_supplement"
            confidence = 0.5
            reasons.append(f"mixed targeted: {dict(category_counts)}")

    # --- Herbal blend (>60% herbs) ---
    elif active_count >= 2 and herb_count > active_count * 0.6:
        primary_type = "herbal_botanical"
        confidence = 0.85
        reasons.append(f"herbal blend: {herb_count}/{active_count} herbs")

    # --- Amino acid dominant ---
    elif amino_ids and len(amino_ids) >= active_count * 0.5:
        primary_type = "amino_acid"
        confidence = 0.8
        reasons.append(f"amino acid dominant: {list(amino_ids)}")

    # --- Collagen ---
    elif collagen_ids:
        primary_type = "collagen"
        confidence = 0.85
        reasons.append(f"collagen: {list(collagen_ids)}")

    # --- Functional category detection from product name ---
    elif active_count >= 2:
        primary_type, confidence, reason = _detect_functional_category(
            product_name, category_counts, active_count, herb_count,
            vitamin_count, mineral_count
        )
        if reason:
            reasons.append(reason)

    # --- Fallback for remaining ---
    elif active_count == 0:
        primary_type = "general_supplement"
        confidence = 0.0
        reasons.append("no quantified active ingredients")

    # =========================================================================
    # SECONDARY TYPE
    # =========================================================================
    if not secondary_type:
        secondary_type = _infer_secondary_type(canonical_ids, product_name, primary_type)

    # =========================================================================
    # DSLD productType cross-validation (confidence boost or flag)
    # =========================================================================
    dsld_agreement = _check_dsld_agreement(primary_type, dsld_product_type)
    if dsld_product_type:
        if dsld_agreement:
            confidence = min(1.0, confidence + 0.05)
            reasons.append(f"dsld_productType confirms: '{dsld_product_type}'")
        elif confidence < 0.7 and primary_type != "general_supplement":
            reasons.append(f"dsld_productType disagrees: '{dsld_product_type}' vs '{primary_type}'")

    # =========================================================================
    # PERCENTILE CATEGORY (derived from primary_type)
    # =========================================================================
    percentile_category = _derive_percentile_category(primary_type, secondary_type, product_name)

    return {
        "primary_type": primary_type,
        "secondary_type": secondary_type,
        "percentile_category": percentile_category,
        "classification_confidence": round(confidence, 2),
        "classification_reasons": reasons,
        "quantified_active_count": active_count,
        "non_quantified_base_count": nq_count,
        "category_breakdown": category_counts,
        "dsld_product_type": dsld_product_type or None,
    }


def _detect_functional_category(
    product_name: str,
    category_counts: dict[str, int],
    active_count: int,
    herb_count: int,
    vitamin_count: int,
    mineral_count: int,
) -> tuple[str, float, str]:
    """Detect functional categories from product name and composition."""

    # Check name-based functional signals
    if any(t in product_name for t in _SLEEP_NAME_TOKENS):
        return "sleep_support", 0.8, f"sleep name signal in '{product_name}'"

    if any(t in product_name for t in _IMMUNE_NAME_TOKENS):
        return "immune_support", 0.8, f"immune name signal in '{product_name}'"

    if any(t in product_name for t in _JOINT_NAME_TOKENS):
        return "joint_support", 0.8, f"joint name signal in '{product_name}'"

    if any(t in product_name for t in _BEAUTY_NAME_TOKENS):
        return "beauty_hair_skin_nails", 0.8, f"beauty name signal in '{product_name}'"

    if any(t in product_name for t in _FIBER_NAME_TOKENS):
        return "fiber_digestive", 0.75, f"fiber/digestive name signal in '{product_name}'"

    # Composition-based fallbacks
    if herb_count > active_count * 0.4:
        return "herbal_botanical", 0.6, f"herbal plurality: {herb_count}/{active_count}"

    if vitamin_count + mineral_count > active_count * 0.6:
        return "vitamin_mineral_combo", 0.5, f"vitamin/mineral plurality: {vitamin_count}v+{mineral_count}m/{active_count}"

    return "general_supplement", 0.3, f"no clear signal: {dict(category_counts)}"


def _infer_secondary_type(
    canonical_ids: list[str],
    product_name: str,
    primary_type: str,
) -> str | None:
    """Infer secondary_type from the dominant canonical ingredient or product name."""
    # For single-ingredient products, use the canonical ID directly
    if len(canonical_ids) == 1:
        cid = canonical_ids[0]
        if cid in _SECONDARY_TYPE_MAP:
            return _SECONDARY_TYPE_MAP[cid]

    # For multi-ingredient, check name signals
    name_secondary_map = {
        "zinc": "zinc",
        "magnesium": "magnesium",
        "vitamin d": "vitamin_d",
        "vitamin c": "vitamin_c",
        "biotin": "biotin",
        "ashwagandha": "ashwagandha",
        "turmeric": "turmeric_curcumin",
        "curcumin": "turmeric_curcumin",
        "berberine": "berberine",
        "elderberry": "elderberry",
        "melatonin": "melatonin",
        "collagen": "collagen",
        "glucosamine": "glucosamine",
        "quercetin": "quercetin",
        "coq10": "coq10",
        "iron": "iron",
        "calcium": "calcium",
        "selenium": "selenium",
        "creatine": "creatine",
    }
    for token, stype in name_secondary_map.items():
        if token in product_name:
            return stype

    # For multi-ingredient, use first canonical ID if it maps
    for cid in canonical_ids:
        if cid in _SECONDARY_TYPE_MAP:
            return _SECONDARY_TYPE_MAP[cid]

    return None


# ============================================================================
# DSLD productType CROSS-VALIDATION
# ============================================================================

# Maps DSLD langualCodeDescription → set of compatible primary_types
_DSLD_TYPE_COMPAT = {
    "vitamin": {"single_vitamin", "b_complex", "vitamin_mineral_combo"},
    "mineral": {"single_mineral", "vitamin_mineral_combo"},
    "multi-vitamin and mineral (mvm)": {"multivitamin"},
    "single vitamin and mineral": {"single_vitamin", "single_mineral", "vitamin_mineral_combo"},
    "botanical": {"herbal_botanical"},
    "botanical with nutrients": {"herbal_botanical", "immune_support", "sleep_support", "joint_support", "beauty_hair_skin_nails"},
    "fat/fatty acid": {"omega_3"},
    "amino acid/protein": {"amino_acid", "protein_powder"},
    "fiber and other nutrients": {"fiber_digestive"},
    "non-nutrient/non-botanical": {"general_supplement", "sleep_support", "joint_support", "beauty_hair_skin_nails"},
    "other combinations": set(),  # too vague to validate
}


def _check_dsld_agreement(primary_type: str, dsld_product_type: str) -> bool:
    """Check if our primary_type agrees with the DSLD productType."""
    if not dsld_product_type:
        return False
    compat = _DSLD_TYPE_COMPAT.get(dsld_product_type, None)
    if compat is None or len(compat) == 0:
        return False  # Unknown or "Other Combinations" — can't validate
    return primary_type in compat


# ============================================================================
# PERCENTILE CATEGORY DERIVATION
# ============================================================================

# Maps primary_type → percentile_category for peer comparison
_PERCENTILE_CATEGORY_MAP = {
    "single_vitamin": "single_vitamin",
    "single_mineral": "single_mineral",
    "vitamin_mineral_combo": "vitamin_mineral_combo",
    "multivitamin": "multivitamin",
    "b_complex": "b_complex",
    "omega_3": "fish_oil",
    "probiotic": "probiotic",
    "herbal_botanical": "herbal_botanical",
    "protein_powder": "protein_powder",
    "collagen": "collagen",
    "greens_powder": "greens_powder",
    "electrolyte": "electrolyte",
    "pre_workout": "pre_workout",
    "amino_acid": "amino_acid",
    "fiber_digestive": "fiber_digestive",
    "sleep_support": "sleep_support",
    "immune_support": "immune_support",
    "joint_support": "joint_support",
    "beauty_hair_skin_nails": "beauty_hair_skin_nails",
    "general_supplement": "general_supplement",
}


def _derive_percentile_category(
    primary_type: str,
    secondary_type: str | None,
    product_name: str,
) -> str:
    """Derive percentile_category from primary_type and secondary_type."""
    return _PERCENTILE_CATEGORY_MAP.get(primary_type, "general_supplement")


# ============================================================================
# CLASSIFICATION ROW ITERATOR (v2 — passes raw rows for NP filtering)
# ============================================================================

def _iter_classification_rows_v2(product: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Get classification rows, preferring ingredient_quality_data.

    Unlike v1, this returns the RAW rows without filtering — the caller
    handles NP/non-quantified filtering to partition into quantified vs base.
    """
    iqd = product.get("ingredient_quality_data", {})
    iqd_rows = _safe_list(iqd.get("ingredients"))
    if iqd_rows:
        return [row for row in iqd_rows if isinstance(row, dict)], "ingredient_quality_data"

    active_rows = _safe_list(product.get("activeIngredients"))
    return [row for row in active_rows if isinstance(row, dict)], "activeIngredients"
