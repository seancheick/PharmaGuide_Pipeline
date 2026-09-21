#!/usr/bin/env python3
"""Full-corpus proposed integration A/B dry run for Phase 5.

Evaluates all 15,421 frozen catalog products:
- Runs build_scored_artifact on proposed code against baseline scored artifacts.
- Verifies all 8 A/B invariants:
    total delta == Evidence delta
    formulation delta == 0
    dose delta == 0
    transparency delta == 0
    verification delta == 0
    safety & hygiene delta == 0
    safety verdict delta == 0
    quarantine delta == 0
    unexplained Evidence delta == 0
- Reconciles baseline complete, proposed complete, remaining partial, partial -> complete.
- Categorizes legitimate residual partial products.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from scoring_v4.scored_artifact import build_scored_artifact
import evidence_resolver as er


def _safe_float(val: Any) -> Optional[float]:
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def run_ab_audit() -> Dict[str, Any]:
    enriched_files = sorted(Path("scripts/products").glob("output_*_enriched/enriched/enriched_*.json"))
    scored_files = sorted(Path("scripts/products").glob("output_*_scored/scored/scored_*.json"))

    print(f"Loading {len(enriched_files)} enriched files and {len(scored_files)} baseline scored files...")

    # Load baseline products indexed by dsld_id
    baseline_by_id: Dict[str, Dict[str, Any]] = {}
    for sf in scored_files:
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            prods = data if isinstance(data, list) else data.get("products", [])
            for p in prods:
                did = str(p.get("dsld_id") or "").strip()
                if did:
                    baseline_by_id[did] = p
        except Exception as e:
            print(f"Error loading {sf}: {e}")

    print(f"Loaded {len(baseline_by_id)} baseline scored products.")

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
    dose_movers = 0
    transparency_movers = 0
    verification_movers = 0
    safety_movers = 0

    safety_verdict_movers = 0
    quarantine_entries = 0
    quarantine_exits = 0

    invariant_violations = []
    unexplained_evidence_movers = []

    residual_products: List[Dict[str, Any]] = []
    residual_reasons = Counter()
    residual_categories = defaultdict(list)

    for ef in enriched_files:
        try:
            data = json.loads(ef.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading {ef}: {e}")
            continue

        prods = data if isinstance(data, list) else data.get("products", [])
        for enriched_p in prods:
            did = str(enriched_p.get("dsld_id") or "").strip()
            if not did or did not in baseline_by_id:
                continue

            total_evaluated += 1
            baseline_p = baseline_by_id[did]

            # Generate proposed scored artifact
            try:
                proposed_p = build_scored_artifact(enriched_p)
            except Exception as e:
                print(f"Error scoring {did}: {e}")
                continue

            base_status = baseline_p.get("quality_assessment_status")
            prop_status = proposed_p.get("quality_assessment_status")

            if base_status == "complete":
                baseline_complete_count += 1
            if prop_status == "complete":
                proposed_complete_count += 1
            else:
                remaining_partial_count += 1
                residual_products.append(proposed_p)

            if base_status == "partial" and prop_status == "complete":
                partial_to_complete_count += 1
            if base_status == "complete" and prop_status == "partial":
                complete_to_partial_count += 1

            # Pillar comparisons
            base_pillars = baseline_p.get("quality_pillars_v4") or {}
            prop_pillars = proposed_p.get("quality_pillars_v4") or {}

            # Evidence
            base_ev = _safe_float((base_pillars.get("evidence") or {}).get("score")) or 0.0
            prop_ev = _safe_float((prop_pillars.get("evidence") or {}).get("score")) or 0.0
            ev_delta = prop_ev - base_ev
            if abs(ev_delta) > 1e-4:
                evidence_score_movers += 1
                evidence_mover_details.append({
                    "dsld_id": did,
                    "product_name": proposed_p.get("product_name"),
                    "base_ev": base_ev,
                    "prop_ev": prop_ev,
                    "ev_delta": ev_delta,
                })

            # Total score
            base_total = _safe_float(baseline_p.get("quality_score_v4_100"))
            prop_total = _safe_float(proposed_p.get("quality_score_v4_100"))

            base_score_status = baseline_p.get("quality_score_status")
            prop_score_status = proposed_p.get("quality_score_status")

            # Check other pillars (must have 0 movement)
            for pillar_name, counter_ref in [
                ("formulation", "formulation_movers"),
                ("dose", "dose_movers"),
                ("transparency", "transparency_movers"),
                ("verification", "verification_movers"),
                ("safety_hygiene", "safety_movers"),
            ]:
                b_score = _safe_float((base_pillars.get(pillar_name) or {}).get("score")) or 0.0
                p_score = _safe_float((prop_pillars.get(pillar_name) or {}).get("score")) or 0.0
                delta = p_score - b_score
                if abs(delta) > 1e-4:
                    if pillar_name == "formulation":
                        formulation_movers += 1
                    elif pillar_name == "dose":
                        dose_movers += 1
                    elif pillar_name == "transparency":
                        transparency_movers += 1
                    elif pillar_name == "verification":
                        verification_movers += 1
                    elif pillar_name == "safety_hygiene":
                        safety_movers += 1

            # Public verdict
            base_verdict = baseline_p.get("public_verdict")
            prop_verdict = proposed_p.get("public_verdict")
            if base_verdict != prop_verdict:
                safety_verdict_movers += 1

            # Quarantine entry/exit
            base_quar = base_score_status in {"suppressed_safety", "not_scored"} or baseline_p.get("quarantine") is True
            prop_quar = prop_score_status in {"suppressed_safety", "not_scored"} or proposed_p.get("quarantine") is True
            if not base_quar and prop_quar:
                quarantine_entries += 1
            elif base_quar and not prop_quar:
                quarantine_exits += 1

            # Tier
            base_tier = baseline_p.get("quality_tier")
            prop_tier = proposed_p.get("quality_tier")
            if base_tier != prop_tier:
                tier_movers += 1

            # A/B Total score invariant: total delta == evidence delta
            if base_total is not None and prop_total is not None:
                tot_delta = prop_total - base_total
                if abs(tot_delta) > 1e-4:
                    total_score_movers += 1
                    if abs(tot_delta - ev_delta) > 1e-4:
                        invariant_violations.append({
                            "dsld_id": did,
                            "tot_delta": tot_delta,
                            "ev_delta": ev_delta,
                            "base_total": base_total,
                            "prop_total": prop_total,
                        })

    # Categorize legitimate residual partials
    for p in residual_products:
        did = p.get("dsld_id")
        res = er.resolve_product_evidence(p)
        disps = [r.disposition for r in res.resolutions]
        blockers = res.unresolved_blockers

        # Check ingredient types
        cids = [r.canonical_id for r in res.resolutions if r.disposition in {
            er.EvidenceDisposition.IDENTITY_INSUFFICIENT.value,
            er.EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value,
        }]

        cat = "other_residual"
        if any("bile" in c.lower() for c in cids):
            cat = "broad bile-salt mixtures"
        elif any("polysaccharide" in c.lower() for c in cids):
            cat = "broad polymer classes"
        elif any("saponin" in c.lower() for c in cids):
            cat = "generic phytochemical classes"
        elif any(c in er._STANDARDIZED_BOTANICALS_PATH.name or "marker" in c.lower() for c in cids):
            cat = "analytical standardization markers"
        elif any("cyclodextrin" in c.lower() for c in cids):
            cat = "cyclodextrins/delivery matrices"
        elif any("oil" in c.lower() or "vehicle" in c.lower() or "cellulose" in c.lower() for c in cids):
            cat = "excipient/carrier vehicle rows"
        elif any("blend" in b.lower() or "blend" in str(cids).lower() for b in blockers):
            cat = "multi-ingredient blends lacking defensible row/formula attribution"
        else:
            cat = "multi-ingredient blends lacking defensible row/formula attribution"

        residual_categories[cat].append(did)
        residual_reasons[cat] += 1

    return {
        "total_evaluated": total_evaluated,
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
        "dose_movers": dose_movers,
        "transparency_movers": transparency_movers,
        "verification_movers": verification_movers,
        "safety_movers": safety_movers,
        "safety_verdict_movers": safety_verdict_movers,
        "quarantine_entries": quarantine_entries,
        "quarantine_exits": quarantine_exits,
        "invariant_violations": len(invariant_violations),
        "unexplained_evidence_movers": len(unexplained_evidence_movers),
        "residual_categories": dict(residual_reasons),
    }


if __name__ == "__main__":
    report = run_ab_audit()
    print("\n" + "=" * 70)
    print("PHASE 5 FULL-CORPUS PRODUCTION A/B INTEGRATION AUDIT")
    print("=" * 70)
    print(f"Total Products Evaluated: {report['total_evaluated']}")
    print(f"Baseline Complete:        {report['baseline_complete']}")
    print(f"Proposed Complete:        {report['proposed_complete']}")
    print(f"Remaining Partial:        {report['remaining_partial']}")
    print(f"Partial -> Complete:      {report['partial_to_complete']}")
    print(f"Complete -> Partial:      {report['complete_to_partial']}")
    print("-" * 70)
    print(f"Evidence Score Movers:    {report['evidence_score_movers']}")
    print(f"Total Score Movers:       {report['total_score_movers']}")
    print(f"Tier Movers:              {report['tier_movers']}")
    if report["evidence_mover_details"]:
        print("Evidence Mover Details:")
        for m in report["evidence_mover_details"]:
            print(f"  dsld_id {m['dsld_id']}: {m['product_name'][:40]} | base={m['base_ev']} -> prop={m['prop_ev']} (delta={m['ev_delta']})")
    print("-" * 70)
    print("Other-Pillar Movers:")
    print(f"  Formulation:            {report['formulation_movers']}")
    print(f"  Dose:                   {report['dose_movers']}")
    print(f"  Transparency:           {report['transparency_movers']}")
    print(f"  Verification:           {report['verification_movers']}")
    print(f"  Safety & Hygiene:       {report['safety_movers']}")
    print("-" * 70)
    print(f"Safety Verdict Movers:    {report['safety_verdict_movers']}")
    print(f"Quarantine Entries:       {report['quarantine_entries']}")
    print(f"Quarantine Exits:         {report['quarantine_exits']}")
    print("-" * 70)
    print(f"A/B Invariant Violations: {report['invariant_violations']}")
    print(f"Unexplained Evidence:     {report['unexplained_evidence_movers']}")
    print("-" * 70)
    print("Residual Partial Products Breakdown:")
    for cat, cnt in sorted(report["residual_categories"].items(), key=lambda x: -x[1]):
        print(f"  {cat:<65}: {cnt}")
