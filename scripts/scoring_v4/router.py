"""v4 class router — decides which module scores a product.

Priority order (intentionally identical to score_supplements._b5_class_for_product
where the two overlap, but a separate decision surface — v4 routes among
the SCORING modules `probiotic / multi_or_prenatal / generic`, while B5
routes among the OPACITY classes `probiotic / multi_or_prenatal /
sports_active / generic`; sports_active doesn't get its own v4 module
because sports stacks fall through generic with class-specific opacity
already handled at B5):

  1. supp_type == "probiotic"      → probiotic       (strongest signal)
  2. supp_type == "multivitamin"   → multi_or_prenatal
  3. product name contains prenatal/pregnancy/etc. → multi_or_prenatal
     (Prenatal DHA / Prenatal Probiotic style products)
  4. primary_category == "multivitamin"           → multi_or_prenatal
     (specialty/targeted enricher classification + multivit category)
  5. fall through                                  → generic

Omega-3 / fish-oil routes to `generic` until the P1.5 decision gate
(does generic handle omega rank-order acceptably?). Sports products
also route to generic — their distinguishing opacity behavior is
already covered by the B5 class multiplier (`sports_active` 1.5x).
"""

from __future__ import annotations

import re
from typing import Any, Dict

VALID_CLASSES = ("generic", "probiotic", "multi_or_prenatal")

_PRENATAL_KEYWORDS = re.compile(
    r"\b(prenatal|pregnancy|pre-natal|expecting|maternal|gestation)\b",
    re.IGNORECASE,
)


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

    # Priority 5: generic (v3 single-nutrient / specialty / targeted /
    # herbal / omega-3 / sports — generic handles all until later
    # phases peel them off).
    return "generic"
