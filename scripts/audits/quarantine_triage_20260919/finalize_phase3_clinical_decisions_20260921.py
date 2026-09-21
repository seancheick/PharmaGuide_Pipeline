#!/usr/bin/env python3
"""Record the approved Phase-3 clinical decisions in the closure ledger.

Clinical authority: **Dr. Pham / PharmaGuide Clinical Team**, 2026-09-21.

Writes a `clinical_policy_decisions_20260921` block into
`phase3_closure_dispositions_20260920.json` and reclassifies the EDTA residual
from "safety policy disposition pending" to the implemented approved policy.
Idempotent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LEDGER = (
    REPO_ROOT
    / "scripts"
    / "audits"
    / "quarantine_triage_20260919"
    / "phase3_closure_dispositions_20260920.json"
)

AUTHORITY = {
    "clinical_reviewer": "Dr. Pham",
    "team": "PharmaGuide Clinical Team",
    "decision_date": "2026-09-21",
    "phase": "Phase 3",
    "policy_decisions": "approved as documented",
    "overall": "APPROVED WITH SPECIFIED PRODUCTS HELD",
    "governance_note": (
        "Per PharmaGuide owner governance this is sufficient clinical sign-off "
        "authority for Phase 3; no licence number, state licence, credential "
        "verification, external attestation, or additional pharmacist paperwork "
        "is required or recorded."
    ),
}

EDTA_DISODIUM_IDS = [
    "252358", "253339", "253350", "253357",
    "312449", "312450", "312451", "312452",
]
EDTA_CALCIUM_DISODIUM_IDS = [
    "252426", "253331", "253335", "253336",
    "311259", "311260", "311261", "311262",
]

DECISIONS = {
    "edta_standalone_oral": {
        "policy": "BLOCKED_SAFETY_CARD_NO_SCORE",
        "products": {
            "disodium_edetate": EDTA_DISODIUM_IDS,
            "calcium_disodium_edetate": EDTA_CALCIUM_DISODIUM_IDS,
        },
        "reason_semantics": ["NON_ROUTINE_CHELATOR", "CLINICIAN_REVIEW_REQUIRED"],
        "invariants": [
            "disodium and calcium disodium edetate remain distinct identities",
            "never collapsed into a generic EDTA safety identity",
            "declared-active label role only; excipient EDTA is out of scope",
            "no quality score is produced; display_100 is N/A",
            "consumer copy asserts no proven acute oral toxicity",
        ],
        "implementation": [
            "scripts/data/banned_recalled_ingredients.json :: "
            "BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM / "
            "BANNED_NON_ROUTINE_CHELATOR_CALCIUM_DISODIUM_EDETATE",
            "scripts/scoring_v4/gate_safety.py :: verdict_reason_code + "
            "role_scope_out_of_scope support",
            "scripts/audits/quarantine_triage_20260919/"
            "apply_edta_non_routine_chelator_policy.py",
        ],
        "policy_basis_authority": "FDA (single-source position)",
        "policy_basis": [
            "FDA, Questions and Answers on Unapproved Chelation Products: FDA "
            "has never approved any chelation product for OTC use for any "
            "health condition; all FDA-approved chelation products require a "
            "prescription.",
            "FDA, warning on Captomer products: FDA advises consumers to avoid "
            "all products offered over the counter for chelation; there are no "
            "FDA-approved OTC chelation products.",
        ],
        "not_asserted": "proven acute toxicity of the labelled oral dose",
    },
    "botanical_standardization_constituents": {
        "policy": "CONTAINED_CONSTITUENT_MODEL_APPROVED",
        "products": ["216948", "232718", "216776", "44423", "77254"],
        "approved_role": "contained_standardization_constituent",
        "invariants": [
            "parent standardized extract owns the formulation dose",
            "child quantity is preserved as disclosure",
            "child is not counted as independent additive mass",
            "child remains available to Safety matching and to evidence matching",
            "criterion is structural, not exact arithmetic equality",
            "no product-id-specific allowlist",
        ],
        "safety_preserved": (
            "232718 keeps B0_WATCHLIST_SUBSTANCE; 216948 keeps "
            "B0_HIGH_RISK_SUBSTANCE"
        ),
        "terminology": {
            "runtime_name": "standardization_marker",
            "recorded_meaning": (
                "a contained quantified constituent of a dosed parent extract, "
                "not necessarily an inert marker"
            ),
            "rename_to": "contained_standardization_constituent",
            "decision": (
                "recorded as non-blocking technical debt; not performed in "
                "Phase 3 because it reaches the cleaner enum, the form-fallback "
                "audit data, the replay classifier and six test modules"
            ),
        },
    },
    "discrete_enzyme_formulation": {
        "policy": "NOT_INDIVIDUALLY_RATED_APPROVED",
        "formulation_evidence_state": "NOT_INDIVIDUALLY_RATED",
        "formulation_credit": "none",
        "formulation_penalty": "none",
        "consumer_presentation": (
            "Not individually rated — we don't currently apply enzyme-specific "
            "formulation evidence to this ingredient."
        ),
        "mechanism": (
            "the existing Formulation-pillar unrated-form neutral floor "
            "(_unrated_form_neutral_ratio); no new denominator or normalisation "
            "was introduced"
        ),
        "not_permanent": (
            "a discrete enzyme becomes rateable once qualifying enzyme-specific "
            "evidence exists"
        ),
        "measured_effect": (
            "28 score changes, all inside the discrete-enzyme / "
            "probiotic-evidence family; 0 Safety-field changes; 0 quarantine "
            "exits; 1 new quarantine (269360, restored dose; residual is "
            "identity-scoring)"
        ),
    },
    "beta_carotene_vitamin_a_ul": {
        "policy": "PREFORMED_VITAMIN_A_ONLY",
        "scope": "closed",
        "detail": (
            "only preformed vitamin A participates in the preformed Vitamin-A "
            "UL; beta-carotene and other provitamin-A carotenoids contribute 0 "
            "and receive no high-dose beta-carotene warning at the resolved "
            "Phase-3 doses (~6.0-6.834 mg/day)"
        ),
        "future_rule_recorded_not_blocking": {
            "threshold_mg_per_day": 15,
            "threshold_is_official_ul": False,
            "note": (
                "no established beta-carotene UL exists; 15 mg/day is a "
                "PharmaGuide operational threshold. Stack-aware personalized "
                "CAUTION at >=15 mg/day and stronger CAUTION at >=20 mg/day for "
                "current/former smokers or significant asbestos exposure. Not a "
                "Phase-3 blocker; recorded for a future stack-Safety phase."
            ),
        },
    },
}

POLICY_LEDGER_STATUS = {
    "edta_standalone_oral": "BLOCKED_SAFETY_CARD_NO_SCORE",
    "botanical_standardization_constituents": "CONTAINED_CONSTITUENT_MODEL_APPROVED",
    "discrete_enzyme_formulation": "NOT_INDIVIDUALLY_RATED_APPROVED",
    "beta_carotene_vitamin_a_ul": "PREFORMED_VITAMIN_A_ONLY",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(LEDGER.read_text(encoding="utf-8"))

    block = {
        "authority": AUTHORITY,
        "policy_ledger_status": POLICY_LEDGER_STATUS,
        "decisions": DECISIONS,
        "clinical_policy_unresolved": 0,
        "record": "PHASE3_CLINICAL_POLICY_20260921.md",
    }

    if payload.get("clinical_policy_decisions_20260921") == block:
        print("already recorded")
    elif args.check:
        print("DRIFT: clinical_policy_decisions_20260921 differs from expected")
        return 1
    else:
        payload["clinical_policy_decisions_20260921"] = block

    # The EDTA residual is no longer pending: it now carries the decided policy.
    changed = False
    for item in payload.get("remaining_external") or []:
        if not isinstance(item, dict):
            continue
        if item.get("classification") == "safety_policy_disposition":
            item["classification"] = "resolved_clinical_policy"
            item["clinical_decision"] = "BLOCKED_SAFETY_CARD_NO_SCORE"
            item["decided_by"] = "Dr. Pham / PharmaGuide Clinical Team (2026-09-21)"
            item["owner"] = "implemented (see clinical_policy_decisions_20260921)"
            changed = True

    if changed and not args.check:
        LEDGER.write_text(
            json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    print("clinical decisions recorded; EDTA residual reclassified:", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
