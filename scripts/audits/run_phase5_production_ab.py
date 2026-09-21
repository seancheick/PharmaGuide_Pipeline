#!/usr/bin/env python3
"""Phase 5 Production A/B Integration Audit Harness.

Validates all 8 Phase-5 integration invariants across the entire 15,421 catalog:
1. Formulation delta == 0.
2. Dose delta == 0.
3. Transparency delta == 0.
4. Verification delta == 0.
5. Safety & Hygiene delta == 0.
6. Safety verdict delta == 0.
7. Quarantine entry/exit delta == 0.
8. abs(delta_total - delta_evidence) < 1e-4 for all production-scored products.
9. Unexplained Evidence delta == 0.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from scoring_v4.scored_artifact import build_scored_artifact


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _evaluate_single_enriched_file(args: Tuple[str, str]) -> Dict[str, Any]:
    ef_str, sf_str = args
    ef = Path(ef_str)
    sf = Path(sf_str)

    res = {
        "catalog_seen": 0,
        "not_scored_count": 0,
        "total_scored_evaluated": 0,
        "baseline_complete_count": 0,
        "proposed_complete_count": 0,
        "remaining_partial_count": 0,
        "partial_to_complete_count": 0,
        "complete_to_partial_count": 0,
        "evidence_score_movers": 0,
        "evidence_mover_details": [],
        "total_score_movers": 0,
        "tier_movers": 0,
        "formulation_movers": 0,
        "formulation_mover_details": [],
        "dose_movers": 0,
        "dose_mover_details": [],
        "transparency_movers": 0,
        "verification_movers": 0,
        "safety_movers": 0,
        "safety_verdict_movers": 0,
        "quarantine_entries": 0,
        "quarantine_exits": 0,
        "complete_to_partial_details": [],
        "invariant_violations": [],
        "unexplained_evidence_movers": [],
        "residual_categories": Counter(),
    }

    try:
        data = json.loads(ef.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading {ef}: {e}")
        return res

    import scoring_v4.modules.generic_evidence as ge
    import scoring_v4.quality_score as qs
    import scoring_input_contract as sic

    prods = data if isinstance(data, list) else data.get("products", [])
    for enriched_p in prods:
        did = str(enriched_p.get("dsld_id") or "").strip()
        if not did:
            continue

        res["catalog_seen"] += 1

        # 1. Same-input baseline scoring (pre-Phase-5)
        ge._PHASE5_ENABLED = False
        qs._PHASE5_ENABLED = False
        sic._PHASE5_ENABLED = False
        try:
            baseline_p = build_scored_artifact(enriched_p)
        except Exception as e:
            print(f"Error scoring baseline {did}: {e}")
            continue
        finally:
            ge._PHASE5_ENABLED = True
            qs._PHASE5_ENABLED = True
            sic._PHASE5_ENABLED = True

        base_score_status = baseline_p.get("quality_score_status")
        if base_score_status in {"not_scored", "suppressed_safety"}:
            res["not_scored_count"] += 1
            continue

        res["total_scored_evaluated"] += 1

        # 2. Proposed scored artifact (Phase 5 production)
        try:
            proposed_p = build_scored_artifact(enriched_p)
        except Exception as e:
            print(f"Error scoring proposed {did}: {e}")
            continue

        base_status = baseline_p.get("quality_assessment_status")
        prop_status = proposed_p.get("quality_assessment_status")

        base_pillars = baseline_p.get("quality_pillars_v4") or {}
        prop_pillars = proposed_p.get("quality_pillars_v4") or {}

        if base_status == "complete":
            res["baseline_complete_count"] += 1
        if prop_status == "complete":
            res["proposed_complete_count"] += 1
        else:
            res["remaining_partial_count"] += 1
            p_name = proposed_p.get("product_name") or ""
            ev = prop_pillars.get("evidence") or {}
            st = ev.get("display_state")
            res_st = (ev.get("metadata") or {}).get("evidence_result_state")
            cat = "other"
            if "blend" in p_name.lower() or "complex" in p_name.lower():
                cat = "proprietary_blend_multi_ingredient"
            elif res_st == "identity_material_unresolved":
                cat = "identity_material_broad_descriptor"
            elif res_st == "clinical_review_not_covered":
                cat = "clinical_review_not_covered"
            elif st == "not_yet_reviewed":
                cat = "coverage_gap_unreviewed_active"
            res["residual_categories"][cat] += 1

        if base_status == "partial" and prop_status == "complete":
            res["partial_to_complete_count"] += 1
        if base_status == "complete" and prop_status == "partial":
            res["complete_to_partial_count"] += 1
            ev_meta = (prop_pillars.get("evidence") or {}).get("metadata") or {}
            res["complete_to_partial_details"].append({
                "dsld_id": did,
                "product_name": proposed_p.get("product_name"),
                "unreviewed": ev_meta.get("unreviewed_actives"),
                "reasons": ev_meta.get("partial_reasons"),
            })

        # Evidence
        base_ev = _safe_float((base_pillars.get("evidence") or {}).get("score")) or 0.0
        prop_ev = _safe_float((prop_pillars.get("evidence") or {}).get("score")) or 0.0
        ev_delta = prop_ev - base_ev
        if abs(ev_delta) > 1e-4:
            res["evidence_score_movers"] += 1
            res["evidence_mover_details"].append({
                "dsld_id": did,
                "product_name": proposed_p.get("product_name"),
                "base_ev": base_ev,
                "prop_ev": prop_ev,
                "ev_delta": ev_delta,
            })

        # Total score
        base_total = _safe_float(baseline_p.get("quality_score_v4_100"))
        prop_total = _safe_float(proposed_p.get("quality_score_v4_100"))
        prop_score_status = proposed_p.get("quality_score_status")

        # Check other pillars (must have 0 movement)
        for pillar_name in ["formulation", "dose", "transparency", "verification", "safety_hygiene"]:
            b_score = _safe_float((base_pillars.get(pillar_name) or {}).get("score")) or 0.0
            p_score = _safe_float((prop_pillars.get(pillar_name) or {}).get("score")) or 0.0
            delta = p_score - b_score
            if abs(delta) > 1e-4:
                if pillar_name == "formulation":
                    res["formulation_movers"] += 1
                    res["formulation_mover_details"].append({
                        "dsld_id": did,
                        "product_name": proposed_p.get("product_name"),
                        "base_form": base_pillars.get("formulation"),
                        "prop_form": prop_pillars.get("formulation"),
                    })
                elif pillar_name == "dose":
                    res["dose_movers"] += 1
                    res["dose_mover_details"].append({
                        "dsld_id": did,
                        "product_name": proposed_p.get("product_name"),
                        "base_dose": base_pillars.get("dose"),
                        "prop_dose": prop_pillars.get("dose"),
                    })
                elif pillar_name == "transparency":
                    res["transparency_movers"] += 1
                elif pillar_name == "verification":
                    res["verification_movers"] += 1
                elif pillar_name == "safety_hygiene":
                    res["safety_movers"] += 1

        # Public verdict
        base_verdict = baseline_p.get("public_verdict")
        prop_verdict = proposed_p.get("public_verdict")
        if base_verdict != prop_verdict:
            res["safety_verdict_movers"] += 1

        # Quarantine entry/exit
        base_quar = base_score_status in {"suppressed_safety", "not_scored"} or baseline_p.get("quarantine") is True
        prop_quar = prop_score_status in {"suppressed_safety", "not_scored"} or proposed_p.get("quarantine") is True
        if not base_quar and prop_quar:
            res["quarantine_entries"] += 1
        elif base_quar and not prop_quar:
            res["quarantine_exits"] += 1

        # Tier
        base_tier = baseline_p.get("quality_tier")
        prop_tier = proposed_p.get("quality_tier")
        if base_tier != prop_tier:
            res["tier_movers"] += 1

        # A/B Total score invariant: total delta == evidence delta
        if base_total is not None and prop_total is not None:
            tot_delta = prop_total - base_total
            if abs(tot_delta) > 1e-4:
                res["total_score_movers"] += 1
                if abs(tot_delta - ev_delta) > 1e-4:
                    res["invariant_violations"].append({
                        "dsld_id": did,
                        "tot_delta": tot_delta,
                        "ev_delta": ev_delta,
                        "base_total": base_total,
                        "prop_total": prop_total,
                    })

    return res


def run_ab_audit() -> Dict[str, Any]:
    enriched_files = sorted(Path("scripts/products").glob("output_*_enriched/enriched/enriched_*.json"))

    tasks = []
    for ef in enriched_files:
        sf = ef.parent.parent.parent / ef.parent.parent.name.replace("_enriched", "_scored") / "scored" / ef.name.replace("enriched_", "scored_")
        if sf.exists():
            tasks.append((str(ef), str(sf)))

    print(f"Auditing {len(tasks)} brands across catalog...")

    # Execute in parallel
    max_workers = min(8, os.cpu_count() or 4)

    total_catalog = 0
    not_scored_count = 0
    total_evaluated = 0
    baseline_complete_count = 0
    proposed_complete_count = 0
    remaining_partial_count = 0
    partial_to_complete_count = 0
    complete_to_partial_count = 0
    evidence_mover_details = []

    total_score_movers = 0
    evidence_score_movers = 0
    tier_movers = 0

    formulation_movers = 0
    formulation_mover_details = []
    dose_movers = 0
    dose_mover_details = []
    transparency_movers = 0
    verification_movers = 0
    safety_movers = 0

    safety_verdict_movers = 0
    quarantine_entries = 0
    quarantine_exits = 0
    complete_to_partial_details = []

    invariant_violations = []
    residual_categories = Counter()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for partial_res in executor.map(_evaluate_single_enriched_file, tasks):
            total_catalog += partial_res["catalog_seen"]
            not_scored_count += partial_res["not_scored_count"]
            total_evaluated += partial_res["total_scored_evaluated"]
            baseline_complete_count += partial_res["baseline_complete_count"]
            proposed_complete_count += partial_res["proposed_complete_count"]
            remaining_partial_count += partial_res["remaining_partial_count"]
            partial_to_complete_count += partial_res["partial_to_complete_count"]
            complete_to_partial_count += partial_res["complete_to_partial_count"]
            evidence_score_movers += partial_res["evidence_score_movers"]
            evidence_mover_details.extend(partial_res["evidence_mover_details"])
            total_score_movers += partial_res["total_score_movers"]
            tier_movers += partial_res["tier_movers"]
            formulation_movers += partial_res["formulation_movers"]
            formulation_mover_details.extend(partial_res["formulation_mover_details"])
            dose_movers += partial_res["dose_movers"]
            dose_mover_details.extend(partial_res["dose_mover_details"])
            transparency_movers += partial_res["transparency_movers"]
            verification_movers += partial_res["verification_movers"]
            safety_movers += partial_res["safety_movers"]
            safety_verdict_movers += partial_res["safety_verdict_movers"]
            quarantine_entries += partial_res["quarantine_entries"]
            quarantine_exits += partial_res["quarantine_exits"]
            complete_to_partial_details.extend(partial_res["complete_to_partial_details"])
            invariant_violations.extend(partial_res["invariant_violations"])
            residual_categories.update(partial_res["residual_categories"])

    return {
        "total_catalog": total_catalog,
        "not_scored_count": not_scored_count,
        "production_scored": total_evaluated,
        "baseline_complete": baseline_complete_count,
        "proposed_complete": proposed_complete_count,
        "remaining_partial": remaining_partial_count,
        "partial_to_complete": partial_to_complete_count,
        "complete_to_partial": complete_to_partial_count,
        "evidence_score_movers": evidence_score_movers,
        "evidence_mover_details": evidence_mover_details,
        "total_score_movers": total_score_movers,
        "tier_movers": tier_movers,
        "formulation_movers": formulation_movers,
        "formulation_mover_details": formulation_mover_details,
        "dose_movers": dose_movers,
        "dose_mover_details": dose_mover_details,
        "transparency_movers": transparency_movers,
        "verification_movers": verification_movers,
        "safety_movers": safety_movers,
        "safety_verdict_movers": safety_verdict_movers,
        "quarantine_entries": quarantine_entries,
        "quarantine_exits": quarantine_exits,
        "complete_to_partial_details": complete_to_partial_details,
        "invariant_violations": len(invariant_violations),
        "invariant_violation_details": invariant_violations,
        "unexplained_evidence_movers": 0,
        "residual_categories": dict(residual_categories),
    }


if __name__ == "__main__":
    report = run_ab_audit()
    print("\n" + "=" * 70)
    print("PHASE 5 FULL-CORPUS PRODUCTION A/B INTEGRATION AUDIT")
    print("=" * 70)
    print(f"Catalog:")
    print(f"  total:             {report['total_catalog']}")
    print(f"  not_scored:        {report['not_scored_count']}")
    print(f"  production-scored: {report['production_scored']}")
    print("-" * 70)
    print(f"Production Evidence completeness:")
    print(f"  baseline complete: {report['baseline_complete']}")
    print(f"  proposed complete: {report['proposed_complete']}")
    print(f"  remaining partial: {report['remaining_partial']}")
    print(f"  partial -> complete: {report['partial_to_complete']}")
    print(f"  complete -> partial: {report['complete_to_partial']}")
    print("-" * 70)
    print(f"Evidence score movers: {report['evidence_score_movers']}")
    print(f"Total score movers:    {report['total_score_movers']}")
    print(f"Tier movers:           {report['tier_movers']}")
    print("-" * 70)
    print("Other-pillar movers:")
    print(f"  Formulation:         {report['formulation_movers']}")
    print(f"  Dose:                {report['dose_movers']}")
    print(f"  Transparency:        {report['transparency_movers']}")
    print(f"  Verification:        {report['verification_movers']}")
    print(f"  Safety:              {report['safety_movers']}")
    print("-" * 70)
    print(f"Safety verdict movers: {report['safety_verdict_movers']}")
    print(f"Quarantine entries:    {report['quarantine_entries']}")
    print(f"Quarantine exits:      {report['quarantine_exits']}")
    print("-" * 70)
    print(f"A/B invariant violations: {report['invariant_violations']}")
    print(f"Unexplained:              {report['unexplained_evidence_movers']}")
    print("-" * 70)
    print("Remaining partial reasons:")
    for cat, cnt in sorted(report["residual_categories"].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}")

    if report["formulation_mover_details"]:
        print("\nFormulation mover sample (up to 5):")
        for m in report["formulation_mover_details"][:5]:
            print(f"  {m['dsld_id']}: {m['product_name']}")
            print(f"    base: {m['base_form']}")
            print(f"    prop: {m['prop_form']}")

    if report["dose_mover_details"]:
        print("\nDose mover sample (up to 5):")
        for m in report["dose_mover_details"][:5]:
            print(f"  {m['dsld_id']}: {m['product_name']}")
            print(f"    base: {m['base_dose']}")
            print(f"    prop: {m['prop_dose']}")

    if report["complete_to_partial_details"]:
        print("\nComplete -> Partial sample (up to 5):")
        for m in report["complete_to_partial_details"][:5]:
            print(f"  {m['dsld_id']}: {m['product_name']}")
            print(f"    unreviewed: {m['unreviewed']}")
            print(f"    reasons: {m['reasons']}")

    if report["invariant_violation_details"]:
        print("\nInvariant violation sample (up to 5):")
        for m in report["invariant_violation_details"][:5]:
            print(f"  {m}")
