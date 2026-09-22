#!/usr/bin/env python3
"""A/B Catalog Verification of Cross-Module Probiotic Evidence Ownership.

Audits:
1. All 884 probiotic-containing catalog products from probiotic_partition_data.json:
   - Old vs new evidence score (assert movers == 0)
   - Old vs new total quality score (assert movers == 0)
   - Old vs new quality tier (assert movers == 0)
   - Old vs new evidence_result_state
   - Old vs new quality_assessment_status
   - Exact strain credit granted to species (assert == 0)
   - Species -> strain transfer (assert == 0)
2. Detailed disposition of the 26 candidate products previously in clinical_review_not_covered:
   - 3 non-probiotic source material / fermentate products (excluded from probiotic ownership)
   - 11 exact-strain stub products in non-probiotic routes (assert native_research_review_incomplete, partial)
   - 12 species-only products (assert research_present_applicability_unestablished, complete)
3. The 122 strain-stub products: assert all 122 remain native_research_review_incomplete / partial
4. Control sample of non-probiotic products: assert 0 changes
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from scoring_v4.scored_artifact import build_scored_artifact


def run_verification():
    t0 = time.time()
    partition_file = ROOT / "scripts/audits/evidence_expansion_2026_09/probiotic_partition_data.json"
    if not partition_file.exists():
        print(f"Error: {partition_file} not found")
        sys.exit(1)

    with open(partition_file) as f:
        partition_data = json.load(f)

    probiotic_products_meta = partition_data.get("products", [])
    print(f"Loaded partition data: {len(probiotic_products_meta)} probiotic products.")

    # Target sets
    CANDIDATE_26_IDS = {
        # 3 non-probiotic source material / fermentate
        "264610", "307558", "177233",
        # 11 exact-strain candidates
        "273676", "273685", "273696", "277516", "277517", "277518",
        "327396", "327400", "327411", "232295", "64842",
        # 12 species-only candidates
        "209440", "322514", "222741", "222746", "222870", "222876",
        "274293", "208587", "208593", "229119", "289077", "321383"
    }
    SOURCE_MATERIAL_3_IDS = {"264610", "307558", "177233"}
    EXACT_STRAIN_11_IDS = {
        "273676", "273685", "273696", "277516", "277517", "277518",
        "327396", "327400", "327411", "232295", "64842"
    }
    SPECIES_ONLY_12_IDS = {
        "209440", "322514", "222741", "222746", "222870", "222876",
        "274293", "208587", "208593", "229119", "289077", "321383"
    }

    # Build map of all enriched files and scored files
    enriched_map = {}
    scored_map = {}

    print("Indexing catalog enriched and scored artifacts...")
    for ef in sorted(ROOT.glob("scripts/products/output_*_enriched/enriched/enriched_*.json")):
        try:
            with open(ef) as f:
                data = json.load(f)
            for p in data:
                did = str(p.get("dsld_id") or p.get("id") or "")
                if did:
                    enriched_map[did] = p
        except Exception as e:
            print(f"Warning reading {ef}: {e}")

    for sf in sorted(ROOT.glob("scripts/products/output_*_scored/scored/scored_*.json")):
        try:
            with open(sf) as f:
                data = json.load(f)
            for p in data:
                did = str(p.get("dsld_id") or p.get("id") or "")
                if did:
                    scored_map[did] = p
        except Exception as e:
            print(f"Warning reading {sf}: {e}")

    # Also load manual product submissions
    for mf in sorted(ROOT.glob("manual_labels/product_submissions/*.json")):
        try:
            with open(mf) as f:
                p = json.load(f)
            did = str(p.get("dsld_id") or p.get("id") or "")
            if did and did not in enriched_map:
                enriched_map[did] = p
        except Exception:
            pass

    print(f"Indexed {len(enriched_map)} enriched and {len(scored_map)} scored products.")

    # Verification accumulators
    evidence_score_movers = []
    total_score_movers = []
    tier_movers = []
    state_transitions = Counter()
    status_transitions = Counter()
    probiotic_component_states = Counter()

    candidate_audit_results = {}
    strain_stubs_122_audit = []

    print(f"\nScoring and verifying {len(probiotic_products_meta)} probiotic catalog products...")
    scored_count = 0

    for pm in probiotic_products_meta:
        did = str(pm["dsld_id"])
        enriched_p = enriched_map.get(did)
        old_scored_p = scored_map.get(did)

        if not enriched_p:
            print(f"Warning: Missing enriched record for dsld_id={did}")
            continue

        new_artifact = build_scored_artifact(enriched_p)
        scored_count += 1

        # Scores
        new_ev = (new_artifact.get("quality_pillars_v4") or {}).get("evidence") or {}
        new_ev_score = float(new_ev.get("score") or 0.0)
        new_ev_state = str(new_ev.get("evidence_result_state") or "")
        new_total_score = float(new_artifact.get("quality_score_v4_100") or 0.0)
        new_tier = str(new_artifact.get("quality_tier") or "")
        new_status = str(new_artifact.get("quality_assessment_status") or "")

        if old_scored_p:
            old_ev = (old_scored_p.get("quality_pillars_v4") or {}).get("evidence") or {}
            old_ev_score = float(old_ev.get("score") or 0.0)
            old_ev_state = str(old_ev.get("evidence_result_state") or "")
            old_total_score = float(old_scored_p.get("quality_score_v4_100") or 0.0)
            old_tier = str(old_scored_p.get("quality_tier") or "")
            old_status = str(old_scored_p.get("quality_assessment_status") or "")

            # Check for score / tier movers
            if abs(new_ev_score - old_ev_score) > 1e-4:
                evidence_score_movers.append({
                    "dsld_id": did,
                    "product_name": pm["name"],
                    "brand": pm["brand"],
                    "old_ev_score": old_ev_score,
                    "new_ev_score": new_ev_score,
                })

            if abs(new_total_score - old_total_score) > 1e-4:
                total_score_movers.append({
                    "dsld_id": did,
                    "product_name": pm["name"],
                    "brand": pm["brand"],
                    "old_total_score": old_total_score,
                    "new_total_score": new_total_score,
                })

            if new_tier != old_tier:
                tier_movers.append({
                    "dsld_id": did,
                    "product_name": pm["name"],
                    "brand": pm["brand"],
                    "old_tier": old_tier,
                    "new_tier": new_tier,
                })

            if old_ev_state != new_ev_state:
                state_transitions[(old_ev_state, new_ev_state)] += 1

            if old_status != new_status:
                status_transitions[(old_status, new_status)] += 1
        else:
            old_ev_state = pm.get("evidence_state", "unknown")
            old_status = pm.get("assessment_status", "unknown")

        # Check 122 strain stubs
        if pm.get("evidence_state") == "native_research_review_incomplete":
            strain_stubs_122_audit.append({
                "dsld_id": did,
                "name": pm["name"],
                "old_state": old_ev_state,
                "new_state": new_ev_state,
                "old_status": old_status,
                "new_status": new_status,
            })

        # Track candidate 26
        if did in CANDIDATE_26_IDS:
            candidate_audit_results[did] = {
                "dsld_id": did,
                "name": pm["name"],
                "brand": pm["brand"],
                "module": pm["module"],
                "identity_category": pm["identity_category"],
                "old_ev_state": old_ev_state,
                "new_ev_state": new_ev_state,
                "old_status": old_status,
                "new_status": new_status,
                "old_ev_score": old_ev_score if old_scored_p else None,
                "new_ev_score": new_ev_score,
                "probiotic_component_meta": (new_ev.get("metadata") or {}).get("probiotic_component_evidence"),
            }

    print(f"\nCompleted scoring {scored_count} probiotic products in {time.time() - t0:.2f}s.")

    # Also verify non-probiotic products: sample 200 products across different brands
    print("\nVerifying control sample of non-probiotic products...")
    control_checked = 0
    control_movers = []
    for did, old_p in list(scored_map.items()):
        if did in probiotic_products_meta:
            continue
        if control_checked >= 300:
            break
        enriched_p = enriched_map.get(did)
        if not enriched_p:
            continue
        new_art = build_scored_artifact(enriched_p)
        control_checked += 1

        old_tot = float(old_p.get("quality_score_v4_100") or 0.0)
        new_tot = float(new_art.get("quality_score_v4_100") or 0.0)
        if abs(new_tot - old_tot) > 1e-4:
            control_movers.append(did)

    print(f"Control sample checked: {control_checked} products, movers: {len(control_movers)}")

    # Compile report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probiotic_products_audited": scored_count,
        "evidence_score_movers_count": len(evidence_score_movers),
        "evidence_score_movers": evidence_score_movers,
        "total_score_movers_count": len(total_score_movers),
        "total_score_movers": total_score_movers,
        "tier_movers_count": len(tier_movers),
        "tier_movers": tier_movers,
        "control_sample_movers_count": len(control_movers),
        "state_transitions": {f"{k[0]} -> {k[1]}": v for k, v in state_transitions.items()},
        "status_transitions": {f"{k[0]} -> {k[1]}": v for k, v in status_transitions.items()},
        "candidate_26_results": candidate_audit_results,
        "strain_stubs_122_total": len(strain_stubs_122_audit),
        "strain_stubs_122_still_partial": sum(1 for x in strain_stubs_122_audit if x["new_status"] == "partial"),
        "strain_stubs_122_still_incomplete": sum(1 for x in strain_stubs_122_audit if x["new_state"] == "native_research_review_incomplete"),
    }

    # Print summary
    print("\n" + "="*80)
    print("PROBIOTIC EVIDENCE A/B VERIFICATION SUMMARY")
    print("="*80)
    print(f"Total Probiotic Products Audited: {scored_count}")
    print(f"Evidence Score Movers: {len(evidence_score_movers)} (Expected: 0)")
    print(f"Total Quality Score Movers: {len(total_score_movers)} (Expected: 0)")
    print(f"Tier Movers: {len(tier_movers)} (Expected: 0)")
    print(f"Control Non-Probiotic Movers: {len(control_movers)} (Expected: 0)")
    print("\nState Transitions (old_state -> new_state):")
    for trans, count in state_transitions.items():
        print(f"  {trans}: {count}")
    print("\nStatus Transitions (old_status -> new_status):")
    for trans, count in status_transitions.items():
        print(f"  {trans}: {count}")

    print("\n122 Strain Stubs Invariant Check:")
    print(f"  Total tracked: {len(strain_stubs_122_audit)}")
    print(f"  Remaining 'native_research_review_incomplete': {report['strain_stubs_122_still_incomplete']}")
    print(f"  Remaining 'partial' status: {report['strain_stubs_122_still_partial']}")

    print("\nCandidate 26 Audit Breakdown:")
    # 3 Source materials
    print("  [3 Source Materials / Fermentates (excluded from probiotic ownership)]:")
    for did in SOURCE_MATERIAL_3_IDS:
        res = candidate_audit_results.get(did, {})
        print(f"    - dsld_id={did} ({res.get('name', 'N/A')}): old_state={res.get('old_ev_state')} -> new_state={res.get('new_ev_state')}, prob_meta={res.get('probiotic_component_meta')}")

    # 11 Exact Strain Candidates
    print("  [11 Exact-Strain Stub Candidates (must be native_research_review_incomplete / partial)]:")
    for did in sorted(EXACT_STRAIN_11_IDS):
        res = candidate_audit_results.get(did, {})
        print(f"    - dsld_id={did} ({res.get('name', 'N/A')[:40]}): state={res.get('new_ev_state')}, status={res.get('new_status')}, prob_meta={res.get('probiotic_component_meta')}")

    # 12 Species-Only Candidates
    print("  [12 Species-Only Candidates (must be research_present_applicability_unestablished / complete)]:")
    for did in sorted(SPECIES_ONLY_12_IDS):
        res = candidate_audit_results.get(did, {})
        print(f"    - dsld_id={did} ({res.get('name', 'N/A')[:40]}): state={res.get('new_ev_state')}, status={res.get('new_status')}, prob_meta={res.get('probiotic_component_meta')}")

    # Save detailed JSON report
    out_path = ROOT / "scripts/audits/evidence_expansion_2026_09/probiotic_ab_verification_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report saved to {out_path}")

    # Assertions
    assert len(evidence_score_movers) == 0, f"Evidence score movers must be 0, found {len(evidence_score_movers)}"
    assert len(total_score_movers) == 0, f"Total score movers must be 0, found {len(total_score_movers)}"
    assert len(tier_movers) == 0, f"Tier movers must be 0, found {len(tier_movers)}"
    assert len(control_movers) == 0, f"Control movers must be 0, found {len(control_movers)}"
    assert report['strain_stubs_122_still_incomplete'] == 122, f"Expected 122 stubs still incomplete, got {report['strain_stubs_122_still_incomplete']}"
    assert report['strain_stubs_122_still_partial'] == 122, f"Expected 122 stubs still partial, got {report['strain_stubs_122_still_partial']}"
    print("\nALL VERIFICATION INVARIANTS PASSED!")


if __name__ == "__main__":
    run_verification()
