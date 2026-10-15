"""v4 fiber/digestive formulation adapter."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from scoring_v4.modules.fiber_digestive_helpers import (
    canonical,
    COMPATIBLE_GUAR_CANONICALS,
    fiber_rows,
    has_fiber_context,
    GUAR_CANONICALS,
    is_hydrolyzed_guar_fiber_row,
    product_name_text,
    row_text,
)
from scoring_v4.modules.generic_formulation import (
    score_formulation as score_generic_formulation,
    shared_formulation_penalty_detail,
)
from scoring_v4.modules.generic_helpers import (
    _norm_text,
    _safe_dict,
    _safe_list,
)


from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "fiber_digestive")["fiber_digestive"]


DIMENSION_CAP = _FVM["dimension_cap"]
PHASE_MARKER = "P1.8_fiber_digestive_formulation_v1"


def score_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(product, dict):
        product = {}

    rows = fiber_rows(product)
    if not rows and not has_fiber_context(product):
        return score_generic_formulation(product)

    source_quality, source_class = _source_quality(rows, product)

    # V4.1 Step 4: disclosure belongs to Transparency, and focus, route-base
    # and name-based practicality bonuses are retired. A stimulant laxative
    # (senna, cascara, aloe latex) is a banned_recalled watchlist/high-risk
    # identity: the safety gate reports it and the formula-checks pillar
    # charges it once when the match is confirmed.
    components: Dict[str, float] = {
        "fiber_source_quality": round(source_quality, 4),
    }

    shared = shared_formulation_penalty_detail(product)
    penalties: Dict[str, float] = dict(shared["penalties"])

    positive = sum(components.values())
    penalty_total = sum(abs(float(v or 0.0)) for v in penalties.values())
    score = max(0.0, min(DIMENSION_CAP, positive - penalty_total))

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "fiber_profile_applied": True,
            "fiber_source_class": source_class,
            "fiber_rows_evaluated": len(rows),
            # Spread the WHOLE shared metadata rather than cherry-picking
            # one key. Picking only "dietary_sugar" silently dropped
            # "inactive_penalty_details" -- the ledger build_final_db needs
            # to colour "Other ingredients" dots. 5,116 products carried a
            # real B1 harmful-additive charge while shipping an empty
            # ledger, so every one of their additive dots rendered green.
            **shared["metadata"],
        },
    }


def _source_quality(rows: List[Dict[str, Any]], product: Dict[str, Any]) -> tuple[float, str]:
    text = " ".join(row_text(row) for row in rows) + " " + product_name_text(product)
    canons = {canonical(row) for row in rows}
    if {"psyllium", "psyllium_husk"} & canons or "psyllium" in text:
        return 12.0, "psyllium"
    if any(is_hydrolyzed_guar_fiber_row(row) for row in rows):
        return 10.0, "hydrolyzed_guar_fiber"
    if any(term in text for term in ("acacia", "glucomannan", "konjac", "beta glucan")):
        return 10.0, "soluble_fiber"
    if any(_has_row_owned_guar_signal(row) for row in rows):
        return 10.0, "soluble_fiber"
    if any(term in text for term in ("inulin", "prebiotic", "resistant starch")):
        return 9.0, "prebiotic_fiber"
    if rows:
        return 7.0, "generic_fiber"
    return 3.0, "fiber_claim_without_mapped_fiber"


def _has_row_owned_guar_signal(row: Dict[str, Any]) -> bool:
    cid = canonical(row)
    if cid in GUAR_CANONICALS:
        return True
    if cid not in COMPATIBLE_GUAR_CANONICALS:
        return False
    owned_text = " ".join(
        _norm_text(part)
        for part in (
            row.get("name"),
            row.get("raw_source_text"),
            *[
                form.get("name")
                for form in _safe_list(row.get("forms"))
                if isinstance(form, dict)
            ],
            *[
                form.get("name")
                for form in _safe_list(_safe_dict(row.get("raw_taxonomy")).get("forms"))
                if isinstance(form, dict)
            ],
        )
    )
    return bool(re.search(r"\bguar\b", owned_text))
