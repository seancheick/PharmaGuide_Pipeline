# G. Safety report (HEAD 391b87c5)

## Verdict precedence and owners (traced)
- `scoring_v4/gate_safety.py::evaluate_safety_gate` → `SafetyGateResult` (BLOCKED / UNSAFE from banned_recalled resolver hits over active + inactive rows, role-scoped policy via `identity.safety.safety_policy_status_for_role`, capture gaps and resolver errors recorded in `ingredient_assessment_errors`); `score_supplements_v4.py::_verdict_from_score` and `scored_artifact.py::_public_verdict` / `_product_safety_status` (BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE); UL → `scoring_v4/dose_safety.py::resolve_dose_safety` (CAUTION ceiling, `B7_dose_safety` Dose penalty, Safety/Hygiene); interactions → `enrich_supplements_v3.py::_collect_interaction_profile` (advisory; never moves the verdict) with subjects from `identity/interaction.py`; harmful additives → `inactive_ingredient_resolver` + Formulation B1 + Safety/Hygiene.
- Sample evidence (probes): 33360 Iron Legion designer steroid → `suppressed_safety`, blob warning `banned_substance critical BANNED_DIMETHANDROSTENOL` (ships blocked with its reason: release rule satisfied). 311187 Frangula bark → scored 39.8, Safety/Hygiene 0, `WATCH_FRANGULA` (2df4bed2 confirmed live). 182627 Life Extension Mix → RISK_BITTER_ORANGE + BANNED_BITTER_ORANGE warnings, Safety/Hygiene 0. 17192 Colon Cleanser → ADD_CASCARA_SAGRADA high, Safety/Hygiene 0. 224794/213472 → beta-carotene lung-cancer caution at ≥ 7,500 mcg RAE (P4 receipt verified); 297614/180316/206312 → informational only below the threshold. 4 BLOCKED + 1 suppressed probiotic in the sample, unchanged pre-window → HEAD (0 safety-verdict changes on 143 labels).

## Fail-open sweep (§15/§32)
| file | except Exception | return None | fail_open/neutral | assessment |
|---|---|---|---|---|
| gate_safety.py | 4 | 4 | 0 | all four append an error to `ingredient_assessment_errors` and continue with fewer hits → **RR-08** (flag has no consumer) |
| quality_score.py | 0 | 8 | 3 (Verification `fail_open_neutral`) | documented and reported in the driver field (rule-compliant) |
| scoring_input_contract.py | 7 | 55 | 1 | `except` blocks wrap optional projections (classification, evidence rows); `return None` are typed "no value" reads; the fail-open string is the plant-part scope mode name |
| enrich_supplements_v3.py | 15 | 135 | 3 | not individually triaged (24k lines); the three fail-open hits are the plant-part `fail_open` scope (checked by `db_integrity_sanity_check`) |
| build_final_db.py | 8 | 44 | 0 | export-side; no verdict computed here |
| identity/safety.py, inactive_ingredient_resolver.py, dose_safety.py, cert_evidence.py, evidence_resolver.py, safety_hygiene.py | 0 | 2–7 | 0 | no exception swallowing; cert policy now raises `CertificationPolicyError` (4233181d) |
- Interaction rules: presence rules stay visible when the amount is unknown (e70a4adf); plant-part rules fail open on an unconfirmed part (`form_scope_match: fail_open`, integrity-checked); an unknown `form_scope_match` value is rejected by `db_integrity_sanity_check` (21209f21).
- Citation gates: `verify_interaction_rules_citations.py --strict` hard-fails the release; `verify_all_citations_content.py --baseline` fails on unresolved or new mismatches; a `partial` match passes silently (166 in Q22) — INFO.

## Separation (quality / product safety / personalized / stack)
- Product quality: six pillars, never softened by safety (BLOCKED/UNSAFE suppress the score: `quality_score_status: suppressed_safety`, 73 candidate products). Product safety: `product_safety_status`, `verdict`, `has_banned_substance`, `has_recalled_ingredient`, `blocking_reason`. Personalized: profile-gated warnings (`warnings_profile_gated`, conditions/drug classes, dose gates evaluated by the app's `profile_gate_evaluator.dart` against the viewer's intake). Stack: `ingredient_fingerprint` + `key_ingredient_tags` (presence rule shared with the enricher since 01213079).
- Double deductions that exist by policy (D12 open): UL excess → Dose penalty + Safety/Hygiene + CAUTION; harmful additives → Formulation B1 + Safety/Hygiene.

## Findings referenced: RR-08 (dormant fail-open), RR-07 (a classifier miss zeroes Formulation — quality, not safety), none P0.
