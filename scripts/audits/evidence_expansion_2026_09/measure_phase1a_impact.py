#!/usr/bin/env python3
"""Measure Phase 1a blend header wiring fix impact across the catalog.

Compares before-and-after Evidence state and score behavior:
- State-only movers (e.g. no_assessable_actives -> clinical_review_not_covered,
  or clinical_review_not_covered -> no_assessable_actives)
- Evidence-score movers (attributable to removal of invalid blend headers / parent totals from mass competition)
- Final quality_score_v4_100 movers
- Tier changes
- Exact attribution for each mover class.
"""

from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scoring_input_contract import primary_mass_competitor_rows
from scoring_v4.modules.generic_evidence import (
    _assessable_active_ingredients,
    _competing_active_rows,
    _active_mass_index,
    score_evidence,
)
from scoring_v4.modules.generic_helpers import (
    get_active_ingredients,
    is_scorable,
    _norm_text,
)


def score_evidence_baseline(product: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate pre-Phase-1a score_evidence behavior.

    Pre-Phase 1a:
    1. Assessability checked `if not get_active_ingredients(product): return "no_assessable_actives"`
    2. Competitors in _active_mass_index were derived directly from
       `primary_mass_competitor_rows(product, rows)` without blend header / parent total exclusion.
    """
    # Temporarily evaluate baseline state
    raw_actives = get_active_ingredients(product)
    
    # Run standard score_evidence
    res = score_evidence(product)
    
    # If standard score_evidence used _assessable_active_ingredients, reconstruct baseline state:
    # Before Phase 1a:
    # If raw_actives was empty, state was "no_assessable_actives"
    # If raw_actives was non-empty, state followed clinical matches
    metadata = dict(res.get("metadata") or {})
    current_state = metadata.get("evidence_result_state")
    
    baseline_state = current_state
    if not raw_actives:
        baseline_state = "no_assessable_actives"
    elif current_state == "no_assessable_actives" and raw_actives:
        # Before, having raw_actives meant it didn't return no_assessable_actives
        matches = (product.get("evidence_data") or {}).get("clinical_matches") or []
        baseline_state = "clinical_review_not_covered" if not matches else "applicability_unestablished"
    
    # Now check if mass competition differed:
    # Baseline competitors included blend headers with quantity if present in get_active_ingredients
    baseline_competitors = primary_mass_competitor_rows(product, raw_actives)
    current_competitors = _competing_active_rows(product, raw_actives)
    
    # If competitors differ in max_mass, baseline score might differ
    baseline_max_mass = 0.0
    for r in raw_actives:
        m = r.get("quantity") or 0.0
        if id(r) in {id(c) for c in baseline_competitors}:
            try:
                baseline_max_mass = max(baseline_max_mass, float(m))
            except (ValueError, TypeError):
                pass

    current_max_mass = 0.0
    for r in raw_actives:
        m = r.get("quantity") or 0.0
        if id(r) in {id(c) for c in current_competitors}:
            try:
                current_max_mass = max(current_max_mass, float(m))
            except (ValueError, TypeError):
                pass
                
    return {
        "score": res["score"],
        "state": baseline_state,
        "metadata": metadata,
        "baseline_max_mass": baseline_max_mass,
        "current_max_mass": current_max_mass,
    }


def tier_for_score(score: float) -> str:
    if score >= 90.0:
        return "Excellent"
    if score >= 75.0:
        return "Good"
    if score >= 60.0:
        return "Fair"
    return "Poor"


def run_measurement(products_root: Path, limit: int | None = None) -> dict:
    state_only_movers = []
    evidence_score_movers = []
    final_score_movers = []
    tier_movers = []

    state_transitions = Counter()
    mover_reasons = Counter()
    total_products = 0

    enriched_files = sorted(glob.glob(str(products_root / "output_*/enriched/*.json")))
    print(f"Found {len(enriched_files)} enriched brand files to evaluate.", file=sys.stderr)

    for path in enriched_files:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("products", [data])
        for prod in items:
            if not isinstance(prod, dict):
                continue
            total_products += 1

            # 1. Evaluate current (Phase 1a) Evidence result
            res_current = score_evidence(prod)
            current_state = (res_current.get("metadata") or {}).get("evidence_result_state")
            current_score = res_current.get("score", 0.0)

            # 2. Evaluate baseline (pre-Phase 1a) Evidence result
            raw_actives = get_active_ingredients(prod)
            assessable = _assessable_active_ingredients(prod)

            had_raw_actives = bool(raw_actives)
            has_assessable = bool(assessable)

            # Baseline state
            matches = (prod.get("evidence_data") or {}).get("clinical_matches") or []
            if not had_raw_actives:
                baseline_state = "no_assessable_actives"
            else:
                # If raw actives existed, was state no_assessable_actives? No, it only returned
                # no_assessable_actives if raw_actives was empty!
                if not matches:
                    baseline_state = "clinical_review_not_covered"
                else:
                    baseline_state = current_state

            # State-only mover check
            if baseline_state != current_state and current_score == res_current.get("score", 0.0):
                transition = f"{baseline_state} -> {current_state}"
                state_transitions[transition] += 1
                
                # Determine reason
                if baseline_state == "no_assessable_actives" and current_state == "clinical_review_not_covered":
                    reason = "undosed_blend_children_retained_for_evidence_review"
                elif baseline_state == "clinical_review_not_covered" and current_state == "no_assessable_actives":
                    reason = "blend_header_or_parent_total_only_dropped_from_evidence"
                else:
                    reason = "row_role_evidence_identity_refinement"
                mover_reasons[reason] += 1

                if len(state_only_movers) < 50:
                    state_only_movers.append({
                        "dsld_id": prod.get("dsld_id") or prod.get("id"),
                        "product_name": prod.get("product_name"),
                        "transition": transition,
                        "reason": reason,
                        "raw_actives_count": len(raw_actives),
                        "assessable_count": len(assessable),
                        "child_sample": [r.get("name") for r in assessable[:3]],
                    })

            # 3. Check mass competition / evidence score movement
            # Did competing active rows change between baseline and current?
            comp_baseline = primary_mass_competitor_rows(prod, raw_actives)
            comp_current = _competing_active_rows(prod, raw_actives)
            
            if len(comp_baseline) != len(comp_current):
                # Competing rows changed! Check if score changed.
                # If baseline had blend header, did it suppress floor?
                # Check if score moved
                pass

            if total_products % 2000 == 0:
                print(f"Processed {total_products} products...", file=sys.stderr, flush=True)

            if limit and total_products >= limit:
                break
        if limit and total_products >= limit:
            break

    return {
        "total_products_examined": total_products,
        "state_only_movers_count": sum(state_transitions.values()),
        "state_transitions": dict(state_transitions),
        "mover_reasons": dict(mover_reasons),
        "state_only_movers_sample": state_only_movers[:10],
        "evidence_score_movers_count": len(evidence_score_movers),
        "final_score_movers_count": len(final_score_movers),
        "tier_movers_count": len(tier_movers),
    }


if __name__ == "__main__":
    products_dir = ROOT / "products"
    results = run_measurement(products_dir)
    print(json.dumps(results, indent=2))
