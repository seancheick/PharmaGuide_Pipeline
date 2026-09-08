# Independent canary review — 2026-09-08

Reviewer: `/root/review_gate_supported`. Scope: the 16 canary failures in the retained full-backstop XML, plus subsequent read-only review of the first three test-only repairs. No production/data/test files changed by this reviewer; only this requested receipt was authored. No full suite or pipeline rerun. Bounded in-memory scoring used current enriched products and the synthetic test fixture.

## Verdict and limits

All 16 failures have stale test premises, not a newly demonstrated production regression. Recommend narrow expectation/fixture corrections with mechanism assertions retained or strengthened; do not increase production scores, widen ranges indiscriminately, remove the high-band coverage requirement, or restore invented per-strain allocations. This is not independent clinical source re-verification or a general clinical-readiness conclusion.

The original full run remains **16,223 passed, 19 failed, 72 skipped**. This review does not turn it into a passing full run. Subsequent focused results must be reported separately.

Important score distinction: cross-module and gate canaries assert `score_probiotic(...).score_100` or `raw_score_v4_100`; the earlier approved corpus report stores six-pillar `quality_score_v4_100`. These are intentionally different surfaces. All 14 affected real IDs have matching current shipped summaries in the earlier approved report: 13 in `canaries`; Hair Sweet Hair 241692 in `changes`. Its earlier report also explicitly records rejection of swallowed-zinc evidence. Relevant production source hashes below match that report's `candidate_code_hashes`.

## Per-failure recommendation

| Failing family / ID | Current raw or dimension result | Shipped score | Source-backed reason and test recommendation |
| --- | ---: | ---: | --- |
| Cross-module 306247 FloraSport | 62.5 | 67.2 | Dose 16; evidence 2 from HN019's retained null-outcome multiplier 0.25; DE111 receives no human-evidence credit. Refresh narrow range; retain certification-positive assertion and pin evidence mechanism. |
| Cross-module 201158 OLLY Quick Melt | 47.5 | 54.6 | No per-strain CFU; named aggregate floor 4 × 0.85 = dose 3.4. LGG context earns evidence 8 without dose applicability. Refresh range; retain positive trust. |
| Cross-module 178346 Spring Valley | 35.5 | 44.4 | Ten named species, no label-owned clinical strains or individual CFU; aggregate presence floor 2 × 0.85 = dose 1.7, evidence 0. Replace obsolete equal-split proxy assertions with exact disclosure-only fields below; retain trust zero. |
| Cross-module 286725 vitafusion | 46.8 | 53.4 | Two disclosed CFU rows, dose 12.55; DE111's currently recorded source does not establish human evidence, evidence 0. Refresh range; retain positive dose and trust zero. |
| Cross-module 184730 Pure Probiotic 123 | 41.6 | 48.8 | Named aggregate floor gives dose 3.4; native research review remains incomplete, evidence 0. Refresh range without implying the review gap proves ineffectiveness; retain trust positive. |
| Cross-module 76803 GNC Prenatal | 42.6 | 45.2 | Two strains, zero individual CFU; named floor 4 × 0.85 = dose 3.4, LGG contextual evidence 8. Keep prenatal routing and replace invented-allocation assertions with disclosure-only mechanism below. |
| Gate 241706 Ripped Rooster | null / NOT_SCORED / confidence null | null | Identity conflict, coverage 2/3; missing strict contract, mapped coverage, identity readiness. `score_unavailable_reason=blocked_by_completeness_gate`; no module assembled. Preserve separate CAUTION safety gate and its non-short-circuit behavior. Assert exact completeness exclusion instead of restoring numeric CAUTION. |
| Gate 241707 Skin Squad | 36.2 / POOR / low | 44.0 | Total CFU absent, dose 0; strongest contextual research only, evidence 8. The raw <40 verdict rule applies despite shipped total 44. Preserve disclosure-debt assertions. |
| Gate 12932 Fiber Gummies | 50.0 / SAFE / moderate | 53.2 | Raw unchanged. Evidence confidence driver `evidence_review_incomplete`; curation backlog is not low calculation confidence. Update only confidence expectation and pin driver. |
| Gate 2266 Triple Chlorophyll | 48.2 / SAFE / moderate | 57.0 | Raw unchanged. Evidence driver `evidence_review_complete_limited_or_negative`; limited support is not an incomplete calculation. Update confidence and pin driver. |
| Gate 241692 Hair Sweet Hair | 50.7 / SAFE / moderate | 57.4 | `INGR_ZINC_PICOLINATE` correctly rejected `clinical_delivery_mismatch`. Existing record explicitly requires acetate/gluconate lozenges; label is gummy. Retained raw evidence 5.265 comes from Biotin/B12. Keep PABA/Fo-Ti unevaluated rows; evidence debt remains shadow-only. Earlier report `changes` already has this exact result and rejection. |
| Gate 230149 OLLY Extra Strength | 64.6 / SAFE / high | 68.3 | Dose 15.1 from disclosure/potency, evidence 6 contextual MTCC5856; DE111 no human credit. Retain high confidence/certification and pin no unreviewed dose-applicability points. |
| Gate 206362 GNC Kids Fast Stix | 41.1 / SAFE / moderate | 45.8 | Dose 1.7 aggregate-only; evidence 5.94 comes from independent Vitamin D3, native strain credit 0. Refresh verdict/range; do not remove valid independent evidence to restore POOR. |
| Omega final 273630 | 84.5 | 87.3 | Exact current NSF SKU entry is already present in prior approved replay. Refresh final range, tied to registry identity below. |
| Omega trust 273630 | 15 /15 | verification 15 | Cert 10 + cert-implied GMP 4 + brand posture 2, capped at 15. Assert exact NSF SKU record and component origins, not merely a 15-point floor; MSC `claimed_only` remains uncredited. |
| Synthetic probiotic above-40 | Original fixture 39.2 / POOR | Not a corpus product | Fictional aggregate-only label rows do not own the attached clinical strain records. Preserve this as negative aggregate+cert case. Existing five individually disclosed 10B named rows produce 50.5 / SAFE and dose 10, evidence 0: adequate positive threshold fixture, but this is disclosure credit, not clinically verified potency or benefit. |

## Exact aggregate-only dose observations

178346:

```json
{"score":1.7,"components":{"per_strain_cfu_disclosure":0.0,"cfu_adequacy":1.7},"aggregate_cfu_proxy":{"applied":true,"score":2.0,"cap":4.0,"reason":"aggregate_cfu_label_presence","total_billion_count":50.0,"floor":2.0},"cfu_guarantee":{"type":"unknown","multiplier":0.85,"applied":true,"reason":"cfu_guarantee_not_disclosed","adjusted_score":1.7},"window_proxy_reason":"aggregate_cfu_not_per_strain","cfu_adequacy_basis":"aggregate_cfu_disclosed_only","per_strain_cfu_disclosed_count":0,"total_strain_count":10,"reference_basis":"industry_potency_not_trial_efficacy"}
```

76803:

```json
{"score":3.4,"components":{"per_strain_cfu_disclosure":0.0,"cfu_adequacy":3.4},"aggregate_cfu_proxy":{"applied":true,"score":4.0,"cap":4.0,"reason":"aggregate_cfu_named_label_presence","total_billion_count":20.0,"floor":4.0},"cfu_guarantee":{"type":"unknown","multiplier":0.85,"applied":true,"reason":"cfu_guarantee_not_disclosed","adjusted_score":3.4},"window_proxy_reason":"aggregate_cfu_not_per_strain","cfu_adequacy_basis":"aggregate_cfu_disclosed_only","per_strain_cfu_disclosed_count":0,"total_strain_count":2,"reference_basis":"industry_potency_not_trial_efficacy"}
```

`proxy_tier`, equal-split `contributions`, and `aggregate_cfu_modeled_proxy` are obsolete. Current `probiotic_dose._compute_aggregate_cfu_proxy` explicitly never divides aggregate CFU into unmeasured individual doses.

## Honest high-band replacement

Add existing reviewed Seed `PG_SUB_35E0BD3374BF494B80FEABE87FC559E7`; keep the >=65 high-band requirement. Independently measured direct/raw 78.3, shipped 81.2, SAFE/moderate, formulation 23, dose 25, evidence 10.2, transparency 12. Dose metadata: `assessment_status=assessed_studied_formula`, `dose_adequacy_basis=studied_formula_native_afu`, `evidence_id=FORMULA_SEED_DS01`, daily dose 53,600,000,000 AFU, individual CFU disclosure count 0, `window_proxy_reason=formula_dose_not_individual_strain_doses`. No AFU-to-CFU conversion or fabricated per-strain allocation. Merely lowering the six existing ranges would otherwise leave no high probiotic canary.

## Omega registry identity to pin

Current source 273630 is `Advanced Omega Lemon Flavor`, brand `Garden of Life Dr. Formulated`, canonical `form_factor=capsule`. Its verified program has `record_id=NSF_CERTIFIE_FE59EE128321`, `program=NSF Certified`, `scope=sku`, `match_confidence=1.0`, `matched_brand=Garden of Life, LLC`, `matched_product=Garden of Life® Dr. Formulated Advanced Omega`, `notes=registry_discovered_product_match`, `verified_at=snapshot_date=2026-06-15`, `recency_status=fresh`. Local registry entry has `product_form=Softgel`; it is not a manufacturer-only record. Do not assert snapshot age as a timeless constant.

`score_trust` records `b4a.B4a_scored_entries=[{program:NSF Certified,scope:sku,pts:10}]`; GMP metadata source is `verified_cert_implies_gmp` with NSF Certified/raw4. MSC is `claimed_only`, rejected under `scope_not_in_verified_set`; no COA or batch lookup. Prior report's `cert_after` already has this exact NSF record and shipped 87.3/verification15.

## Review of the first three test-only repairs

No important issue found in the inspected repairs:

- Canonical continuity: `label_active_projection` is explicitly classified by `scoring_input_contract._scoring_input_kind_for_product_evidence` and built with `evidence_origin=compatibility_derived`. Including it in derived-origin assertions is correct. The new invariant retains row-level scope, source path, and unchanged clean/scoring identity. This does not make it non-material product-level evidence.
- EpiCor: exact alias occurs in `standardized_botanicals.epicor`; generic `other_ingredients` explicitly disclaims branded ownership. Existing Sep-04 audit records exact-identity-only correction and unchanged scores. Updated exact branded expectation is correct; adjacent generic expected result stays unchanged.
- PureWay-C: enrichment's `_source_owned_active_ingredients_for_enrichment` joins exact source path plus label identity, otherwise constructs a scoring-only row lacking the label's forms. Adding `ingredientRows[0]` restores an actual fixture ownership link; it is not a scoring exception. Positive branded-evidence assertions remain, and the new missing-link negative test retains generic Vitamin C evidence while rejecting borrowed branded credit.

## Evidence hashes inspected

Paths below are relative to repository root; SHA-256 values were read during this review.

| Artifact | SHA-256 |
| --- | --- |
| `reports/identity_quarantine_2026_09_08/full_serial_candidate.xml` | `e0f69af0b5fb6f72c1fed497717aebf825ea3679e42d86c27d7f0c9934a0c52d` |
| `reports/scoring_merge_2026_09_08/corpus_dose_closure_verified.json` | `97c930705071cceced31d538aa5b4eb758f3fef300cffebe67043d4d08b7f832` |
| `reports/identity_quarantine_2026_09_08/corpus_after_cert_order.json` | `9677fabb244314156dacc674c1ab59088fded10108b7879d27505c0141457f7d` |
| `reports/identity_quarantine_2026_09_08/candidate_verification.json` | `26fdec913fb2d8acef8c2d8b991c343988bf06692b6de8865929c00e37dd72ac` |
| `reports/identity_quarantine_2026_09_08/candidate/dist/pharmaguide_core.db` | `5f4dc14d3d3aa9cc960d1c4468099e4a99dbf34e81be3d14c0c55329800f07a6` |
| `scripts/data/cert_registry.json` | `19694aa4c0b8ec98eaf2c5b27f68d2ee018ef01d9d7ab7b1598d222dd16fedad` |
| `scripts/scoring_v4/modules/probiotic_dose.py` | `776467261e96b29e9a0039b3f8b2e5c6b6b694b1d04aec8d96f48cc930a80f46` |
| `scripts/scoring_v4/modules/probiotic_evidence.py` | `f1bf706c97a5b25107b725600ef470e2a79e95610da7d924bc9ba30e468b5ecf` |
| `scripts/scoring_v4/confidence.py` | `114a6fe332ed3007dee122e25c9a3a6bcc390b1a8c124b328217a84b1c64f351` |
| `scripts/score_supplements_v4.py` | `9a57e8c63d941e6abe71fe701ccf473957481b563165344c1b91254f758ad3b7` |
| `scripts/scoring_v4/modules/omega_trust.py` | `76da293c8e3dbfe224c9c6e9f29aaba67e0f7597d0776ff50685ae59308d5f82` |

The five scoring-source entries above were individually compared to the earlier approved corpus report and matched. Local registry content is reviewed as an artifact here, not independently fetched from NSF in this task.
